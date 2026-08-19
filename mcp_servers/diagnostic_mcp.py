"""diagnostic-mcp - read-only investigation tools for the Diagnosis Agent.

Tools:
    get_service_status(service)    -> live /health state of a service
    inspect_service_state(service) -> container state (running, started_at,
                                      restart_count, health) from docker inspect

STRICTLY read-only: nothing here can modify or restart a service. The future
security demonstration depends on this boundary (PLAN §1, ARCHITECTURE §4.3).

Run:  python -m mcp_servers.diagnostic_mcp
"""

from __future__ import annotations

import json

from mcp_servers.common import ToolError, docker, get_health, json_text, make_server, resolve_service

diagnostic_mcp = make_server(
    "diagnostic-mcp",
    "Diagnostic MCP: read-only service status and state inspection for AegisOps agents.",
)


@diagnostic_mcp.tool(
    description=(
        "Return the live health status of a service (read-only). "
        "Reports unhealthy state as data - it never modifies the service."
    ),
)
def get_service_status(service: str) -> str:
    """Check the current health of `service`.

    Args:
        service: logical service name (allowlist: auth-api)
    """
    resolve_service(service)
    return json_text(get_health())


@diagnostic_mcp.tool(
    description=(
        "Return container state for a service: running, started_at, restart_count, "
        "health, image (read-only). Secret-bearing fields (env, config) are NOT included."
    ),
)
def inspect_service_state(service: str) -> str:
    """Inspect the runtime state of `service`'s container.

    Args:
        service: logical service name (allowlist: auth-api)
    """
    container = resolve_service(service)
    proc = docker("inspect", container)
    if proc.returncode != 0:
        raise ToolError(f"docker inspect failed for '{service}': {proc.stderr.strip() or proc.stdout.strip()}")

    try:
        info = json.loads(proc.stdout)[0]
    except (json.JSONDecodeError, IndexError, KeyError) as exc:
        raise ToolError(f"could not parse docker inspect output for '{service}': {exc}") from exc

    state = info.get("State", {})
    health = state.get("Health") or {}
    return json_text(
        {
            "service": service,
            "running": bool(state.get("Running")),
            "started_at": state.get("StartedAt"),
            "restart_count": state.get("RestartCount"),
            "health_status": health.get("Status") if health else "none",
            "image": info.get("Config", {}).get("Image"),
        }
    )


if __name__ == "__main__":
    diagnostic_mcp.run(transport="streamable-http", host="127.0.0.1", port=8082)