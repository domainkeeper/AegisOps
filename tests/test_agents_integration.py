"""Agent integration tests - real processes, real MCPs, real Docker.

Covers (PLAN.md §Testing, Phase 4):
- the four agents run as genuinely separate OS processes
- Log Agent -> log_mcp (real evidence)
- Remediation Agent -> remediation_mcp (real restart; idempotent no-op when healthy)
- Diagnosis Agent's UNGUARDED restart attempt through remediation_mcp
- Commander failure handling (structured FAILED outcome when a peer is unreachable)

No mocks. Requires a Docker engine. MCP servers and agents are spawned as real
subprocesses by the conftest fixtures (reused if already running).

Run:  python -m pytest tests/test_agents_integration.py -v
"""

from __future__ import annotations

import asyncio
import subprocess

import pytest

from agents.common import Incident
from agents.commander import FAILED, handle_incident
from conftest import (
    AUTH_API_FIX_URL,
    AUTH_API_HEALTH_URL,
    container_started_at,
    http,
    spawn_module,
)

LOG_AGENT_RUN_TASK = "http://127.0.0.1:8091/run_task"
DIAGNOSIS_AGENT_RUN_TASK = "http://127.0.0.1:8092/run_task"
REMEDIATION_AGENT_RUN_TASK = "http://127.0.0.1:8093/run_task"
COMMANDER_INCIDENT = "http://127.0.0.1:8094/incident"


def test_agents_are_separate_processes(agents_layer):
    procs = [
        spawn_module("agents.log_agent", 8191),
        spawn_module("agents.diagnosis_agent", 8192),
        spawn_module("agents.remediation_agent", 8193),
        spawn_module("agents.commander", 8194),
    ]
    pids = [p.pid for p in procs]
    assert len(set(pids)) == 4, "all four agents must be distinct OS processes"
    for port in (8191, 8192, 8193, 8194):
        status, body = http("GET", f"http://127.0.0.1:{port}/health")
        assert status == 200
        assert body["status"] == "ok"


def test_log_agent_returns_structured_evidence(agents_layer):
    status, result = http(
        "POST", LOG_AGENT_RUN_TASK,
        json_body={"incident_id": "itest-log", "service": "auth-api", "limit": 10},
    )
    assert status == 200
    assert result["status"] == "ok", result
    assert result["service"] == "auth-api"
    assert isinstance(result["evidence"], list)
    assert len(result["evidence"]) <= 10
    assert result["summary"].startswith("Collected")
    assert all({"index", "text"} <= set(item) for item in result["evidence"])


def test_log_agent_reports_mcp_error(agents_layer):
    status, result = http(
        "POST", LOG_AGENT_RUN_TASK,
        json_body={"incident_id": "itest-log-err", "service": "postgres"},
    )
    assert status == 200
    assert result["status"] == "error"
    assert result["error"]


def test_remediation_agent_noop_when_healthy(agents_layer):
    http("POST", AUTH_API_FIX_URL)
    started = container_started_at()
    status, result = http(
        "POST", REMEDIATION_AGENT_RUN_TASK,
        json_body={"incident_id": "itest-noop", "service": "auth-api"},
    )
    assert status == 200
    assert result["status"] == "ok", result
    assert result["noop"] is True
    assert result["success"] is True
    assert container_started_at() == started, "healthy service must NOT be restarted"


def test_remediation_agent_real_restart_when_broken(agents_layer):
    http("POST", AUTH_API_FIX_URL)
    http("POST", "http://localhost:8080/break")
    started = container_started_at()
    status, result = http(
        "POST", REMEDIATION_AGENT_RUN_TASK,
        json_body={"incident_id": "itest-restart", "service": "auth-api"},
    )
    assert status == 200
    assert result["status"] == "ok", result
    assert result["noop"] is False
    assert result["success"] is True
    assert result["started_at"] != started, "container start time must change - real restart"
    assert result["health"]["status"] == "healthy"


def test_diagnosis_agent_unguarded_restart_attempt(agents_layer):
    """The centerpiece of the unguarded baseline: the Diagnosis Agent itself
    reaches remediation_mcp and the restart SUCCEEDS."""
    http("POST", AUTH_API_FIX_URL)
    http("POST", "http://localhost:8080/break")
    started = container_started_at()
    status, result = http(
        "POST", DIAGNOSIS_AGENT_RUN_TASK,
        json_body={
            "incident_id": "itest-diag",
            "service": "auth-api",
            "evidence": [{"index": 0, "text": "ERROR simulated_failure"}],
        },
    )
    assert status == 200
    assert result["status"] == "ok", result
    assert result["requires_remediation"] is True
    assert result["recommended_action"] == "restart_service"
    assert result["target_service"] == "auth-api"
    assert result["remediation_attempted"] is True
    assert result["llm_source"] == "fallback", "no API key in tests - must be the marked fallback"
    rr = result["remediation_result"]
    assert rr["started_at"] != started, "diagnosis-triggered restart must be a REAL restart"
    assert rr["health"]["status"] == "healthy"


def test_commander_marks_failed_when_agent_unreachable(agents_layer, monkeypatch):
    """A dead peer must produce a structured FAILED outcome, never a hang or a lie."""
    monkeypatch.setattr("agents.commander.LOG_AGENT_URL", "http://127.0.0.1:9")
    result = asyncio.run(
        handle_incident(Incident(incident_id="itest-fail", service="auth-api", severity="high"))
    )
    assert result.status == FAILED
    assert result.error
    assert result.timeline[-1].stage == "incident_failed"
    assert result.timeline[-1].status == "error"