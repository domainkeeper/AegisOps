"""ArmorIQ delegation - the explicit authority model (Phase 6).

Verified against installed armoriq-sdk 0.6.10 (source-inspected 2026-08-20) and
the official docs (docs.armoriq.ai/sdk/core-methods/delegate):

    delegate(intent_token, delegate_public_key, validity_seconds=3600,
             allowed_actions=None, target_agent=None, subtask=None)
             -> DelegationResult
    DelegationResult fields: delegation_id, delegated_token (IntentToken),
    delegate_public_key, target_agent, expires_at, trust_delta, status, metadata

The central authority model (Architecture Decision / authority matrix):

    Commander (root intent token over the full 4-step plan)
     ├── log_agent          -> ["search_logs"]
     ├── diagnosis_agent    -> ["get_service_status", "inspect_service_state"]
     └── remediation_agent  -> ["restart_service"]

Hard invariants enforced here, in tests, and by ArmorIQ itself:
- diagnosis_agent MUST NOT receive restart_service
- remediation_agent MUST receive restart_service
- each delegation is bound to the child's own Ed25519 public key (Phase 5)
- the delegated token is held in memory only; safe metadata only is serialized

Never log, serialize, or persist tokens (raw_token/jwt_token) or keys.
"""

from __future__ import annotations

import time
from typing import Any

from armoriq.client_setup import ensure_keypair, public_key_hex
from armoriq_sdk import DelegationResult
from armoriq_sdk.models import IntentToken

# The exact action names, matching the MCP layer tools 1:1 (no invented names).
DELEGATION_SCOPES: dict[str, list[str]] = {
    "log_agent": ["search_logs"],
    "diagnosis_agent": ["get_service_status", "inspect_service_state"],
    "remediation_agent": ["restart_service"],
}

CHILD_AGENTS = tuple(DELEGATION_SCOPES)

# Scopes that MUST never change without an explicit, reviewed decision.
_VERIFIED_SCOPES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("log_agent", ("search_logs",)),
    ("diagnosis_agent", ("get_service_status", "inspect_service_state")),
    ("remediation_agent", ("restart_service",)),
)


class ScopeValidationError(ValueError):
    """A delegation scope violates the verified authority model."""


def _validate_scope(agent: str, allowed_actions: list[str]) -> None:
    expected = dict(_VERIFIED_SCOPES)[agent]
    if tuple(sorted(allowed_actions)) != tuple(sorted(expected)):
        raise ScopeValidationError(
            f"scope for '{agent}' must be exactly {list(expected)}, got {allowed_actions}"
        )


def delegation_validity_seconds() -> int:
    """Default delegated-token validity (shorter than the root token, per SDK design)."""
    import os

    return int(os.environ.get("AEGISOPS_DELEGATION_VALIDITY", "300"))


class DelegationRecord:
    """A single in-memory delegation. The token is never serialized or logged."""

    __slots__ = (
        "agent",
        "delegation_id",
        "allowed_actions",
        "expires_at",
        "status",
        "target_agent",
        "token",
    )

    def __init__(
        self,
        agent: str,
        delegation_id: str,
        allowed_actions: list[str],
        expires_at: float,
        status: str,
        target_agent: str | None,
        token: IntentToken,
    ) -> None:
        self.agent = agent
        self.delegation_id = delegation_id
        self.allowed_actions = list(allowed_actions)
        self.expires_at = expires_at
        self.status = status
        self.target_agent = target_agent
        self.token = token

    @classmethod
    def from_result(cls, agent: str, result: DelegationResult) -> "DelegationRecord":
        return cls(
            agent=agent,
            delegation_id=result.delegation_id,
            allowed_actions=list(DELEGATION_SCOPES[agent]),
            expires_at=float(result.expires_at or 0),
            status=result.status or "delegated",
            target_agent=result.target_agent,
            token=result.delegated_token,
        )

    def metadata(self) -> dict[str, Any]:
        """SAFE metadata only - never includes the token or any secret."""
        return {
            "agent": self.agent,
            "delegation_id": self.delegation_id,
            "allowed_actions": list(self.allowed_actions),
            "expires_at": self.expires_at,
            "status": self.status,
            "target_agent": self.target_agent,
        }

    def authority_payload(self) -> dict[str, Any]:
        """Serialized authority for transport to the child agent over HTTP.

        Includes the delegated token because the child needs it to invoke
        through ArmorIQ. This is sent to the owning child only - never logged,
        never persisted, never returned in API responses.
        """
        return {
            "agent": self.agent,
            "delegation_id": self.delegation_id,
            "allowed_actions": list(self.allowed_actions),
            "expires_at": self.expires_at,
            "target_agent": self.target_agent,
            "token": self.token.model_dump(),
        }


def create_delegations(
    client: Any,
    root_token: IntentToken,
    validity_seconds: int | None = None,
) -> dict[str, DelegationRecord]:
    """Create the three delegated authorities from the Commander's root token.

    Each child gets exactly its verified scope, bound to its own public key.
    Raises ScopeValidationError before any network call if a scope is wrong.
    Raises armoriq_sdk.DelegationException / ArmorIQException on failure - the
    caller records the failure; nothing is faked.
    """
    validity = validity_seconds if validity_seconds is not None else delegation_validity_seconds()
    if validity <= 0:
        raise ScopeValidationError("validity_seconds must be positive")

    records: dict[str, DelegationRecord] = {}
    for agent, scope in DELEGATION_SCOPES.items():
        _validate_scope(agent, scope)
        pubkey = public_key_hex(ensure_keypair(agent))
        result = client.delegate(
            intent_token=root_token,
            delegate_public_key=pubkey,
            validity_seconds=validity,
            allowed_actions=list(scope),
            target_agent=agent,
        )
        records[agent] = DelegationRecord.from_result(agent, result)
    return records


def delegations_metadata(records: dict[str, DelegationRecord]) -> list[dict[str, Any]]:
    """Safe metadata for all delegations (never tokens)."""
    return [r.metadata() for r in records.values()]


def is_expired(record: DelegationRecord, now: float | None = None) -> bool:
    now = now or time.time()
    return bool(record.expires_at) and now > record.expires_at


__all__ = [
    "DELEGATION_SCOPES",
    "CHILD_AGENTS",
    "ScopeValidationError",
    "DelegationRecord",
    "create_delegations",
    "delegations_metadata",
    "delegation_validity_seconds",
    "is_expired",
]