"""Phase 5 tests: per-agent identities, explicit execution plan, intent token.

Covered (no real ArmorIQ account, no network, no faked tokens):
- Identity: four agents have distinct Ed25519 keypairs under .keys/ (gitignored);
  private key material is never exposed; per-agent email scopes.
- Plan: the Commander builds an explicit 4-step plan and validates it strictly.
- Intent token: capture_plan -> get_intent_token handshake via stub clients;
  honest not_configured/error states when ArmorIQ is unavailable; the token
  itself never appears in incident results or logs.

Hermetic: conftest forces ARMORIQ_API_KEY="" and AEGISOPS_GEMINI_API_KEY="".
"""

from __future__ import annotations

import json

import pytest

from armoriq import client_setup, plan as plan_mod
from armoriq_sdk import ConfigurationException
from agents.common import Incident
from agents.commander import IncidentContext, _capture_intent, _to_error_result

AGENTS = ("commander", "log_agent", "diagnosis_agent", "remediation_agent")


def _incident() -> Incident:
    return Incident(
        incident_id="p5-1",
        service="auth-api",
        severity="high",
        description="unhealthy",
    )


def _valid_plan() -> dict:
    return plan_mod.build_incident_plan(_incident())


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


def test_four_agents_have_distinct_keypairs(monkeypatch, tmp_path):
    monkeypatch.setattr(client_setup, "KEYS_DIR", tmp_path)
    public_keys = [
        client_setup.public_key_hex(client_setup.ensure_keypair(agent))
        for agent in AGENTS
    ]
    assert len(set(public_keys)) == 4, "each agent must have its own keypair"
    for agent in AGENTS:
        priv, pub = client_setup.keypair_paths(agent)
        assert priv.exists() and pub.exists()


def test_keypair_roundtrip_preserves_public_key(monkeypatch, tmp_path):
    monkeypatch.setattr(client_setup, "KEYS_DIR", tmp_path)
    first = client_setup.generate_and_save_keypair("commander")
    reloaded = client_setup.load_private_key("commander")
    assert client_setup.public_key_hex(reloaded) == client_setup.public_key_hex(first)


def test_ensure_keypair_is_idempotent(monkeypatch, tmp_path):
    monkeypatch.setattr(client_setup, "KEYS_DIR", tmp_path)
    a = client_setup.public_key_hex(client_setup.ensure_keypair("log_agent"))
    b = client_setup.public_key_hex(client_setup.ensure_keypair("log_agent"))
    assert a == b, "existing keypairs must never be regenerated"


def test_private_key_never_exposed_as_public_hex(monkeypatch, tmp_path):
    monkeypatch.setattr(client_setup, "KEYS_DIR", tmp_path)
    client_setup.ensure_keypair("diagnosis_agent")
    priv, pub = client_setup.keypair_paths("diagnosis_agent")
    assert priv.read_bytes() != pub.read_text().strip().encode()
    assert "PRIVATE KEY" not in pub.read_text()


def test_keys_dir_is_gitignored():
    import subprocess

    result = subprocess.run(
        ["git", "check-ignore", "-q", ".keys/commander/private.pem"],
        cwd=client_setup.PROJECT_ROOT,
        capture_output=True,
    )
    assert result.returncode == 0, ".keys/ must be gitignored (private keys never committed)"


def test_agent_email_follows_plan_convention(monkeypatch):
    monkeypatch.delenv("AEGISOPS_COMMANDER_EMAIL", raising=False)
    monkeypatch.delenv("AEGISOPS_LOG_AGENT_EMAIL", raising=False)
    monkeypatch.delenv("AEGISOPS_DIAGNOSIS_AGENT_EMAIL", raising=False)
    monkeypatch.delenv("AEGISOPS_REMEDIATION_AGENT_EMAIL", raising=False)
    assert client_setup.agent_email("commander") == "commander@aegisops.local"
    assert client_setup.agent_email("diagnosis_agent") == "diagnosis_agent@aegisops.local"


def test_agent_email_env_override(monkeypatch):
    monkeypatch.setenv("AEGISOPS_COMMANDER_EMAIL", "ops@company.example")
    assert client_setup.agent_email("commander") == "ops@company.example"


def test_agent_email_unknown_role_raises(monkeypatch):
    monkeypatch.delenv("AEGISOPS_UNKNOWN_EMAIL", raising=False)
    with pytest.raises(ConfigurationException):
        client_setup.agent_email("unknown_role")


def test_get_api_key_requires_valid_prefix(monkeypatch):
    monkeypatch.setenv("ARMORIQ_API_KEY", "garbage-not-an-armoriq-key")
    with pytest.raises(ConfigurationException):
        client_setup.get_api_key()
    monkeypatch.setenv("ARMORIQ_API_KEY", "ak_test_1234")
    assert client_setup.get_api_key() == "ak_test_1234"


# ---------------------------------------------------------------------------
# Explicit execution plan
# ---------------------------------------------------------------------------


def test_build_incident_plan_has_explicit_four_steps():
    plan = _valid_plan()
    assert plan["goal"]
    assert [s["action"] for s in plan["steps"]] == list(plan_mod.PLAN_ACTIONS)
    assert [s["mcp"] for s in plan["steps"]] == [
        "log-mcp", "diagnostic-mcp", "diagnostic-mcp", "remediation-mcp",
    ]
    assert all(s["params"]["service"] == "auth-api" for s in plan["steps"])


def test_validate_plan_accepts_valid_plan():
    plan_mod.plan_ok_for_capture(_valid_plan())


@pytest.mark.parametrize(
    "plan",
    [
        None,
        "not a dict",
        {"steps": []},
        {"goal": "", "steps": [{"action": "x", "mcp": "y", "params": {}}]},
        {"goal": "g", "steps": "nope"},
        {"goal": "g", "steps": ["not a dict"]},
        {"goal": "g", "steps": [{"mcp": "y", "params": {}}]},
        {"goal": "g", "steps": [{"action": "x", "params": {}}]},
        {"goal": "g", "steps": [{"action": "x", "mcp": "y"}]},
        {"goal": "g", "steps": [{"action": "", "mcp": "y", "params": {}}]},
    ],
)
def test_validate_plan_rejects_malformed(plan):
    with pytest.raises(plan_mod.PlanValidationError):
        plan_mod.plan_ok_for_capture(plan)


def test_capture_execution_plan_passes_intended_plan_and_label():
    captured = {}

    class _StubClient:
        def capture_plan(self, llm, prompt, plan, metadata):
            captured["llm"] = llm
            captured["prompt"] = prompt
            captured["plan"] = plan
            captured["metadata"] = metadata
            return {"captured": True}

    plan_mod.capture_execution_plan(_StubClient(), _incident())
    assert captured["llm"] == plan_mod.PLAN_LLM_LABEL
    assert captured["metadata"]["incident_id"] == "p5-1"
    assert [s["action"] for s in captured["plan"]["steps"]] == list(plan_mod.PLAN_ACTIONS)


def test_generate_intent_token_passes_plan_capture():
    seen = {}

    class _StubClient:
        def get_intent_token(self, plan_capture, policy=None, validity_seconds=60.0):
            seen["plan_capture"] = plan_capture
            seen["validity_seconds"] = validity_seconds
            return {"token": "x"}

    result = plan_mod.generate_intent_token(_StubClient(), {"captured": True}, validity_seconds=300.0)
    assert seen["validity_seconds"] == 300.0
    assert result == {"token": "x"}


def test_generate_intent_token_rejects_non_positive_validity():
    with pytest.raises(plan_mod.PlanValidationError):
        plan_mod.generate_intent_token(object(), {}, validity_seconds=0)


# ---------------------------------------------------------------------------
# Commander integration (intent handshake states; token never exposed)
# ---------------------------------------------------------------------------


def test_intent_capture_not_configured_without_key(monkeypatch):
    monkeypatch.setenv("ARMORIQ_API_KEY", "")
    ctx = IncidentContext(_incident())
    _capture_intent(ctx)
    assert ctx.plan is not None and len(ctx.plan["steps"]) == 4
    assert ctx.intent_token_status == "not_configured"
    assert ctx.intent_token_expires_at is None
    assert "ARMORIQ_API_KEY" in ctx.intent_token_error


def test_intent_capture_ready_with_stub_client(monkeypatch):
    monkeypatch.setenv("ARMORIQ_API_KEY", "ak_test_1234")
    monkeypatch.setattr(plan_mod, "armoriq_configured", lambda: True)

    class _Token:
        expires_at = "2026-08-20T12:00:00Z"

    class _StubClient:
        def capture_plan(self, **kwargs):
            return {"captured": True}

        def get_intent_token(self, plan_capture, **kwargs):
            assert plan_capture == {"captured": True}
            return _Token()

    monkeypatch.setattr(client_setup, "get_client", lambda: _StubClient())
    ctx = IncidentContext(_incident())
    _capture_intent(ctx)
    assert ctx.intent_token_status == "ready"
    assert ctx.intent_token_expires_at == "2026-08-20T12:00:00Z"
    assert ctx.intent_token_error is None


def test_intent_capture_records_handshake_error(monkeypatch):
    monkeypatch.setenv("ARMORIQ_API_KEY", "ak_test_1234")
    monkeypatch.setattr(plan_mod, "armoriq_configured", lambda: True)

    def _boom():
        raise ConfigurationException("network unreachable")

    monkeypatch.setattr(client_setup, "get_client", _boom)
    ctx = IncidentContext(_incident())
    _capture_intent(ctx)
    assert ctx.intent_token_status == "error"
    assert "network unreachable" in ctx.intent_token_error
    assert ctx.plan is not None, "plan stays captured locally even when the token step fails"


def test_intent_capture_records_plan_validation_error(monkeypatch):
    monkeypatch.setattr(plan_mod, "build_incident_plan", lambda incident: {"goal": "", "steps": []})
    ctx = IncidentContext(_incident())
    _capture_intent(ctx)
    assert ctx.intent_token_status == "error"
    assert "plan validation failed" in ctx.intent_token_error


def test_token_material_never_appears_in_incident_result(monkeypatch):
    monkeypatch.setenv("ARMORIQ_API_KEY", "ak_test_1234")
    monkeypatch.setattr(plan_mod, "armoriq_configured", lambda: True)

    class _Token:
        expires_at = "2026-08-20T12:00:00Z"
        raw_token = "RAW-SECRET"
        jwt_token = "JWT-SECRET"
        token_id = "tok-123"

    class _StubClient:
        def capture_plan(self, **kwargs):
            return {"captured": True}

        def get_intent_token(self, plan_capture, **kwargs):
            return _Token()

    monkeypatch.setattr(client_setup, "get_client", lambda: _StubClient())
    ctx = IncidentContext(_incident())
    _capture_intent(ctx)
    assert ctx.intent_token_status == "ready"

    result = _to_error_result(ctx)
    assert result.intent_token_expires_at == "2026-08-20T12:00:00Z"
    assert result.intent_token_status == "ready"
    dumped = json.dumps(result.model_dump())
    for secret in ("RAW-SECRET", "JWT-SECRET", "tok-123", "jwt_token", "raw_token"):
        assert secret not in dumped, "intent token material must never be serialized"
    assert not hasattr(ctx, "intent_token"), "the token object is never retained on the context"