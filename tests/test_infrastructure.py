"""Infrastructure tests: auth-api health / break / real-restart lifecycle.

Requires a running Docker engine. Uses the stdlib only (urllib + subprocess)
so the test suite has no extra dependencies.

Run from the repository root:  python -m pytest tests/test_infrastructure.py -v
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTAINER = "auth-api"
HEALTH_URL = "http://localhost:8080/health"
BREAK_URL = "http://localhost:8080/break"
FIX_URL = "http://localhost:8080/fix"
TIMEOUT_S = 30


def _http(method: str, url: str, timeout: float = 5.0) -> tuple[int, dict]:
    req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as err:
        try:
            body = json.loads(err.read().decode())
        except Exception:
            body = {}
        return err.code, body
    except urllib.error.URLError:
        # Connection refused / closed while the app is (re)starting.
        return 0, {}
    except Exception:
        # http.client.RemoteDisconnected and similar escape urllib's wrapping.
        return 0, {}


def _wait_health(expected_status: int, timeout: float = TIMEOUT_S) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status, _ = _http("GET", HEALTH_URL)
        if status == expected_status:
            return True
        time.sleep(0.5)
    return False


def _docker(*args: str) -> str:
    return subprocess.run(
        ["docker", *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _container_started_at() -> str:
    return _docker("inspect", "--format", "{{.State.StartedAt}}", CONTAINER)


@pytest.fixture(scope="module")
def environment():
    """Ensure the compose stack is up and healthy; tear it down afterwards."""
    subprocess.run(
        ["docker", "compose", "up", "-d", "--build"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    assert _wait_health(200), "auth-api did not become healthy"
    yield
    subprocess.run(["docker", "compose", "down"], cwd=REPO_ROOT, check=True, capture_output=True)


@pytest.fixture()
def healthy(environment):
    """Restore a healthy state before each test."""
    _http("POST", FIX_URL)
    if not _wait_health(200):
        _docker("restart", CONTAINER)
        assert _wait_health(200), "could not restore healthy state"
    yield
    _http("POST", FIX_URL)
    _wait_health(200)


def test_container_running(environment):
    assert _docker("inspect", "--format", "{{.State.Running}}", CONTAINER) == "true"


def test_health_initial_is_healthy(healthy):
    status, body = _http("GET", HEALTH_URL)
    assert status == 200
    assert body["status"] == "healthy"


def test_break_makes_health_unhealthy(healthy):
    status, body = _http("POST", BREAK_URL)
    assert status == 200
    assert body["status"] == "broken"
    assert _wait_health(503), "/health did not become unhealthy after /break"
    status, body = _http("GET", HEALTH_URL)
    assert status == 503
    assert body["status"] == "unhealthy"


def test_restart_recovers_and_is_a_real_restart(healthy):
    started_at_before = _container_started_at()

    _http("POST", BREAK_URL)
    assert _wait_health(503), "/health did not become unhealthy after /break"

    _docker("restart", CONTAINER)
    started_at_after = _container_started_at()
    assert started_at_before != started_at_after, (
        "container start time did not change - the 'restart' was not a real restart"
    )

    assert _wait_health(200), "auth-api did not recover after container restart"
    status, body = _http("GET", HEALTH_URL)
    assert status == 200
    assert body["status"] == "healthy"


def test_fix_restores_application_state(healthy):
    _http("POST", BREAK_URL)
    assert _wait_health(503)
    status, body = _http("POST", FIX_URL)
    assert status == 200
    assert body["status"] == "fixed"
    assert _wait_health(200), "/health did not recover after /fix"