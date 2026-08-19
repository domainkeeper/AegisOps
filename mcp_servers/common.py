"""Shared helpers for the AegisOps MCP layer.

The MCP layer exposes *capabilities*, not shell access. Each server registers
narrowly scoped tools that map to the real infrastructure (Docker + auth-api).
Authorization of *who* may call a tool is deliberately NOT implemented here;
that boundary belongs to ArmorIQ in later phases (ARCHITECTURE.md §7).
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request

from mcp.server.mcpserver import MCPServer

AUTH_API_HEALTH_URL = "http://localhost:8080/health"

# Explicit allowlist: logical service name -> Docker container name.
# This is the ONLY set of services any MCP tool may act on. No dynamic names,
# no shell interpolation - a service name is resolved through this map only.
SERVICES: dict[str, str] = {
    "auth-api": "auth-api",
}

HEALTH_POLL_TIMEOUT_S = 30.0
DOCKER_TIMEOUT_S = 30.0

SERVICE_NAMES = ", ".join(sorted(SERVICES))


class ToolError(Exception):
    """A tool-level failure that should surface as a structured MCP error."""


def make_server(name: str, description: str) -> MCPServer:
    return MCPServer(name, description=description, version="0.3.0")


def resolve_service(service_name: str) -> str:
    """Return the Docker container name for a logical service name.

    Raises ToolError for anything not on the explicit allowlist.
    """
    if not isinstance(service_name, str) or not service_name.strip():
        raise ToolError(f"service_name must be a non-empty string; expected one of: {SERVICE_NAMES}")
    container = SERVICES.get(service_name.strip())
    if container is None:
        raise ToolError(f"unknown service '{service_name}'; allowed: {SERVICE_NAMES}")
    return container


def fetch_json(url: str, timeout: float = 5.0) -> tuple[int, dict]:
    """HTTP GET -> (status_code, parsed JSON). Connection failures surface as ToolError."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as err:
        try:
            body = json.loads(err.read().decode())
        except Exception:
            body = {}
        return err.code, body
    except Exception as exc:
        raise ToolError(f"could not reach {url}: {exc}") from exc


def get_health(timeout: float = 5.0) -> dict:
    """Current auth-api health: {"service", "http_code", "status", "uptime_seconds"}."""
    code, body = fetch_json(AUTH_API_HEALTH_URL, timeout)
    return {
        "service": "auth-api",
        "http_code": code,
        "status": body.get("status"),
        "uptime_seconds": body.get("uptime_seconds"),
    }


def docker(*args: str, timeout: float = DOCKER_TIMEOUT_S) -> subprocess.CompletedProcess:
    """Run a docker command with a FIXED argument list. Never shell=True."""
    try:
        return subprocess.run(
            ["docker", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ToolError(f"docker {' '.join(args)} timed out after {timeout}s") from exc
    except FileNotFoundError as exc:
        raise ToolError("docker CLI not available on this host") from exc


def wait_for_healthy(timeout_s: float = HEALTH_POLL_TIMEOUT_S) -> bool:
    """Poll auth-api /health until it returns 200. True on recovery."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            code, _ = fetch_json(AUTH_API_HEALTH_URL, timeout=3.0)
            if code == 200:
                return True
        except ToolError:
            pass
        time.sleep(0.5)
    return False


def container_started_at(container: str) -> str | None:
    """Current .State.StartedAt of a container, or None if it cannot be read."""
    proc = docker("inspect", "--format", "{{.State.StartedAt}}", container)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def json_text(payload: dict) -> str:
    """Serialize a tool result payload to the JSON string MCP expects."""
    return json.dumps(payload, default=str)