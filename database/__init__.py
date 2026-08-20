"""Database package - local application storage.

Phase 7: `audit` - a thin SQLite mirror of ArmorIQ results (safe metadata only).
Authorization truth lives in ArmorIQ; SQLite never stores tokens or keys.
"""

from __future__ import annotations

from database.audit import AuditStore, audit, get_store

__all__ = ["AuditStore", "audit", "get_store"]