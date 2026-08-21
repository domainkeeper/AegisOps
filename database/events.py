"""Timeline event storage for incidents, backed by SQLite.

Each row represents one state transition in an incident's lifecycle.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from database.repository import EventRepository

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = PROJECT_ROOT / "database" / "aegisops.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS incident_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id TEXT NOT NULL,
    ts          REAL NOT NULL,
    stage       TEXT NOT NULL,
    status      TEXT NOT NULL,
    detail      TEXT DEFAULT '',
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_incident ON incident_events(incident_id);
CREATE INDEX IF NOT EXISTS idx_events_created  ON incident_events(created_at);
"""


class EventStore(EventRepository):
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(
            db_path or os.environ.get("AEGISOPS_DATABASE_URL") or DEFAULT_DB
        )
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def append(
        self,
        incident_id: str,
        ts: float,
        stage: str,
        status: str,
        detail: str = "",
    ) -> None:
        created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self._lock:
            self._conn.execute(
                "INSERT INTO incident_events (incident_id, ts, stage, status, detail, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (incident_id, ts, stage, status, detail, created_at),
            )
            self._conn.commit()

    def by_incident(
        self, incident_id: str, limit: int = 200
    ) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, incident_id, ts, stage, status, detail, created_at "
                "FROM incident_events "
                "WHERE incident_id = ? ORDER BY id ASC LIMIT ?",
                (incident_id, limit),
            ).fetchall()
        cols = ["id", "incident_id", "ts", "stage", "status", "detail", "created_at"]
        return [dict(zip(cols, row)) for row in rows]

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, incident_id, ts, stage, status, detail, created_at "
                "FROM incident_events "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        cols = ["id", "incident_id", "ts", "stage", "status", "detail", "created_at"]
        return [dict(zip(cols, row)) for row in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["EventStore", "SCHEMA", "DEFAULT_DB"]