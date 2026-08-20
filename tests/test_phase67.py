"""Phase 6 + 7 tests: delegation, governed invocation, audit mirror.

Verified SDK surface (armoriq-sdk 0.6.10, source-inspected 2026-08-20):
- delegate(intent_token, delegate_public_key, validity_seconds=3600,
  allowed_actions=None, target_agent=None, subtask=None) -> DelegationResult
- invoke(mcp, action, intent_token, params=None, merkle_proof=None,
  user_email=None) -> MCPInvocationResult
- ArmorIQ rejections surface as ArmorIQException subclasses; nothing is faked.

Covered here (no network, no real key):
- three delegations with the exact verified scopes
- diagnosis scope EXCLUDES restart_service; remediation INCLUDES it
- delegation bound to each child's own Ed25519 public key
- safe metadata only; tokens never serialized in results or audit rows
- governed invoke success propagates the MCP result
- governed invoke rejection surfaces + audits the verified error type
- audit mirror records safe metadata and refuses secrets
- delegation failure keeps the unguarded baseline working
"""

from __future__ import annotations

import json
import importlib
from time import time

import pytest
from armoriq_sdk import DelegationException, PolicyBlockedException, InvalidTokenException
from armoriq_sdk.models import DelegationResult, IntentToken, MCPInvocationResult

from armoriq import client_setup
from armoriq.delegation import DELEGATION_SCOPES, create_delegations, delegations_metadata
from agents.common import DelegatedAuthority, Incident, invoke_governed
from agents.commander import IncidentContext, _capture_intent, _to_error_result
from database.audit import AuditStore


def _token(token_id: str = "tok-1") -> IntentToken:
    return IntentToken(
        token_id=token_id,
        plan_hash="h" * 64,
        signature="sig",
        issued_at=1.0,
        expires_at=time() + 3600,
        composite_identity="test",
        raw_token={"token": {"token_id": token_id, "plan": {"steps": [
            {"action": "search_logs"}, {"action": "get_service_status"},
            {"action": "inspect_service_state"}, {"action": "restart_service"},
        ]}}, "plan": {"steps": [
            {"action": "search_logs"}, {"action": "get_service_status"},
            {"action": "inspect_service_state"}, {"action": "restart_service"},
        ]}},
    )


def _delegation_result(agent: str, token: IntentToken, delegation_id: str) -> DelegationResult:
    return DelegationResult(
        delegation_id=delegation_id,
        delegated_token=token,
        delegate_public_key="k" * 64,
        expires_at=token.expires_at,
        trust_delta={},
        status="delegated",
        target_agent=agent,
        metadata={},
    )


class RecordingClient:
    """Stub client recording every SDK call; delegate/invoke programmable."""

    def __init__(self, root_token: IntentToken | None = None) -> None:
        self.root_token = root_token or _token()
        self.delegate_calls: list[dict] = []
        self.invoke_calls: list[dict] = []
        self.delegate_error: Exception | None = None
        self.invoke_error: Exception | None = None
        self.invoke_result: MCPInvocationResult | None = None

    def capture_plan(self, **kwargs):
        return {"captured": True}

    def get_intent_token(self, plan_capture, **kwargs):
        return self.root_token

    def delegate(self, **kwargs):
        if self.delegate_error is not None:
            raise self.delegate_error
        self.delegate_calls.append(kwargs)
        agent = kwargs["target_agent"]
        return _delegation_result(agent, _token(f"tok-{agent}"), f"did-{agent}")

    def invoke(self, **kwargs):
        if self.invoke_error is not None:
            raise self.invoke_error
        self.invoke_calls.append(kwargs)
        if self.invoke_result is not None:
            return self.invoke_result
        return MCPInvocationResult(
            mcp=kwargs["mcp"], action=kwargs["action"], result={"ok": True},
            status="success", execution_time=0.01, verified=True, metadata={},
        )


# ---------------------------------------------------------------------------
# Delegation: scopes, identity binding, metadata
# ---------------------------------------------------------------------------


def test_three_delegations_created_with_exact_scopes(monkeypatch, tmp_path):
    monkeypatch.setattr(client_setup, "KEYS_DIR", tmp_path)
    client = RecordingClient()
    records = create_delegations(client, client.root_token)
    assert set(records) == {"log_agent", "diagnosis_agent", "remediation_agent"}
    assert client.delegate_calls[0]["allowed_actions"] == ["search_logs"]
    assert client.delegate_calls[1]["allowed_actions"] == ["get_service_status", "inspect_service_state"]
    assert client.delegate_calls[2]["allowed_actions"] == ["restart_service"]


def test_diagnosis_scope_excludes_restart_service(monkeypatch, tmp_path):
    monkeypatch.setattr(client_setup, "KEYS_DIR", tmp_path)
    client = RecordingClient()
    records = create_delegations(client, client.root_token)
    assert "restart_service" not in records["diagnosis_agent"].allowed_actions
    assert DELEGATION_SCOPES["diagnosis_agent"] == ["get_service_status", "inspect_service_state"]


def test_remediation_scope_includes_restart_service(monkeypatch, tmp_path):
    monkeypatch.setattr(client_setup, "KEYS_DIR", tmp_path)
    client = RecordingClient()
    records = create_delegations(client, client.root_token)
    assert records["remediation_agent"].allowed_actions == ["restart_service"]


def test_delegation_bound_to_each_child_public_key(monkeypatch, tmp_path):
    monkeypatch.setattr(client_setup, "KEYS_DIR", tmp_path)
    client = RecordingClient()
    create_delegations(client, client.root_token)
    for call in client.delegate_calls:
        agent = call["target_agent"]
        expected = client_setup.public_key_hex(client_setup.ensure_keypair(agent))
        assert call["delegate_public_key"] == expected, f"{agent} must be bound to its own key"
    keys = {c["delegate_public_key"] for c in client.delegate_calls}
    assert len(keys) == 3, "three distinct child identities"


def test_delegation_metadata_never_contains_tokens(monkeypatch, tmp_path):
    monkeypatch.setattr(client_setup, "KEYS_DIR", tmp_path)
    client = RecordingClient()
    records = create_delegations(client, client.root_token)
    dumped = json.dumps(delegations_metadata(records))
    assert "raw_token" not in dumped and "jwt_token" not in dumped
    assert "tok-" not in dumped and "token" not in json.dumps(records["log_agent"].metadata())
    assert records["log_agent"].metadata()["allowed_actions"] == ["search_logs"]


def test_scope_validation_blocks_wrong_diagnosis_scope(monkeypatch, tmp_path):
    from armoriq import delegation as delegation_mod
    from armoriq.delegation import ScopeValidationError

    monkeypatch.setattr(client_setup, "KEYS_DIR", tmp_path)
    monkeypatch.setitem(
        delegation_mod.DELEGATION_SCOPES,
        "diagnosis_agent",
        ["get_service_status", "restart_service"],
    )
    client = RecordingClient()
    with pytest.raises(ScopeValidationError):
        create_delegations(client, client.root_token)
    delegated = [c["target_agent"] for c in client.delegate_calls]
    assert delegated == ["log_agent"], "no network call may be made with the bad scope"


def test_delegation_validity_must_be_positive(monkeypatch, tmp_path):
    from armoriq.delegation import ScopeValidationError

    monkeypatch.setattr(client_setup, "KEYS_DIR", tmp_path)
    with pytest.raises(ScopeValidationError):
        create_delegations(RecordingClient(), _token(), validity_seconds=0)


def test_delegation_failure_propagates_sdk_exception(monkeypatch, tmp_path):
    monkeypatch.setattr(client_setup, "KEYS_DIR", tmp_path)
    client = RecordingClient()
    client.delegate_error = DelegationException("trust rejected", target_agent="log_agent")
    with pytest.raises(DelegationException):
        create_delegations(client, client.root_token)


# ---------------------------------------------------------------------------
# Commander integration: delegation state on incidents
# ---------------------------------------------------------------------------


def _incident() -> Incident:
    return Incident(incident_id="p67-1", service="auth-api", severity="high", description="unhealthy")


def test_commander_delegates_when_intent_token_ready(monkeypatch, tmp_path):
    monkeypatch.setenv("ARMORIQ_API_KEY", "ak_test_1234")
    monkeypatch.setattr(client_setup, "KEYS_DIR", tmp_path)
    from armoriq import plan as plan_mod

    monkeypatch.setattr(plan_mod, "armoriq_configured", lambda: True)
    monkeypatch.setattr(client_setup, "get_client", lambda: RecordingClient())

    ctx = IncidentContext(_incident())
    _capture_intent(ctx)
    assert ctx.intent_token_status == "ready"
    assert ctx.governed is True
    assert ctx.delegation_error is None
    assert set(ctx.delegations) == {"log_agent", "diagnosis_agent", "remediation_agent"}

    result = _to_error_result(ctx)
    assert len(result.delegations) == 3
    assert result.governed is True
    actions = {d["agent"]: d["allowed_actions"] for d in result.delegations}
    assert actions["diagnosis_agent"] == ["get_service_status", "inspect_service_state"]
    assert actions["remediation_agent"] == ["restart_service"]


def test_delegation_failure_keeps_incident_unguarded(monkeypatch, tmp_path):
    monkeypatch.setenv("ARMORIQ_API_KEY", "ak_test_1234")
    monkeypatch.setattr(client_setup, "KEYS_DIR", tmp_path)
    from armoriq import plan as plan_mod

    monkeypatch.setattr(plan_mod, "armoriq_configured", lambda: True)
    client = RecordingClient()
    client.delegate_error = DelegationException("proxy unreachable", target_agent="log_agent")
    monkeypatch.setattr(client_setup, "get_client", lambda: client)

    ctx = IncidentContext(_incident())
    _capture_intent(ctx)
    assert ctx.intent_token_status == "ready"
    assert ctx.governed is False
    assert ctx.delegations == {}
    assert ctx.delegation_error and "DelegationException" in ctx.delegation_error

    result = _to_error_result(ctx)
    assert result.governed is False and result.delegations == []


def test_incident_result_never_contains_token_material(monkeypatch, tmp_path):
    monkeypatch.setenv("ARMORIQ_API_KEY", "ak_test_1234")
    monkeypatch.setattr(client_setup, "KEYS_DIR", tmp_path)
    from armoriq import plan as plan_mod

    monkeypatch.setattr(plan_mod, "armoriq_configured", lambda: True)

    class _SneakyClient(RecordingClient):
        def get_intent_token(self, plan_capture, **kwargs):
            return IntentToken(
                token_id="SECRET-ROOT", plan_hash="h" * 64, signature="sig",
                issued_at=1.0, expires_at=time() + 300, composite_identity="c",
                raw_token={"token": {"token_id": "SECRET-ROOT", "jwt_token": "JWT-SECRET"}},
            )

        def delegate(self, **kwargs):
            self.delegate_calls.append(kwargs)
            token = IntentToken(
                token_id="SECRET-CHILD", plan_hash="h" * 64, signature="sig",
                issued_at=1.0, expires_at=time() + 300, composite_identity="c",
                raw_token={"token": {"token_id": "SECRET-CHILD", "jwt_token": "JWT-SECRET"}},
            )
            return _delegation_result(kwargs["target_agent"], token, "did-secret")

    monkeypatch.setattr(client_setup, "get_client", lambda: _SneakyClient())
    ctx = IncidentContext(_incident())
    _capture_intent(ctx)
    assert ctx.governed is True

    dumped = json.dumps(_to_error_result(ctx).model_dump())
    for secret in ("SECRET-ROOT", "SECRET-CHILD", "JWT-SECRET", "raw_token", "jwt_token"):
        assert secret not in dumped, f"token material leaked into IncidentResult: {secret}"
    assert "did-secret" in dumped  # delegation_id is safe metadata


# ---------------------------------------------------------------------------
# Governed invocation
# ---------------------------------------------------------------------------


def _authority(agent: str = "log_agent") -> DelegatedAuthority:
    token = _token(f"tok-{agent}")
    return DelegatedAuthority(
        agent=agent,
        delegation_id=f"did-{agent}",
        allowed_actions=list(DELEGATION_SCOPES[agent]),
        expires_at=token.expires_at,
        target_agent=agent,
        token=token.model_dump(),
    )


def test_invoke_governed_success_propagates_mcp_result(monkeypatch, tmp_path):
    audit_mod = importlib.import_module("database.audit")

    store = AuditStore(tmp_path / "audit.db")
    monkeypatch.setattr(audit_mod, "get_store", lambda: store)
    client = RecordingClient()
    client.invoke_result = MCPInvocationResult(
        mcp="log-mcp", action="search_logs", result={"lines": ["a", "b"]},
        status="success", execution_time=0.01, verified=True, metadata={},
    )
    monkeypatch.setattr(client_setup, "get_client", lambda: client)

    out = invoke_governed(
        agent="log_agent", authority=_authority("log_agent"),
        mcp="log-mcp", action="search_logs",
        params={"service": "auth-api"}, incident_id="p67-1",
    )
    assert out == {"lines": ["a", "b"]}
    assert client.invoke_calls[0]["user_email"] == "log_agent@aegisops.local"
    assert client.invoke_calls[0]["intent_token"].token_id == "tok-log_agent"
    rows = store.recent()
    assert any(r["action"] == "log-mcp.search_logs" and r["status"] == "success" for r in rows)


def test_invoke_governed_blocked_surfaces_and_audits(monkeypatch, tmp_path):
    audit_mod = importlib.import_module("database.audit")

    from agents.common import AgentError

    store = AuditStore(tmp_path / "audit.db")
    monkeypatch.setattr(audit_mod, "get_store", lambda: store)
    client = RecordingClient()
    client.invoke_error = PolicyBlockedException(
        "Delegated token does not permit restart_service", enforcement_action="block",
        reason="scope violation", metadata={},
    )
    monkeypatch.setattr(client_setup, "get_client", lambda: client)

    with pytest.raises(AgentError) as exc_info:
        invoke_governed(
            agent="diagnosis_agent", authority=_authority("diagnosis_agent"),
            mcp="remediation-mcp", action="restart_service",
            params={"service_name": "auth-api"}, incident_id="p67-1",
        )
    assert "PolicyBlockedException" in str(exc_info.value)
    rows = store.recent()
    blocked = [r for r in rows if r["action"] == "remediation-mcp.restart_service"]
    assert blocked and blocked[0]["status"] == "blocked"
    assert blocked[0]["error_type"] == "PolicyBlockedException"


def test_invoke_governed_invalid_token_surfaces_and_audits(monkeypatch, tmp_path):
    audit_mod = importlib.import_module("database.audit")

    from agents.common import AgentError

    store = AuditStore(tmp_path / "audit.db")
    monkeypatch.setattr(audit_mod, "get_store", lambda: store)
    client = RecordingClient()
    client.invoke_error = InvalidTokenException("Token verification failed")
    monkeypatch.setattr(client_setup, "get_client", lambda: client)

    with pytest.raises(AgentError) as exc_info:
        invoke_governed(
            agent="log_agent", authority=_authority("log_agent"),
            mcp="log-mcp", action="search_logs", params={}, incident_id="p67-1",
        )
    assert "InvalidTokenException" in str(exc_info.value)
    rows = store.recent()
    assert any(r["status"] == "error" and r["error_type"] == "InvalidTokenException" for r in rows)


# ---------------------------------------------------------------------------
# Audit mirror
# ---------------------------------------------------------------------------


def test_audit_store_records_safe_metadata_and_no_secrets(tmp_path):
    store = AuditStore(tmp_path / "audit.db")
    store.record(incident_id="i-1", agent="remediation_agent", parent_agent="commander",
                 action="remediation-mcp.restart_service", status="success",
                 delegation_id="did-1")
    store.record(incident_id="i-1", agent="diagnosis_agent", parent_agent="commander",
                 action="delegate", status="error", error_type="DelegationException")
    rows = store.recent()
    assert len(rows) == 2
    assert rows[0]["action"] == "delegate" and rows[0]["error_type"] == "DelegationException"
    assert rows[1]["delegation_id"] == "did-1"
    dumped = json.dumps(rows)
    for secret in ("raw_token", "jwt_token", "api_key", "private_key", "signature", "secret"):
        assert secret not in dumped, f"audit mirror stored a secret: {secret}"


def test_audit_refuses_to_store_forbidden_values(tmp_path):
    store = AuditStore(tmp_path / "audit.db")
    with pytest.raises(ValueError):
        store.record(incident_id="i-1", agent="x", action="y", status="ok",
                     detail="token=AKIA...")
    with pytest.raises(ValueError):
        store.record(incident_id="i-1", agent="x", action="y", status="ok",
                     delegation_id="raw_token")


def test_audit_rows_have_incident_and_timestamp(tmp_path):
    store = AuditStore(tmp_path / "audit.db")
    store.record(incident_id="i-9", agent="log_agent", action="log-mcp.search_logs", status="success")
    row = store.recent(1)[0]
    assert row["incident_id"] == "i-9" and row["created_at"] and row["agent"] == "log_agent"