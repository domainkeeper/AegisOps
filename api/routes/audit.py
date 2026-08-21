"""Audit log routes: searchable, paginated."""

from __future__ import annotations

from fastapi import APIRouter, Query

from database.audit import get_store

router = APIRouter(tags=["audit"])


@router.get("/audit")
async def list_audit(
    incident_id: str | None = Query(None),
    agent: str | None = Query(None),
    action: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
):
    store = get_store()
    rows = store.recent(limit=limit + offset)

    if incident_id:
        rows = [r for r in rows if r.get("incident_id") == incident_id]
    if agent:
        rows = [r for r in rows if r.get("agent") == agent]
    if action:
        rows = [r for r in rows if r.get("action") == action]
    if status:
        rows = [r for r in rows if r.get("status") == status]
    if from_:
        rows = [r for r in rows if (r.get("created_at") or "") >= from_]
    if to:
        rows = [r for r in rows if (r.get("created_at") or "") <= to]

    total = len(rows)
    paged = rows[offset : offset + limit]

    return {
        "items": paged,
        "total": total,
        "limit": limit,
        "offset": offset,
    }