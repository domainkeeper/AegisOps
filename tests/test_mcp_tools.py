"""MCP layer tests: transport, tool discovery, tool invocation, real Docker effect.

Real integration (no mocks): each MCP server is spawned as a real subprocess and
spoken to over Streamable HTTP using the official MCP Python SDK client. The
remediation test performs an actual `docker restart auth-api`.

Run from the repository root:  python -m pytest tests/test_mcp_tools.py -v
Requires: a running Docker engine (auth-api is brought up by the environment fixture).
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Iterator

import pytest
from mcp import Client

REPO_ROOT = Path(__file__).resolve().parent.parent
AUTH_API_HEALTH_URL = "http://localhost:8080/health"
AUTH_API_BREAK_URL = "http://localhost:8080/break"


def _wait_for_port(port: int, timeout_s: float = 30.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.3)
    pytest.fail(f"server on port {port} did not become reachable")


def _http(method: str, url: str, timeout: float = 5.0) -> tuple[int, dict]:
    req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as err:  # type: ignore[attr-defined]
        try:
            body = json.loads(err.read().decode())
        except Exception:
            body = {}
        return err.code, body
    except Exception:
        # Connection refused/closed while the app is (re)starting.
        return 0, {}


def _tool_result_text(result) -> dict:
    """Extract the JSON string payload from an MCP CallToolResult text item."""
    for item in result.content:
        if item.type == "text":
            return json.loads(item.text)
    pytest.fail("no text content item in tool result")


@pytest.fixture(scope="module")
def environment():
    """Ensure the auth-api compose stack is up before the MCP tests."""
    subprocess.run(["docker", "compose", "up", "-d", "--build"], cwd=REPO_ROOT, check=True, capture_output=True)
    deadline = time.time() + 30
    while time.time() < deadline:
        status, _ = _http("GET", AUTH_API_HEALTH_URL)
        if status == 200:
            break
        time.sleep(0.5)
    else:
        pytest.fail("auth-api did not become healthy")
    yield


@pytest.fixture()
def spawn_server() -> Iterator[callable]:
    """Fixture factory: spawn a server module on a port, yield a client URL."""

    processes: list[subprocess.Popen] = []

    def _spawn(module: str, port: int) -> str:
        proc = subprocess.Popen(
            [sys.executable, "-m", module],
            cwd=REPO_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        processes.append(proc)
        _wait_for_port(port)
        return f"http://127.0.0.1:{port}/mcp"

    yield _spawn
    for proc in processes:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_log_mcp_exposes_only_search_logs(environment, spawn_server):
    url = spawn_server("mcp_servers.log_mcp", 8081)
    async def run():
        async with Client(url) as client:
            tools = await client.list_tools()
            return [t.name for t in tools.tools]
    import asyncio
    assert asyncio.run(run()) == ["search_logs"]


def test_log_mcp_search_logs_returns_structured_lines(environment, spawn_server):
    url = spawn_server("mcp_servers.log_mcp", 8081)
    import asyncio

    async def run():
        async with Client(url) as client:
            result = await client.call_tool("search_logs", {"service": "auth-api", "limit": 5})
            return result
    result = asyncio.run(run())
    payload = _tool_result_text(result)
    assert payload["service"] == "auth-api"
    assert isinstance(payload["count"], int)
    assert isinstance(payload["lines"], list)
    assert len(payload["lines"]) <= 5


def test_log_mcp_keyword_filter(environment, spawn_server):
    url = spawn_server("mcp_servers.log_mcp", 8081)
    import asyncio

    async def run():
        async with Client(url) as client:
            result = await client.call_tool("search_logs", {"service": "auth-api", "keyword": "xyzzy-not-present", "limit": 10})
            return result
    payload = _tool_result_text(asyncio.run(run()))
    assert payload["count"] == 0


def test_log_mcp_rejects_unknown_service(environment, spawn_server):
    url = spawn_server("mcp_servers.log_mcp", 8081)
    import asyncio

    async def run():
        async with Client(url) as client:
            return await client.call_tool("search_logs", {"service": "postgres"})
    result = asyncio.run(run())
    assert result.is_error


def test_diagnostic_mcp_exposes_only_read_tools(environment, spawn_server):
    url = spawn_server("mcp_servers.diagnostic_mcp", 8082)
    import asyncio

    async def run():
        async with Client(url) as client:
            tools = await client.list_tools()
            return [t.name for t in tools.tools]
    assert asyncio.run(run()) == ["get_service_status", "inspect_service_state"]


def test_diagnostic_get_service_status_healthy(environment, spawn_server):
    url = spawn_server("mcp_servers.diagnostic_mcp", 8082)
    import asyncio

    async def run():
        async with Client(url) as client:
            return await client.call_tool("get_service_status", {"service": "auth-api"})
    payload = _tool_result_text(asyncio.run(run()))
    assert payload["service"] == "auth-api"
    assert payload["http_code"] == 200
    assert payload["status"] == "healthy"


def test_diagnostic_get_service_status_reports_unhealthy_as_data(environment, spawn_server):
    url = spawn_server("mcp_servers.diagnostic_mcp", 8082)
    import asyncio

    async def run():
        async with Client(url) as client:
            return await client.call_tool("get_service_status", {"service": "auth-api"})
    _http("POST", AUTH_API_BREAK_URL)
    try:
        result = asyncio.run(run())
        payload = _tool_result_text(result)
        assert payload["http_code"] == 503
        assert payload["status"] == "unhealthy"
    finally:
        _http("POST", "http://localhost:8080/fix")


def test_diagnostic_inspect_service_state(environment, spawn_server):
    url = spawn_server("mcp_servers.diagnostic_mcp", 8082)
    import asyncio

    async def run():
        async with Client(url) as client:
            return await client.call_tool("inspect_service_state", {"service": "auth-api"})
    payload = _tool_result_text(asyncio.run(run()))
    assert payload["service"] == "auth-api"
    assert payload["running"] is True
    assert payload["started_at"]
    assert "health_status" in payload


def test_diagnostic_rejects_unknown_service(environment, spawn_server):
    url = spawn_server("mcp_servers.diagnostic_mcp", 8082)
    import asyncio

    async def run():
        async with Client(url) as client:
            return await client.call_tool("get_service_status", {"service": "database"})
    result = asyncio.run(run())
    assert result.is_error


def test_remediation_exposes_only_restart_service(environment, spawn_server):
    url = spawn_server("mcp_servers.remediation_mcp", 8083)
    import asyncio

    async def run():
        async with Client(url) as client:
            tools = await client.list_tools()
            return [t.name for t in tools.tools]
    names = asyncio.run(run())
    assert names == ["restart_service"]
    assert not any(n in names for n in ("run_shell", "execute_shell", "bash", "docker_exec", "run_command"))


def test_remediation_real_restart_changes_started_at_and_recovers(environment, spawn_server):
    """The centerpiece: restart_service() must perform a REAL docker restart."""
    url = spawn_server("mcp_servers.remediation_mcp", 8083)
    import asyncio

    started_before = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.StartedAt}}", "auth-api"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    _http("POST", AUTH_API_BREAK_URL)
    status, _ = _http("GET", AUTH_API_HEALTH_URL)
    assert status == 503, "auth-api should be broken before the restart"

    async def run():
        async with Client(url) as client:
            return await client.call_tool("restart_service", {"service_name": "auth-api"})

    result = asyncio.run(run())
    assert not result.is_error, result
    payload = _tool_result_text(result)

    assert payload["service"] == "auth-api"
    assert payload["operation"] == "restart_service"
    assert payload["success"] is True
    assert payload["started_at"] != started_before, "container start time did not change - not a real restart"
    assert payload["health"]["http_code"] == 200
    assert payload["health"]["status"] == "healthy"


def test_remediation_rejects_unknown_and_malicious_service_names(environment, spawn_server):
    url = spawn_server("mcp_servers.remediation_mcp", 8083)
    import asyncio

    async def run():
        async with Client(url) as client:
            results = []
            for name in ("postgres", "auth-api; rm -rf /", "auth-api --help", ""):
                results.append(await client.call_tool("restart_service", {"service_name": name}))
            return results
    for result in asyncio.run(run()):
        assert result.is_error, "unknown/malicious service names must be rejected"

    status, _ = _http("GET", AUTH_API_HEALTH_URL)
    assert status == 200, "auth-api must be untouched after rejected calls"


def test_remediation_rejects_missing_required_param(environment, spawn_server):
    url = spawn_server("mcp_servers.remediation_mcp", 8083)
    import asyncio

    async def run():
        async with Client(url) as client:
            return await client.call_tool("restart_service", {})
    result = asyncio.run(run())
    assert result.is_error


# ---------------------------------------------------------------------------
# Hostile-input hardening (final engineering pass)
# ---------------------------------------------------------------------------


def test_log_mcp_hostile_since_never_shells_out(environment, spawn_server):
    """A hostile `since` value is passed to docker as a FIXED argument (no shell),
    never executed. The server either rejects it cleanly or returns valid lines -
    and auth-api is untouched either way."""
    url = spawn_server("mcp_servers.log_mcp", 8081)
    import asyncio

    async def run():
        async with Client(url) as client:
            results = []
            for since in ("not-a-real-time; rm -rf /", "2026-01-01T00:00:00Z --follow", "`id`"):
                results.append(await client.call_tool(
                    "search_logs", {"service": "auth-api", "since": since, "limit": 5}
                ))
            return results
    results = asyncio.run(run())
    for result in results:
        assert result.is_error or _tool_result_text(result)["service"] == "auth-api"
    status, _ = _http("GET", AUTH_API_HEALTH_URL)
    assert status == 200, "auth-api must be untouched by hostile since values"


def test_log_mcp_rejects_non_string_service(environment, spawn_server):
    url = spawn_server("mcp_servers.log_mcp", 8081)
    import asyncio

    async def run():
        async with Client(url) as client:
            results = []
            for bad in (123, ["auth-api"], {"service": "auth-api"}, None, True):
                results.append(await client.call_tool("search_logs", {"service": bad}))
            return results
    for result in asyncio.run(run()):
        assert result.is_error, "non-string service values must be rejected"


def test_diagnostic_rejects_non_string_service(environment, spawn_server):
    url = spawn_server("mcp_servers.diagnostic_mcp", 8082)
    import asyncio

    async def run():
        async with Client(url) as client:
            results = []
            for bad in (0, ["auth-api"], True):
                results.append(await client.call_tool("get_service_status", {"service": bad}))
            return results
    for result in asyncio.run(run()):
        assert result.is_error


def test_log_mcp_rejects_huge_limit(environment, spawn_server):
    url = spawn_server("mcp_servers.log_mcp", 8081)
    import asyncio

    async def run():
        async with Client(url) as client:
            return await client.call_tool(
                "search_logs", {"service": "auth-api", "limit": 99999}
            )
    result = asyncio.run(run())
    assert result.is_error, "limits above the documented cap must be rejected"


def test_remediation_rejects_list_service_name(environment, spawn_server):
    """The restart capability must never accept a container list / compound value."""
    url = spawn_server("mcp_servers.remediation_mcp", 8083)
    import asyncio

    async def run():
        async with Client(url) as client:
            results = []
            for bad in (["auth-api"], {"service": "auth-api"}, 8080, None):
                results.append(await client.call_tool("restart_service", {"service_name": bad}))
            return results
    for result in asyncio.run(run()):
        assert result.is_error
    status, _ = _http("GET", AUTH_API_HEALTH_URL)
    assert status == 200, "auth-api must be untouched after rejected hostile calls"
