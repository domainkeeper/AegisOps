"""End-to-end test: one complete incident through the real, unguarded
multi-agent system.

break auth-api
  -> Commander receives incident (HTTP)
  -> Log Agent investigates via log_mcp
  -> Diagnosis Agent inspects via diagnostic_mcp, produces diagnosis
     (deterministic TEST fallback - no API key in tests) and performs the
     UNGUARDED restart attempt through remediation_mcp
  -> Remediation Agent confirms/restarts via remediation_mcp
  -> Commander verifies /health and marks the incident RESOLVED

The final Docker restart is REAL - never mocked. Requires a Docker engine.

Run:  python -m pytest tests/test_e2e.py -v
"""

from __future__ import annotations

import pytest

from conftest import AUTH_API_BREAK_URL, AUTH_API_HEALTH_URL, container_started_at, http

COMMANDER_INCIDENT = "http://127.0.0.1:8094/incident"

EXPECTED_STAGES = [
    "incident_received",
    "investigated",
    "diagnosed",
    "remediated",
    "verified",
    "incident_resolved",
]


def test_full_incident_flow_resolves_with_real_restart(agents_layer):
    started_before = container_started_at()

    # 2. break auth-api, 3. wait until /health reports unhealthy
    http("POST", AUTH_API_BREAK_URL)
    deadline = 30.0
    import time

    t0 = time.time()
    while time.time() - t0 < deadline:
        status, body = http("GET", AUTH_API_HEALTH_URL)
        if status == 503 and body.get("status") == "unhealthy":
            break
        time.sleep(0.5)
    else:
        pytest.fail("auth-api did not go unhealthy")

    # 4. submit the incident to the Commander (real HTTP)
    status, result = http(
        "POST", COMMANDER_INCIDENT,
        json_body={
            "incident_id": "e2e-incident-1",
            "service": "auth-api",
            "severity": "high",
            "description": "auth-api reporting unhealthy",
        },
    )
    assert status == 200, result

    # 12. incident must reach RESOLVED with no swallowed errors
    assert result["status"] == "RESOLVED", result.get("error")
    assert result["service"] == "auth-api"
    assert result["error"] is None

    # timeline is complete and ordered
    stages = [t["stage"] for t in result["timeline"]]
    for expected in EXPECTED_STAGES:
        assert expected in stages, f"missing stage {expected} in {stages}"
    assert stages[-1] == "incident_resolved"
    assert result["timeline"][-1]["status"] == "ok"

    # investigation evidence was actually collected
    assert len(result["investigation"]["evidence"]) > 0

    # diagnosis: LLM/fallback reasoning concluded remediation is needed, and the
    # Diagnosis Agent performed the UNGUARDED restart attempt that succeeded
    diag = result["diagnosis"]
    assert diag["status"] == "ok", diag
    assert diag["requires_remediation"] is True
    assert diag["remediation_attempted"] is True
    assert diag["llm_source"] == "fallback", "tests run without an API key"
    assert diag["remediation_result"]["started_at"] != started_before

    # remediation agent path: service already recovered by the diagnosis attempt,
    # so the idempotency guard reports a healthy no-op (still success)
    rem = result["remediation"]
    assert rem["status"] == "ok", rem
    assert rem["success"] is True
    assert rem["noop"] is True

    # 11. Commander verified recovery via diagnostic_mcp
    assert result["verification"]["http_code"] == 200
    assert result["verification"]["status"] == "healthy"

    # Phase 5 intent handshake: the Commander built and captured the explicit
    # 4-step plan locally. With no ARMORIQ_API_KEY in tests the token step is
    # honestly reported as not_configured - never faked, never blocking.
    plan = result["plan"]
    assert plan is not None
    assert [s["action"] for s in plan["steps"]] == [
        "search_logs", "get_service_status", "inspect_service_state", "restart_service",
    ]
    assert all(s["mcp"] for s in plan["steps"])
    assert result["intent_token_status"] == "not_configured"
    assert result["intent_token_error"] and "ARMORIQ_API_KEY" in result["intent_token_error"]
    assert result["intent_token_expires_at"] is None

    # Phase 6/7: with no ArmorIQ connection there is no root token to delegate
    # from, so the incident runs UNGUARDED (Phase 4 baseline) - reported
    # honestly as zero delegations and governed=False.
    assert result["delegations"] == []
    assert result["governed"] is False

    # The Docker container genuinely restarted (start time changed) and is healthy
    started_after = container_started_at()
    assert started_after == diag["remediation_result"]["started_at"], "reported restart must match docker"
    assert started_after != started_before, "container must have really restarted"

    status, final = http("GET", AUTH_API_HEALTH_URL)
    assert status == 200
    assert final["status"] == "healthy"