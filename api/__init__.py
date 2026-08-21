"""AegisOps API layer - production-facing REST gateway.

The frontend talks ONLY to this API. The API reads from the database, proxies
to agent processes, and exposes safe system status. It NEVER exposes secrets,
never executes arbitrary commands, and never decides authorization.
"""

from __future__ import annotations

__all__: list[str] = []