"""Explicit execution-plan + intent-token handshake with ArmorIQ (Phase 5).

Purpose (PLAN.md §5 Phase 5, ARCHITECTURE.md §ArmorIQ - Intent, not yet
enforcement): the Commander builds an EXPLICIT, 4-step plan for every incident,
captures it with ArmorIQ (``capture_plan``), and then requests an intent token
(``get_intent_token``). The token is retained by the Commander as readiness
state only - it is NOT returned in API responses, NOT logged, and NOT yet used
to authorize anything. Enforcement arrives in Phase 6 via ``delegate()``.

Verified against armoriq-sdk 0.6.10 (2026-08-20):
- capture_plan(llm, prompt, plan, metadata) -> PlanCapture  (local, no network)
- get_intent_token(plan_capture, policy, validity_seconds) -> IntentToken
  (network). The IntentToken object is SENSITIVE: it carries raw_token and
  jwt_token fields - never log or serialize it.

Failure handling: any error in this handshake is recorded on the incident as
intent_token_status="error"/"not_configured" but never blocks the unguarded
Phase 4 remediation flow (the system must keep working without ArmorIQ).
"""

from __future__ import annotations

from typing import Any

from armoriq.client_setup import load_env
from armoriq_sdk import ConfigurationException

# Label of the LLM that produced the plan context (a capture_plan metadata
# field, not a model invocation). Kept consistent with agents/llm.DEFAULT_MODEL.
PLAN_LLM_LABEL = "gemini-3.5-flash-lite"

# The explicit 4-step remediation plan shape (PLAN.md §5 / smoke test AEGIS_PLAN).
PLAN_ACTIONS = ("search_logs", "get_service_status", "inspect_service_state", "restart_service")


class PlanValidationError(ValueError):
    """The execution plan is malformed and cannot be captured."""


def armoriq_configured() -> bool:
    """True when a real ARMORIQ_API_KEY is present in the environment."""
    load_env()
    import os

    return bool(os.environ.get("ARMORIQ_API_KEY", "").strip())


def build_incident_plan(incident: Any) -> dict:
    """Build the explicit execution plan for an incident.

    Shape mirrors the AEGIS_PLAN from scripts/armoriq_smoke_test.py so a single
    plan structure is used everywhere. Each step names the MCP the action maps
    to; enforcement of these bindings is a Phase 6 concern.
    """
    service = incident.service
    steps = [
        {"action": "search_logs", "mcp": "log-mcp", "params": {"service": service}},
        {"action": "get_service_status", "mcp": "diagnostic-mcp", "params": {"service": service}},
        {"action": "inspect_service_state", "mcp": "diagnostic-mcp", "params": {"service": service}},
        {"action": "restart_service", "mcp": "remediation-mcp", "params": {"service": service}},
    ]
    return {
        "goal": (
            f"Investigate and remediate unhealthy service '{service}' "
            f"(incident {incident.incident_id})"
        ),
        "steps": steps,
    }


def validate_plan(plan: Any) -> None:
    """Structural validation of the execution plan. Raises PlanValidationError."""
    if not isinstance(plan, dict):
        raise PlanValidationError("plan must be a dict")
    goal = plan.get("goal")
    if not isinstance(goal, str) or not goal.strip():
        raise PlanValidationError("plan.goal must be a non-empty string")
    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        raise PlanValidationError("plan.steps must be a non-empty list")
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            raise PlanValidationError(f"plan.steps[{i}] must be a dict")
        action = step.get("action")
        mcp = step.get("mcp")
        params = step.get("params")
        if not isinstance(action, str) or not action.strip():
            raise PlanValidationError(f"plan.steps[{i}].action must be a non-empty string")
        if not isinstance(mcp, str) or not mcp.strip():
            raise PlanValidationError(f"plan.steps[{i}].mcp must be a non-empty string")
        if not isinstance(params, dict):
            raise PlanValidationError(f"plan.steps[{i}].params must be a dict")


def capture_execution_plan(client: Any, incident: Any) -> Any:
    """Build + validate + ArmorIQ-capture the execution plan.

    Returns a PlanCapture. Local operation (no network) once a client exists.
    """
    plan = build_incident_plan(incident)
    validate_plan(plan)
    return client.capture_plan(
        llm=PLAN_LLM_LABEL,
        prompt=(
            f"Explicit execution plan for incident {incident.incident_id} on "
            f"service {incident.service}."
        ),
        plan=plan,
        metadata={"incident_id": incident.incident_id, "service": incident.service},
    )


def generate_intent_token(client: Any, plan_capture: Any, validity_seconds: float = 300.0) -> Any:
    """Exchange a captured plan for an intent token (network call).

    Returns an IntentToken. The caller must treat it as SENSITIVE: never log,
    never serialize, never return in API responses.
    """
    if validity_seconds <= 0:
        raise PlanValidationError("validity_seconds must be positive")
    return client.get_intent_token(plan_capture, validity_seconds=validity_seconds)


def plan_ok_for_capture(plan: Any) -> None:
    """Public entry point used by the Commander before capturing.

    Raises PlanValidationError with a clear message on malformed plans.
    """
    validate_plan(plan)


__all__ = [
    "PLAN_LLM_LABEL",
    "PLAN_ACTIONS",
    "PlanValidationError",
    "armoriq_configured",
    "build_incident_plan",
    "validate_plan",
    "capture_execution_plan",
    "generate_intent_token",
    "plan_ok_for_capture",
    "ConfigurationException",
]