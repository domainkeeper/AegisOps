"""Security / authority visualization routes."""

from __future__ import annotations

from fastapi import APIRouter

from armoriq.delegation import DELEGATION_SCOPES
from armoriq.plan import PLAN_ACTIONS

router = APIRouter(tags=["security"])


@router.get("/security/authority")
async def get_authority():
    authority_entries = [
        {
            "agent": agent,
            "allowed_actions": actions,
            "steps": [str(PLAN_ACTIONS.index(a)) for a in actions],
        }
        for agent, actions in DELEGATION_SCOPES.items()
    ]
    return {
        "authority_model": authority_entries,
        "plan_actions": list(PLAN_ACTIONS),
        "note": "This is a read-only authority visualization. "
        "The frontend must not decide authorization — "
        "all authorization decisions are enforced by ArmorIQ at invoke time.",
    }