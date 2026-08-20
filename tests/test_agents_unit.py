"""Unit tests for the agent layer: contracts, LLM output validation, the
deterministic TEST fallback, incident lifecycle, and the no-shell-execution
guarantee.

These tests need no infrastructure (no Docker, no MCPs, no agents running).

Run:  python -m pytest tests/test_agents_unit.py -v
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agents import llm
from agents.common import (
    AgentError,
    DiagnosisRequest,
    DiagnosisResult,
    Incident,
    InvestigationRequest,
    InvestigationResult,
    RemediationRequest,
    RemediationResult,
)
from agents.commander import FAILED, RESOLVED, IncidentContext, _validate_result

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / "agents"


# ---------------------------------------------------------------------------
# Contract validation
# ---------------------------------------------------------------------------


def test_incident_requires_id():
    with pytest.raises(ValidationError):
        Incident(service="auth-api")  # type: ignore[call-arg]


def test_incident_validates_severity():
    with pytest.raises(ValidationError):
        Incident(incident_id="i1", service="auth-api", severity="extreme")


def test_incident_roundtrip():
    incident = Incident(incident_id="inc-1", service="auth-api", severity="high", description="down")
    restored = Incident.model_validate(incident.model_dump())
    assert restored == incident


def test_investigation_request_validates_limit():
    with pytest.raises(ValidationError):
        InvestigationRequest(incident_id="i1", service="auth-api", limit=0)
    with pytest.raises(ValidationError):
        InvestigationRequest(incident_id="i1", service="auth-api", limit=99999)


def test_diagnosis_request_accepts_evidence():
    req = DiagnosisRequest(incident_id="i1", service="auth-api",
                           evidence=[{"index": 0, "text": "ERROR boom"}])
    assert req.evidence[0].text == "ERROR boom"


def test_all_contracts_roundtrip():
    for model, payload in [
        (InvestigationResult, {"incident_id": "i1", "service": "auth-api", "evidence": [], "status": "ok"}),
        (DiagnosisResult, {"incident_id": "i1", "service": "auth-api", "status": "ok"}),
        (RemediationRequest, {"incident_id": "i1", "service": "auth-api"}),
        (RemediationResult, {"incident_id": "i1", "service": "auth-api", "status": "ok"}),
    ]:
        assert model.model_validate(model.model_validate(payload).model_dump()) is not None


# ---------------------------------------------------------------------------
# LLM output validation
# ---------------------------------------------------------------------------


def _valid_output(**overrides):
    data = {
        "diagnosis": "auth-api is unhealthy, a restart is appropriate.",
        "confidence": 0.9,
        "root_cause": "simulated failure",
        "requires_remediation": True,
        "recommended_action": "restart_service",
        "target_service": "auth-api",
    }
    data.update(overrides)
    return data


def test_llm_output_accepts_valid_schema():
    llm.DiagnosisOutput.model_validate(_valid_output())


@pytest.mark.parametrize("action", ["run_shell", "bash", "docker_exec", "execute_shell", "run_command", "rm -rf /"])
def test_llm_output_rejects_arbitrary_actions(action):
    with pytest.raises(ValidationError):
        llm.DiagnosisOutput.model_validate(_valid_output(recommended_action=action))


def test_llm_output_rejects_arbitrary_target_service():
    with pytest.raises(ValidationError):
        llm.DiagnosisOutput.model_validate(_valid_output(target_service="postgres"))


@pytest.mark.parametrize("confidence", [-0.1, 1.5])
def test_llm_output_rejects_out_of_range_confidence(confidence):
    with pytest.raises(ValidationError):
        llm.DiagnosisOutput.model_validate(_valid_output(confidence=confidence))


def test_llm_parse_strips_markdown_fences():
    content = "```json\n" + json.dumps(_valid_output()) + "\n```"
    output = llm._parse_and_validate(content)
    assert output.recommended_action == "restart_service"


def test_llm_parse_rejects_invalid_json():
    with pytest.raises(json.JSONDecodeError):
        llm._parse_and_validate("this is not json")


def test_llm_parse_rejects_schema_violation():
    with pytest.raises(ValidationError):
        llm._parse_and_validate(json.dumps(_valid_output(recommended_action="curl http://evil")))


def test_llm_failure_is_clear_when_configured_but_unreachable(monkeypatch):
    monkeypatch.setenv("AEGISOPS_LLM_API_KEY", "sk-test")
    monkeypatch.setenv("AEGISOPS_LLM_BASE_URL", "http://127.0.0.1:1")  # nothing listens here
    with pytest.raises(llm.LLMUnavailableError):
        llm.generate_diagnosis("auth-api", [], {"http_code": 503}, {})


def test_fallback_enabled_gate(monkeypatch):
    monkeypatch.setenv("AEGISOPS_LLM_FALLBACK", "test")
    assert llm.test_fallback_enabled() is True
    monkeypatch.delenv("AEGISOPS_LLM_FALLBACK")
    assert llm.test_fallback_enabled() is False


def test_configured_requires_key(monkeypatch):
    monkeypatch.setenv("AEGISOPS_LLM_API_KEY", "sk-real")
    assert llm.configured() is True
    monkeypatch.delenv("AEGISOPS_LLM_API_KEY")
    assert llm.configured() is False


# ---------------------------------------------------------------------------
# Deterministic TEST fallback
# ---------------------------------------------------------------------------


def test_fallback_requires_restart_when_unhealthy_and_running():
    out = llm.fallback_diagnosis(
        "auth-api",
        [{"index": 0, "text": "ERROR crash"}],
        {"http_code": 503, "status": "unhealthy"},
        {"running": True, "health_status": "unhealthy"},
    )
    assert out.requires_remediation is True
    assert out.recommended_action == "restart_service"
    assert out.target_service == "auth-api"
    assert 0.0 <= out.confidence <= 1.0
    assert out.root_cause


def test_fallback_no_remediation_when_healthy():
    out = llm.fallback_diagnosis(
        "auth-api",
        [],
        {"http_code": 200, "status": "healthy"},
        {"running": True, "health_status": "healthy"},
    )
    assert out.requires_remediation is False
    assert out.recommended_action == "none"


def test_fallback_marked_not_model_generated():
    out = llm.fallback_diagnosis("auth-api", [], {"http_code": 503}, {"running": True})
    assert out.diagnosis  # it is a string, never carries llm_source="llm"
    assert not hasattr(out, "llm_source") or out.llm_source is None


# ---------------------------------------------------------------------------
# Incident lifecycle / commander internals
# ---------------------------------------------------------------------------


def test_incident_context_lifecycle():
    ctx = IncidentContext(Incident(incident_id="i1", service="auth-api"))
    assert ctx.status == "RECEIVED"
    ctx.stage("investigating", "running")
    ctx.stage("diagnosed", "ok")
    ctx.status = RESOLVED
    ctx.stage("incident_resolved", "ok")
    assert ctx.status == RESOLVED
    assert [t.stage for t in ctx.timeline] == ["investigating", "diagnosed", "incident_resolved"]
    assert all(isinstance(t.ts, float) for t in ctx.timeline)


def test_commander_accepts_valid_peer_response():
    payload = {"incident_id": "i1", "service": "auth-api", "evidence": [], "summary": "s", "status": "ok"}
    _validate_result(InvestigationResult, payload, "log-agent")  # must not raise


def test_commander_rejects_invalid_peer_response():
    with pytest.raises(AgentError):
        _validate_result(InvestigationResult, {"bogus": 1}, "log-agent")
    with pytest.raises(AgentError):
        _validate_result(DiagnosisResult, "not-a-dict", "diagnosis-agent")


def test_commander_failed_path():
    ctx = IncidentContext(Incident(incident_id="i1", service="auth-api"))
    ctx.status = FAILED
    ctx.error = "boom"
    ctx.stage("incident_failed", "error")
    assert ctx.status == FAILED
    assert ctx.error == "boom"
    assert ctx.timeline[-1].status == "error"


# ---------------------------------------------------------------------------
# No-shell-execution guarantee (static)
# ---------------------------------------------------------------------------


def test_agents_never_shell_out_to_docker_or_shell():
    """Agents must talk to Docker ONLY through the MCP layer."""
    banned = (
        "import subprocess",
        "from subprocess",
        "subprocess.run",
        "subprocess.Popen",
        "Popen(",
        "os.system",
        "shell=True",
    )
    for path in AGENTS_DIR.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        for token in banned:
            assert token not in source, f"{path.name} must not contain '{token}'"


def test_commander_never_restarts_docker_itself():
    source = (AGENTS_DIR / "commander.py").read_text(encoding="utf-8")
    for token in ("subprocess.run", "import subprocess", "Popen(", "shell=True"):
        assert token not in source, f"commander.py must not contain '{token}'"