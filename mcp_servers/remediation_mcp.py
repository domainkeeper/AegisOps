"""remediation-mcp - the security-sensitive write MCP.

Tool:
    restart_service(service_name) -> a REAL `docker restart <container>` for a
        service on the explicit allowlist (currently only "auth-api"), then
        polls /health until the service recovers.

This server is single-purpose by design: there is NO run_shell, NO docker_exec,
NO generic command tool anywhere in the MCP layer. The service name is resolved
through the SERVICES allowlist map only (mcp_servers.common), never interpolated
into a shell string. The future ArmorIQ boundary decides WHICH agent may invoke
this capability; this file decides WHAT the capability can do.

Run:  python -m mcp_servers.remediation_mcp
"""

from __future__ import annotations

from mcp_servers.common import (
    ToolError,
    container_started_at,
    docker,
    get_health,
    json_text,
    make_server,
    resolve_service,
    wait_for_healthy,
)

remediation_mcp = make_server(
    "remediation-mcp",
    "Remediation MCP: restart a service on the explicit allowlist (auth-api).",
)


@remediation_mcp.tool(
    description=(
        "Restart a service for real (docker restart) and wait until it reports healthy. "
        "Only services on the explicit allowlist are accepted; anything else is rejected."
    ),
)
def restart_service(service_name: str) -> str:
    """Restart `service_name` and verify recovery.

    Args:
        service_name: logical service name (allowlist: auth-api)
    """
    container = resolve_service(service_name)

    started_at_before = container_started_at(container)
    proc = docker("restart", container)
    if proc.returncode != 0:
        raise ToolError(f"docker restart failed for '{service_name}': {proc.stderr.strip() or proc.stdout.strip()}")

    started_at_after = container_started_at(container)
    if not wait_for_healthy():
        raise ToolError(
            f"container '{container}' was restarted but auth-api did not recover within the health window"
        )

    return json_text(
        {
            "service": service_name,
            "operation": "restart_service",
            "success": True,
            "container": container,
            "started_at_before": started_at_before,
            "started_at": started_at_after,
            "health": get_health(),
        }
    )


if __name__ == "__main__":
    remediation_mcp.run(transport="streamable-http", host="127.0.0.1", port=8083)