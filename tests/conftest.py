"""Shared pytest fixtures and helpers for the AegisOps agent tests.

Hermetic-by-default: the agent LLM path is forced to the explicitly-marked
deterministic TEST fallback unless a specific test re-enables credentials.
Real components only - Docker compose for auth-api, real MCP subprocesses, real
agent subprocesses, real HTTP. No mocks.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Keep the suite deterministic: tests never hit a real LLM endpoint unless a
# specific test explicitly injects credentials via monkeypatch.
os.environ["AEGISOPS_GEMINI_API_KEY"] = ""
os.environ["AEGISOPS_LLM_FALLBACK"] = "test"

# Keep the ArmorIQ intent-token handshake offline/hermetic: the Commander
# records intent_token_status="not_configured" unless a test injects a key.
os.environ["ARMORIQ_API_KEY"] = ""

PROCESSES: list[subprocess.Popen] = []

AUTH_API_HEALTH_URL = "http://localhost:8080/health"
AUTH_API_BREAK_URL = "http://localhost:8080/break"
AUTH_API_FIX_URL = "http://localhost:8080/fix"


def wait_for_port(port: int, timeout_s: float = 40.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.3)
    pytest.fail(f"port {port} never became reachable")


def http(method: str, url: str, timeout: float = 30.0, json_body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(json_body).encode() if json_body is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(url, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as err:  # type: ignore[attr-defined]
        try:
            body = json.loads(err.read().decode())
        except Exception:
            body = {}
        return err.code, body
    except Exception:
        return 0, {}


def spawn_module(module: str, port: int) -> subprocess.Popen:
    """Spawn a module as a real subprocess and wait for its port to open."""
    env = dict(os.environ)
    env["AEGISOPS_AGENT_PORT"] = str(port)  # agents bind this port when started as a process
    proc = subprocess.Popen(
        [sys.executable, "-m", module],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    PROCESSES.append(proc)
    wait_for_port(port)
    return proc


def container_started_at() -> str:
    return subprocess.run(
        ["docker", "inspect", "--format", "{{.State.StartedAt}}", "auth-api"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _ensure_mcp(module: str, port: int, url: str) -> None:
    probe = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "probe", "version": "0"},
            },
        }
    )
    try:
        req = urllib.request.Request(
            url, method="POST", data=probe.encode(),
            headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
        )
        with urllib.request.urlopen(req, timeout=3):
            return  # already running
    except Exception:
        spawn_module(module, port)


def _ensure_agent(module: str, port: int) -> None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2):
            return  # already running
    except Exception:
        spawn_module(module, port)


@pytest.fixture(scope="session", autouse=True)
def _cleanup_processes():
    yield
    for proc in PROCESSES:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


@pytest.fixture(scope="module")
def environment():
    """Ensure the auth-api compose stack is up and healthy."""
    subprocess.run(["docker", "compose", "up", "-d"], cwd=REPO_ROOT, check=True, capture_output=True)
    deadline = time.time() + 30
    while time.time() < deadline:
        status, _ = http("GET", AUTH_API_HEALTH_URL)
        if status == 200:
            break
        time.sleep(0.5)
    else:
        pytest.fail("auth-api did not become healthy")
    yield


@pytest.fixture(scope="module")
def mcp_layer(environment):
    """Ensure the three MCP servers are running (spawns them if not)."""
    _ensure_mcp("mcp_servers.log_mcp", 8081, "http://127.0.0.1:8081/mcp")
    _ensure_mcp("mcp_servers.diagnostic_mcp", 8082, "http://127.0.0.1:8082/mcp")
    _ensure_mcp("mcp_servers.remediation_mcp", 8083, "http://127.0.0.1:8083/mcp")
    yield


@pytest.fixture(scope="module")
def agents_layer(mcp_layer):
    """Ensure the four agent processes are running (spawns them if not)."""
    _ensure_agent("agents.log_agent", 8091)
    _ensure_agent("agents.diagnosis_agent", 8092)
    _ensure_agent("agents.remediation_agent", 8093)
    _ensure_agent("agents.commander", 8094)
    yield


@pytest.fixture()
def broken_auth_api():
    """Break auth-api and wait until /health reports 503, then restore on teardown."""
    http("POST", AUTH_API_BREAK_URL)
    deadline = time.time() + 30
    while time.time() < deadline:
        status, _ = http("GET", AUTH_API_HEALTH_URL)
        if status == 503:
            break
        time.sleep(0.5)
    else:
        pytest.fail("auth-api did not go unhealthy")
    yield
    http("POST", AUTH_API_FIX_URL)