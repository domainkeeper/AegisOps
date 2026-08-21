"""Abstract repository interfaces for incident storage.

Defines repository contracts so the SQLite implementations can be swapped
for PostgreSQL (or other backends) without changing callers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IncidentRepository(ABC):
    @abstractmethod
    def save(self, incident: Any) -> None: ...

    @abstractmethod
    def get(self, incident_id: str) -> Any | None: ...

    @abstractmethod
    def list(
        self, limit: int = 50, offset: int = 0, status: str | None = None
    ) -> list: ...

    @abstractmethod
    def count(self, status: str | None = None) -> int: ...

    @abstractmethod
    def update_status(
        self, incident_id: str, status: str, error: str | None = None
    ) -> None: ...


class EventRepository(ABC):
    @abstractmethod
    def append(
        self,
        incident_id: str,
        ts: float,
        stage: str,
        status: str,
        detail: str = "",
    ) -> None: ...

    @abstractmethod
    def by_incident(self, incident_id: str, limit: int = 200) -> list: ...


__all__ = ["IncidentRepository", "EventRepository"]