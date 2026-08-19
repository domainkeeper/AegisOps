"""Minimal spike verification: transport, wire format, and tool round-trip.

The spike (mcp_servers/spike.py) is deliberately the only file re-verified here,
so an SDK/protocol upgrade can be validated against it before the real servers.
Requires auth-api (localhost:8080) to be up.

Run from the repository root:  python -m pytest tests/test_mcp_spike.py -v
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from mcp import Client

REPO_ROOT = Path(__file__).resolve().parent.parent
SPIKE_URL = "http://127.0.0.1:8090/mcp"
AUTH_API_HEALTH_URL = "http://localhost:8080/health"


@pytest.fixture(scope="module")
def environment():
    """Ensure auth-api is up (the infrastructure test module tears compose down)."""
    subprocess.run(["docker", "compose", "up", "-d"], cwd=REPO_ROOT, check=True, capture_output=True)
    import urllib.error

    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(AUTH_API_HEALTH_URL, timeout=3) as resp:
                if resp.status == 200:
                    break
        except Exception:
            pass
        time.sleep(0.5)
    else:
        pytest.fail("auth-api did not become healthy")
    yield


@pytest.fixture(scope="module")
def spike_server(environment):
    proc = subprocess.Popen(
        [sys.executable, "-m", "mcp_servers.spike"],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 30
    while time.time() < deadline:
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", 8090)) == 0:
                break
        time.sleep(0.3)
    else:
        pytest.fail("spike server did not start")
    yield
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_wire_format_is_armoriq_compatible_sse(spike_server):
    """Raw HTTP check: POST /mcp answers text/event-stream with event: message - the
    exact format the ArmorIQ proxy requires (JSON-RPC 2.0 over HTTP, SSE responses)."""
    import json

    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "probe", "version": "0"}},
        }
    ).encode()
    req = urllib.request.Request(
        SPIKE_URL,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        content_type = resp.headers.get("Content-Type", "")
        payload = resp.read().decode()

    assert "text/event-stream" in content_type
    assert "event: message" in payload
    assert '"jsonrpc":"2.0"' in payload
    assert '"result"' in payload


def test_initialize_and_tool_discovery(spike_server):
    async def run():
        async with Client(SPIKE_URL) as client:
            tools = await client.list_tools()
            return [t.name for t in tools.tools], client.server_info

    import asyncio

    names, server_info = asyncio.run(run())
    assert names == ["health_check"]
    assert server_info.name == "spike-mcp"


def test_health_check_returns_real_auth_api_state(spike_server):
    async def run():
        async with Client(SPIKE_URL) as client:
            return await client.call_tool("health_check", {"service": "auth-api"})

    import asyncio
    import json

    result = asyncio.run(run())
    assert not result.is_error
    for item in result.content:
        if item.type == "text":
            payload = json.loads(item.text)
            assert payload["service"] == "auth-api"
            assert payload["http_code"] == 200
            assert payload["status"] == "healthy"
            return
    pytest.fail("no text content item in result")


def test_unknown_service_is_rejected(spike_server):
    async def run():
        async with Client(SPIKE_URL) as client:
            return await client.call_tool("health_check", {"service": "postgres"})

    import asyncio

    result = asyncio.run(run())
    assert result.is_error
