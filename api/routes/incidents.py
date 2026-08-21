"""Incident routes: CRUD, timeline, audit."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from api.errors import error_response
from api.routes.system import get_current_user, require_auth
from database.audit import get_store as get_audit_store
from database.events import EventStore
from database.incidents import IncidentRecord, IncidentStore

router = APIRouter(tags=["incidents"])


# ---------------------------------------------------------------------------
# Store helpers (lazy, process-local singletons)
# ---------------------------------------------------------------------------


def _get_incident_store() -> IncidentStore:
    store = getattr(_get_incident_store, "_store", None)
    if store is None:
        store = IncidentStore()
        _get_incident_store._store = store
    return store


def _get_event_store() -> EventStore:
    store = getattr(_get_event_store, "_store", None)
    if store is None:
        store = EventStore()
        _get_event_store._store = store
    return store


# ---------------------------------------------------------------------------
# Commander proxy
# ---------------------------------------------------------------------------


async def trigger_commander(incident: dict) -> dict:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post("http://127.0.0.1:8094/incident", json=incident)
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/incidents")
async def list_incidents(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
):
    store = _get_incident_store()
    items = store.list(limit=limit, offset=offset, status=status)
    total = store.count(status=status)
    return {
        "items": [_record_to_dict(r) for r in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/incidents")
async def create_incident(body: dict):
    incident_id = body.get("incident_id", "")
    if not incident_id:
        return error_response(
            code="VALIDATION_ERROR", message="incident_id is required"
        )
    service = body.get("service", "auth-api")
    severity = body.get("severity", "high")
    description = body.get("description", "")

    record = IncidentRecord(
        id=incident_id,
        service=service,
        severity=severity,
        description=description,
        status="pending",
    )
    store = _get_incident_store()
    store.save(record)

    commander_payload = {
        "incident_id": incident_id,
        "service": service,
        "severity": severity,
        "description": description,
    }
    try:
        commander_result = await trigger_commander(commander_payload)
    except httpx.HTTPError as exc:
        store.update_status(incident_id, "error", str(exc))
        return error_response(
            code="COMMANDER_ERROR",
            message=f"Failed to forward to Commander: {exc}",
            status=502,
        )
    return {
        "incident_id": incident_id,
        "commander_result": commander_result,
    }


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: str):
    store = _get_incident_store()
    record = store.get(incident_id)
    if record is None:
        return error_response(
            code="NOT_FOUND",
            message=f"Incident {incident_id} not found",
            status=404,
        )

    event_store = _get_event_store()
    timeline = event_store.by_incident(incident_id, limit=200)

    audit_store = get_audit_store()
    audit_events = audit_store.by_incident(incident_id, limit=200)

    result: dict[str, Any] = _record_to_dict(record)
    result["timeline"] = timeline
    result["audit_events"] = audit_events
    return result


@router.get("/incidents/{incident_id}/timeline")
async def get_incident_timeline(incident_id: str, limit: int = Query(200, ge=1, le=1000)):
    event_store = _get_event_store()
    events = event_store.by_incident(incident_id, limit=limit)
    return {"incident_id": incident_id, "timeline": events}


@router.get("/incidents/{incident_id}/audit")
async def get_incident_audit(incident_id: str, limit: int = Query(200, ge=1, le=1000)):
    audit_store = get_audit_store()
    events = audit_store.by_incident(incident_id, limit=limit)
    return {"incident_id": incident_id, "audit_events": events}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _record_to_dict(r: IncidentRecord) -> dict[str, Any]:
    return {
        "id": r.id,
        "service": r.service,
        "status": r.status,
        "severity": r.severity,
        "description": r.description,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
        "resolved_at": r.resolved_at,
        "summary": r.summary,
        "diagnosis": r.diagnosis,
        "recommended_action": r.recommended_action,
        "resolution": r.resolution,
        "intent_token_status": r.intent_token_status,
        "governed": r.governed,
        "error": r.error,
    }