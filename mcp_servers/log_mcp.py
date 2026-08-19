"""log-mcp - exposes incident/log information to agents (read-only).

Tools:
    search_logs(service, keyword, since, limit) -> recent log lines for a service
        backed by `docker logs <container>` (no filesystem access, no SQL).

The log source is auth-api's stdout via docker logs, matching PLAN.md §3
("log source: auth-api just writes logs to stdout"). A future incidents
database (PLAN §7) can back search_logs later without changing the tool shape.

Run:  python -m mcp_servers.log_mcp
"""

from __future__ import annotations

from mcp_servers.common import ToolError, docker, json_text, make_server, resolve_service

log_mcp = make_server("log-mcp", "Log MCP: read-only access to service logs and events for AegisOps agents.")

MAX_LIMIT = 500


@log_mcp.tool(
    description=(
        "Return recent log lines for a service. Read-only. The only supported service is 'auth-api'. "
        "Optionally filter by keyword and by a docker `--since` value (e.g. '10m' or an RFC3339 timestamp)."
    ),
)
def search_logs(service: str, keyword: str | None = None, since: str | None = None, limit: int = 50) -> str:
    """Fetch recent log lines for `service`.

    Args:
        service: logical service name (allowlist: auth-api)
        keyword: optional substring filter applied to the returned lines
        since: optional docker `--since` value, e.g. "10m" or "2026-08-19T12:00:00Z"
        limit: maximum number of lines to return (1-500)
    """
    container = resolve_service(service)

    if not isinstance(limit, int) or isinstance(limit, bool) or not (1 <= limit <= MAX_LIMIT):
        raise ToolError(f"limit must be an integer between 1 and {MAX_LIMIT}")

    args = ["logs", "--tail", str(limit), "--timestamps", container]
    if since:
        args += ["--since", since]
    proc = docker(*args)
    if proc.returncode != 0:
        raise ToolError(f"docker logs failed for '{service}': {proc.stderr.strip() or proc.stdout.strip()}")

    lines = proc.stdout.splitlines()
    if keyword:
        lines = [line for line in lines if keyword in line]

    return json_text({"service": service, "count": len(lines), "lines": lines})


if __name__ == "__main__":
    log_mcp.run(transport="streamable-http", host="127.0.0.1", port=8081)