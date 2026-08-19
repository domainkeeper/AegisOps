"""Minimal MCP spike - proves the transport before the three real servers.

Serves ONE harmless read-only tool (`health_check`) over the exact transport
the full MCP layer uses (official MCP Python SDK, Streamable HTTP + SSE), so a
new SDK/protocol version can be re-verified against this file before touching
the real servers. Verified working in Phase 3 (2026-08-19).

Run:  python -m mcp_servers.spike
"""

from __future__ import annotations

from mcp_servers.common import get_health, make_server, resolve_service

spike = make_server("spike-mcp", "Minimal MCP spike: proves the MCP transport with one read-only tool.")


@spike.tool(
    description="Return the current health state of a service (read-only).",
)
def health_check(service: str) -> str:
    """Check the real health state of `service` (currently only auth-api exists).

    Args:
        service: logical service name, e.g. "auth-api"
    """
    resolve_service(service)
    from mcp_servers.common import json_text

    return json_text(get_health())


if __name__ == "__main__":
    spike.run(transport="streamable-http", host="127.0.0.1", port=8090)