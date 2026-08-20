"""LIVE Phase 8 + 9 authorization verification - real ArmorIQ, real Docker.

These tests are separated from the offline suite by the `live` marker and
hard self-skips: they require a REAL ARMORIQ_API_KEY, a reachable ArmorIQ
proxy with the MCP servers registered (log-mcp, diagnostic-mcp,
remediation-mcp, reachable by the proxy via tunnel URLs), the local MCP
servers running, and the auth-api Docker container running.

Nothing here is mocked: the intent token is minted by the real platform,
delegations are real subtree delegations, and invoke() goes
Agent -> ArmorIQ invoke() -> authorization decision -> MCP -> Docker.

Phase 8 (BLOCKED): the Diagnosis Agent's delegated authority does not include
restart_service. A real invoke() with its real diagnosis token MUST be
rejected by ArmorIQ. Proof: the container's StartedAt is unchanged and the
audit mirror holds a status="blocked" row for the attempt.

Phase 9 (ALLOWED): the Remediation Agent's delegated authority DOES include
restart_service. A real invoke() with its real remediation token MUST be
accepted and the remediation MCP performs a REAL docker restart. Proof:
StartedAt changes, /health returns healthy, audit mirror holds status="success".

The ACTUAL rejection exception type from the live platform is observed and
recorded here - never hardcoded before it is seen: the test asserts the
rejection surfaces as an ArmorIQException subclass named in the message and
stores the exact class name in the audit error_type.

Run with:   python -m pytest tests/test_live_authorization.py -m live
Skipped (not passed) whenever the live prerequisites are missing.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.request

import pytest

pytestmark = pytest.mark.live


def _docker_started_at() -> str:
    out = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.StartedAt}}", "auth-api"],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        pytest.skip(f"auth-api container not running: {out.stderr.strip()}")
    return out.stdout.strip()


def _http_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


class LivePlatform:
    """Real platform context: client, intent token, three real delegations."""

    def __init__(self) -> None:
        from armoriq.client_setup import get_client
        from armoriq.plan import capture_execution_plan, generate_intent_token
        from armoriq.delegation import create_delegations
        from types import SimpleNamespace

        self.client = get_client()
        try:
            self.mcps = self.client.list_mcps()
        except Exception as exc:
            pytest.skip(f"ArmorIQ proxy unreachable: {type(exc).__name__}: {exc}")
        if not self.mcps:
            pytest.skip(
                "no MCPs registered on the ArmorIQ platform - register log-mcp, "
                "diagnostic-mcp and remediation-mcp with public tunnel URLs first"
            )

        self.incident_id = f"live-{int(time.time())}"
        incident = SimpleNamespace(incident_id=self.incident_id, service="auth-api")
        plan_capture = capture_execution_plan(self.client, incident)
        self.root_token = generate_intent_token(
            self.client, plan_capture, validity_seconds=300
        )
        self.records = create_delegations(self.client, self.root_token)

    def authority(self, agent: str):
        from agents.common import DelegatedAuthority

        record = self.records[agent]
        return DelegatedAuthority(
            agent=agent,
            delegation_id=record.delegation_id,
            allowed_actions=list(record.allowed_actions),
            expires_at=record.expires_at,
            target_agent=record.target_agent,
            token=record.token.model_dump(),
        )


@pytest.fixture()
def platform() -> LivePlatform:
    from armoriq.plan import armoriq_configured

    if not armoriq_configured():
        pytest.skip("ARMORIQ_API_KEY is not set - live verification requires a real key")
    return LivePlatform()


def _audit_rows():
    from database.audit import get_store

    return get_store().recent(500)


def test_live_three_real_delegations_with_exact_scopes(platform):
    assert set(platform.records) == {"log_agent", "diagnosis_agent", "remediation_agent"}
    for agent, expected in (
        ("log_agent", ["search_logs"]),
        ("diagnosis_agent", ["get_service_status", "inspect_service_state"]),
        ("remediation_agent", ["restart_service"]),
    ):
        record = platform.records[agent]
        assert record.status == "delegated"
        assert record.allowed_actions == expected
        assert record.delegation_id
        assert record.expires_at > time.time()
    # tokens are in memory; metadata serialization must not leak them
    dumped = json.dumps([r.metadata() for r in platform.records.values()])
    for secret in ("raw_token", "jwt_token", "signature", "api_key"):
        assert secret not in dumped


def test_live_diagnosis_restart_service_blocked(platform):
    """Phase 8: the diagnosis authority must be rejected for restart_service."""
    from agents.common import AgentError, invoke_governed

    started_before = _docker_started_at()
    before = len(_audit_rows())

    try:
        invoke_governed(
            agent="diagnosis_agent",
            authority=platform.authority("diagnosis_agent"),
            mcp="remediation-mcp",
            action="restart_service",
            params={"service_name": "auth-api"},
            incident_id=platform.incident_id,
        )
    except AgentError as exc:
        message = str(exc)
        # Observe the REAL production exception name from the live platform.
        match = re.search(r"\(([A-Za-z]+Exception)\)", message)
        assert match, f"rejection must name an ArmorIQ exception type: {message}"
        error_type = match.group(1)
        # A transport failure (proxy cannot reach the MCP) is NOT the
        # authorization decision this test must prove.
        assert error_type != "MCPInvocationException", (
            f"got a transport failure instead of an authorization rejection: {message}"
        )
        print(f"OBSERVED live rejection exception: {error_type}")
    else:
        pytest.fail("ArmorIQ ALLOWED restart_service for the diagnosis authority - this must never happen")

    assert _docker_started_at() == started_before, (
        "the blocked attempt must not touch the container"
    )
    new_rows = _audit_rows()[before:]
    blocked = [r for r in new_rows if r["action"] == "remediation-mcp.restart_service"
               and r["agent"] == "diagnosis_agent"]
    assert blocked, "audit mirror must hold the blocked row"
    assert blocked[0]["status"] == "blocked"
    assert blocked[0]["error_type"] and blocked[0]["error_type"] != "AgentError"


def test_live_remediation_restart_service_allowed(platform):
    """Phase 9: the remediation authority MUST be accepted for restart_service."""
    from agents.common import invoke_governed

    started_before = _docker_started_at()
    before = len(_audit_rows())

    result = invoke_governed(
        agent="remediation_agent",
        authority=platform.authority("remediation_agent"),
        mcp="remediation-mcp",
        action="restart_service",
        params={"service_name": "auth-api"},
        incident_id=platform.incident_id,
    )

    assert isinstance(result, dict) and result.get("success") is True, (
        f"remediation invoke must succeed: {result}"
    )
    started_after = _docker_started_at()
    assert started_after != started_before, "the authorized action must really restart the container"

    deadline = time.time() + 30
    while time.time() < deadline and not _http_ok("http://localhost:8080/health"):
        time.sleep(0.5)
    assert _http_ok("http://localhost:8080/health"), "auth-api /health must return 200 after restart"

    new_rows = _audit_rows()[before:]
    ok_rows = [r for r in new_rows if r["action"] == "remediation-mcp.restart_service"
               and r["agent"] == "remediation_agent"]
    assert ok_rows, "audit mirror must hold the success row"
    assert ok_rows[0]["status"] == "success"