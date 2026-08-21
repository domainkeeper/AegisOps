"""Database package - local application storage.

Phase 7: `audit` - a thin SQLite mirror of ArmorIQ results (safe metadata only).
Phase 8: `incidents` + `events` - persistent incident and timeline storage.

Authorization truth lives in ArmorIQ; SQLite never stores tokens or keys.
"""

from __future__ import annotations

from database.audit import AuditStore, audit, get_store
from database.events import EventStore
from database.incidents import IncidentRecord, IncidentStore

__all__ = [
    "AuditStore",
    "audit",
    "get_store",
    "IncidentRecord",
    "IncidentStore",
    "EventStore",
]