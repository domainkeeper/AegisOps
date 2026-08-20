"""SQLite audit mirror - a thin local application mirror (Phase 7).

Mirrors only SAFE metadata from the ArmorIQ path: who did what, when, and with
what outcome. It is NOT a copy of the ArmorIQ audit system - ArmorIQ remains the
source of truth for authorization decisions.

NEVER stored here (enforced by the API surface and asserted by tests):
- API keys, private keys, raw intent tokens, delegated tokens, signatures

Schema (matching ARCHITECTURE.md §10):
    audit_events(id PK, incident_id, agent, parent_agent, action, status,
                 delegation_id, error_type, detail, created_at)

Thread-safety: one sqlite connection per process behind a lock; agents are
single-process uvicorn servers. Writes are best-effort - an audit failure is
logged and must never break the incident flow.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = PROJECT_ROOT / "database" / "audit.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id   TEXT,
    agent         TEXT,
    parent_agent  TEXT,
    action        TEXT,
    status        TEXT,
    delegation_id TEXT,
    error_type    TEXT,
    detail        TEXT,
    created_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_incident ON audit_events(incident_id);
CREATE INDEX IF NOT EXISTS idx_audit_created  ON audit_events(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_delegation ON audit_events(delegation_id);
"""

_FORBIDDEN_FIELDS = ("token", "raw_token", "jwt_token", "signature", "api_key", "private_key", "secret")


def _looks_like_secret(value: object) -> bool:
    """Exact forbidden field names, or values that carry a secret assignment."""
    if not isinstance(value, str):
        return False
    if value in _FORBIDDEN_FIELDS:
        return True
    lowered = value.lower()
    return any(
        marker in lowered
        for marker in ("token=", "raw_token=", "jwt_token=", "api_key=",
                       "private_key=", "signature=", "secret=")
    )


class AuditStore:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path or os.environ.get("AEGISOPS_AUDIT_DB") or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def record(
        self,
        *,
        incident_id: str | None,
        agent: str | None,
        action: str | None,
        status: str,
        parent_agent: str | None = None,
        delegation_id: str | None = None,
        error_type: str | None = None,
        detail: str | None = None,
    ) -> None:
        """Insert one audit row. Safe metadata only - never tokens/keys."""
        values = {
            "incident_id": incident_id,
            "agent": agent,
            "parent_agent": parent_agent,
            "action": action,
            "status": status,
            "delegation_id": delegation_id,
            "error_type": error_type,
            "detail": detail,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        if any(_looks_like_secret(v) for v in values.values()):
            raise ValueError("audit record attempted to store a forbidden field")
        with self._lock:
            self._conn.execute(
                "INSERT INTO audit_events (incident_id, agent, parent_agent, action, status, "
                "delegation_id, error_type, detail, created_at) "
                "VALUES (:incident_id, :agent, :parent_agent, :action, :status, "
                ":delegation_id, :error_type, :detail, :created_at)",
                values,
            )
            self._conn.commit()

    def recent(self, limit: int = 50) -> list[dict]:
        """Most recent rows (used by tests and the trail viewer later)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT incident_id, agent, parent_agent, action, status, delegation_id, "
                "error_type, detail, created_at FROM audit_events "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        cols = ["incident_id", "agent", "parent_agent", "action", "status",
                "delegation_id", "error_type", "detail", "created_at"]
        return [dict(zip(cols, row)) for row in rows]

    def by_incident(self, incident_id: str, limit: int = 200) -> list[dict]:
        """All audit rows for one incident, oldest first (indexed by incident_id)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT incident_id, agent, parent_agent, action, status, delegation_id, "
                "error_type, detail, created_at FROM audit_events "
                "WHERE incident_id = ? ORDER BY id ASC LIMIT ?",
                (incident_id, limit),
            ).fetchall()
        cols = ["incident_id", "agent", "parent_agent", "action", "status",
                "delegation_id", "error_type", "detail", "created_at"]
        return [dict(zip(cols, row)) for row in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


_store: AuditStore | None = None
_store_lock = threading.Lock()


def get_store() -> AuditStore:
    """Process-wide audit store (lazy). Override the DB via AEGISOPS_AUDIT_DB."""
    global _store
    with _store_lock:
        if _store is None:
            _store = AuditStore()
        return _store


def audit(
    *,
    incident_id: str | None,
    agent: str,
    action: str | None,
    status: str,
    parent_agent: str | None = None,
    delegation_id: str | None = None,
    error_type: str | None = None,
    detail: str | None = None,
) -> None:
    """Best-effort audit write. Never raises into the incident flow."""
    try:
        get_store().record(
            incident_id=incident_id,
            agent=agent,
            parent_agent=parent_agent,
            action=action,
            status=status,
            delegation_id=delegation_id,
            error_type=error_type,
            detail=detail,
        )
    except Exception as exc:  # noqa: BLE001 - audit must not break the flow
        logging.getLogger("aegisops.audit").warning("audit write failed: %s", exc)


__all__ = ["AuditStore", "get_store", "audit", "DEFAULT_DB", "SCHEMA"]