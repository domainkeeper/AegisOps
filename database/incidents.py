"""Persistent incident storage backed by SQLite.

Schema mirrors the Incident model from agents/common.py. Designed to be
swapped for a PostgreSQL implementation via the IncidentRepository ABC.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from database.repository import IncidentRepository

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = PROJECT_ROOT / "database" / "aegisops.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    id                  TEXT PRIMARY KEY,
    service             TEXT NOT NULL,
    status              TEXT NOT NULL,
    severity            TEXT NOT NULL,
    description         TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    resolved_at         TEXT,
    summary             TEXT,
    diagnosis           TEXT,
    recommended_action  TEXT,
    resolution          TEXT,
    intent_token_status TEXT DEFAULT 'not_configured',
    governed            INTEGER DEFAULT 0,
    error               TEXT
);
"""


@dataclass
class IncidentRecord:
    id: str
    service: str
    status: str
    severity: str = "medium"
    description: str = ""
    created_at: str = ""
    updated_at: str = ""
    resolved_at: str | None = None
    summary: str = ""
    diagnosis: str = ""
    recommended_action: str = ""
    resolution: str = ""
    intent_token_status: str = "not_configured"
    governed: bool = False
    error: str | None = None


class IncidentStore(IncidentRepository):
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(
            db_path or os.environ.get("AEGISOPS_DATABASE_URL") or DEFAULT_DB
        )
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def save(self, incident: IncidentRecord) -> None:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self._lock:
            self._conn.execute(
                "INSERT INTO incidents "
                "(id, service, status, severity, description, created_at, updated_at, "
                "resolved_at, summary, diagnosis, recommended_action, resolution, "
                "intent_token_status, governed, error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET "
                "service=excluded.service, status=excluded.status, "
                "severity=excluded.severity, description=excluded.description, "
                "updated_at=excluded.updated_at, resolved_at=excluded.resolved_at, "
                "summary=excluded.summary, diagnosis=excluded.diagnosis, "
                "recommended_action=excluded.recommended_action, "
                "resolution=excluded.resolution, "
                "intent_token_status=excluded.intent_token_status, "
                "governed=excluded.governed, error=excluded.error",
                (
                    incident.id,
                    incident.service,
                    incident.status,
                    incident.severity,
                    incident.description,
                    incident.created_at or now,
                    now,
                    incident.resolved_at,
                    incident.summary,
                    incident.diagnosis,
                    incident.recommended_action,
                    incident.resolution,
                    incident.intent_token_status,
                    int(incident.governed),
                    incident.error,
                ),
            )
            self._conn.commit()

    def get(self, incident_id: str) -> IncidentRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM incidents WHERE id = ?", (incident_id,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def list(
        self,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> list[IncidentRecord]:
        with self._lock:
            if status:
                rows = self._conn.execute(
                    "SELECT * FROM incidents WHERE status = ? "
                    "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (status, limit, offset),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM incidents ORDER BY created_at DESC "
                    "LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def count(self, status: str | None = None) -> int:
        with self._lock:
            if status:
                row = self._conn.execute(
                    "SELECT COUNT(*) FROM incidents WHERE status = ?", (status,)
                ).fetchone()
            else:
                row = self._conn.execute(
                    "SELECT COUNT(*) FROM incidents"
                ).fetchone()
        return row[0]

    def update_status(
        self,
        incident_id: str,
        status: str,
        error: str | None = None,
    ) -> None:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self._lock:
            self._conn.execute(
                "UPDATE incidents SET status = ?, updated_at = ?, error = ? "
                "WHERE id = ?",
                (status, now, error, incident_id),
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> IncidentRecord:
        return IncidentRecord(
            id=row["id"],
            service=row["service"],
            status=row["status"],
            severity=row["severity"],
            description=row["description"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            resolved_at=row["resolved_at"],
            summary=row["summary"] or "",
            diagnosis=row["diagnosis"] or "",
            recommended_action=row["recommended_action"] or "",
            resolution=row["resolution"] or "",
            intent_token_status=row["intent_token_status"] or "not_configured",
            governed=bool(row["governed"]),
            error=row["error"],
        )


__all__ = ["IncidentRecord", "IncidentStore", "SCHEMA", "DEFAULT_DB"]