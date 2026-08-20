"""ArmorIQ delegation - the explicit authority model (Phase 6, live-verified 2026-08-20).

VERIFIED LIVE against the real ArmorIQ platform (2026-08-20):
- `capture_plan()` + `get_intent_token()`: work (real tokens issued).
- `delegate()` (legacy CSRG path): **DEAD on this platform** - the live endpoint
  /iap/trust/delegate responds 400 `{"message":"parentToken is required"}`. The
  legacy payload shape (`token`/`delegate_public_key`/`validity_seconds`) is rejected.
- `delegate_subtree()`: **the working delegation mechanism** - posts
  `parentToken`/`delegatePublicKey`/`validitySeconds`/`subtreePath`/`planId` to the
  same endpoint and mints real subtree-bounded delegated tokens (trust_id,
  inclusion_proof, subtree_root, delegated_token with `subtree_delegation` metadata
  that invoke() auto-attaches as X-CSRG-Subtree-* headers).

The central authority model (Architecture Decision / authority matrix):

    Commander (root intent token over the full 4-step plan)
     ├── log_agent          -> steps [search_logs]
     ├── diagnosis_agent    -> steps [get_service_status, inspect_service_state]
     └── remediation_agent  -> steps [restart_service]

Each child's authority is expressed as a SUBTREE of the captured plan (step
indices), minted by the platform via delegate_subtree(). The platform's proxy
(PEP) rejects invocations outside the subtree at invoke() time.

Hard invariants enforced here, in tests, and by ArmorIQ itself:
- diagnosis_agent MUST NOT receive restart_service
- remediation_agent MUST receive restart_service
- each delegation is bound to the child's own Ed25519 public key (Phase 5)
- the delegated token is held in memory only; safe metadata only is serialized

Never log, serialize, or persist tokens (raw_token/jwt_token) or keys.

NOTE: the `subtree_path` wire format (comma-separated step indices, e.g. "1,2")
was accepted by the live platform for token minting; the proxy PEP's exact path
grammar is verified during Phase 8/9 live enforcement testing (MCPs must be
registered and reachable for invoke() to reach the PEP).
"""

from __future__ import annotations

import time
from typing import Any

from armoriq.client_setup import ensure_keypair, public_key_hex
from armoriq.plan import PLAN_ACTIONS
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


def subtree_path_for(agent: str) -> str:
    """The plan-subtree step indices for an agent's verified scope.

    Derived deterministically from PLAN_ACTIONS so the delegation always names
    exactly the steps the agent may take (and nothing more).
    """
    index_by_action = {action: str(i) for i, action in enumerate(PLAN_ACTIONS)}
    indices = [index_by_action[action] for action in DELEGATION_SCOPES[agent]]
    return ",".join(indices)


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
    def from_subtree(cls, agent: str, payload: dict[str, Any]) -> "DelegationRecord":
        """Build a record from the live delegate_subtree() response dict."""
        delegated_token = payload["delegated_token"]
        return cls(
            agent=agent,
            delegation_id=str(payload.get("trust_id") or delegated_token.token_id),
            allowed_actions=list(DELEGATION_SCOPES[agent]),
            expires_at=float(getattr(delegated_token, "expires_at", 0) or 0),
            status="delegated",
            target_agent=agent,
            token=delegated_token,
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

    Uses the platform's verified subtree-delegation mechanism
    (delegate_subtree()): each child gets exactly its verified scope, expressed
    as a plan subtree, bound to its own public key. Raises ScopeValidationError
    before any network call if a scope is wrong. Raises armoriq_sdk exceptions
    on failure - the caller records the failure; nothing is faked.
    """
    validity = validity_seconds if validity_seconds is not None else delegation_validity_seconds()
    if validity <= 0:
        raise ScopeValidationError("validity_seconds must be positive")

    records: dict[str, DelegationRecord] = {}
    for agent, scope in DELEGATION_SCOPES.items():
        _validate_scope(agent, scope)
        pubkey = public_key_hex(ensure_keypair(agent))
        result = client.delegate_subtree(
            root_token,
            delegate_public_key=pubkey,
            subtree_path=subtree_path_for(agent),
            validity_seconds=validity,
            target_agent=agent,
        )
        records[agent] = DelegationRecord.from_subtree(agent, result)
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
    "subtree_path_for",
]