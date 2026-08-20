#!/usr/bin/env python
"""AegisOps preflight - human-readable readiness report (local + live).

Checks, in order:
  [local]   Python venv present
  [local]   .env present (warn if missing)
  [local]   ARMORIQ_API_KEY set + well-formed (value never printed)
  [local]   AEGISOPS_GEMINI_API_KEY set (informational)
  [local]   agent identity keypairs exist under .keys/ (gitignored)
  [local]   audit mirror DB location writable
  [infra]   Docker available + auth-api /health healthy
  [infra]   three MCP servers respond to an initialize handshake
  [infra]   four agents respond to /health
  [live]    ArmorIQ reachable (SDK init + list_mcps()) - the ONLY way to know
            whether live enforcement can run. Reported as NOT VERIFIED until
            the log-mcp/diagnostic-mcp/remediation-mcp are registered and
            reachable by the ArmorIQ proxy.

Exit codes:
  0  core local+infra checks pass (live enforcement may still be unverified)
  1  a core check failed
  2  ARMORIQ_API_KEY missing/malformed (required for live/govened mode)

Usage:
    python scripts/preflight.py [--local-only]
    scripts/preflight.sh [--local-only]
    scripts/preflight.ps1 [--local-only]

The report is honest: it never claims live enforcement is ready unless
list_mcps() returns the three registered MCPs.
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import sys
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
if not PYTHON.exists():
    PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"

AGENTS = {
    "log-agent": (8091, "agents.log_agent"),
    "diagnosis-agent": (8092, "agents.diagnosis_agent"),
    "remediation-agent": (8093, "agents.remediation_agent"),
    "commander": (8094, "agents.commander"),
}
MCP = {
    "log-mcp": 8081,
    "diagnostic-mcp": 8082,
    "remediation-mcp": 8083,
}
REQUIRED_MCPS = set(MCP)

MCP_INIT = (
    '{"jsonrpc":"2.0","id":1,"method":"initialize",'
    '"params":{"protocolVersion":"2025-03-26","capabilities":{},'
    '"clientInfo":{"name":"preflight-probe","version":"0"}}}'
)


class Report:
    def __init__(self) -> None:
        self.failures = 0
        self.warnings = 0

    def ok(self, name: str, detail: str = "") -> None:
        print(f"  [PASS] {name}" + (f"  ({detail})" if detail else ""))

    def warn(self, name: str, detail: str = "") -> None:
        self.warnings += 1
        print(f"  [WARN] {name}" + (f"  ({detail})" if detail else ""))

    def fail(self, name: str, detail: str = "") -> None:
        self.failures += 1
        print(f"  [FAIL] {name}" + (f"  ({detail})" if detail else ""))

    def skip(self, name: str, detail: str = "") -> None:
        print(f"  [SKIP] {name}" + (f"  ({detail})" if detail else ""))


def _http_json(url: str, method: str = "GET", data: bytes | None = None, timeout: float = 5.0) -> int:
    req = urllib.request.Request(
        url, method=method, data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status
    except Exception:
        return 0


def _port_open(port: int, timeout: float = 2.0) -> bool:
    with socket.socket() as sock:
        sock.settimeout(timeout)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def main() -> int:
    parser = argparse.ArgumentParser(description="AegisOps preflight readiness report")
    parser.add_argument("--local-only", action="store_true",
                        help="skip network/live checks (armoriq SDK + MCP discovery)")
    args = parser.parse_args()

    print("== AegisOps preflight ==")
    r = Report()

    # 1. Venv ----------------------------------------------------------------
    print("[local] environment")
    if PYTHON.exists():
        r.ok("Python venv present", str(PYTHON))
    else:
        r.fail("Python venv", "run: python -m venv .venv && .venv/Scripts/pip install -r requirements.txt")

    # 2. .env ----------------------------------------------------------------
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        r.ok(".env present", str(env_file))
    else:
        r.warn(".env missing", "copy .env.example to .env for LIVE mode (local runs still work)")

    # 3. ARMORIQ_API_KEY -----------------------------------------------------
    from armoriq.client_setup import get_api_key

    key = None
    try:
        key = get_api_key()
        r.ok("ARMORIQ_API_KEY present and well-formed", f"{key[:9]}... (never printed in full)")
    except Exception as exc:
        r.fail("ARMORIQ_API_KEY", str(exc))
        print("\nHow to fix: copy .env.example to .env and set ARMORIQ_API_KEY.")
        print("Without it the system can still run locally, but governed mode "
              "(ArmorIQ enforcement) cannot activate and live verification is impossible.")
        return 2

    # 4. Gemini key ----------------------------------------------------------
    if os.environ.get("AEGISOPS_GEMINI_API_KEY", "").strip():
        r.ok("AEGISOPS_GEMINI_API_KEY set (real Gemini diagnosis available)")
    else:
        r.warn("AEGISOPS_GEMINI_API_KEY missing",
               "diagnosis will use the deterministic TEST fallback (marked llm_source=fallback)")

    # 5. Identities ----------------------------------------------------------
    from armoriq import client_setup

    for role in client_setup.AGENT_ROLES:
        priv, pub = client_setup.keypair_paths(role)
        if priv.exists() and pub.exists():
            r.ok(f"identity keypair for {role}", f"{priv.parent.name}/")
        else:
            r.fail(f"identity keypair for {role}", f"run: {PYTHON.name} scripts/ensure_identities.py")

    # 6. Audit DB ------------------------------------------------------------
    from database.audit import get_store

    try:
        store = get_store()
        store.record(incident_id="__preflight__", agent="preflight",
                     action="preflight", status="ok")
        r.ok("audit mirror writable", str(store.db_path))
    except Exception as exc:  # noqa: BLE001
        r.fail("audit mirror", str(exc))

    # 7. Docker + auth-api ---------------------------------------------------
    print("[infra] infrastructure")
    if shutil.which("docker"):
        r.ok("docker CLI available")
    else:
        r.fail("docker CLI", "docker must be installed and on PATH")
    code = _http_json("http://localhost:8080/health")
    if code == 200:
        r.ok("auth-api /health", "HTTP 200 healthy")
    elif code == 503:
        r.warn("auth-api /health", "HTTP 503 unhealthy - run scripts/start_env.sh")
    else:
        r.fail("auth-api /health", f"unreachable (HTTP {code}) - run scripts/start_env.sh")

    # 8. MCP servers ---------------------------------------------------------
    for name, port in MCP.items():
        status = _http_json(f"http://127.0.0.1:{port}/mcp", method="POST", data=MCP_INIT.encode())
        if status == 200:
            r.ok(f"{name} reachable", f"port {port}")
        else:
            r.warn(f"{name} reachable", f"port {port} not responding - run scripts/start_mcps.sh")

    # 9. Agents --------------------------------------------------------------
    for name, (port, _mod) in AGENTS.items():
        status = _http_json(f"http://127.0.0.1:{port}/health")
        if status == 200:
            r.ok(f"{name} reachable", f"port {port}")
        else:
            r.warn(f"{name} reachable", f"port {port} not responding - run scripts/start_agents.sh")

    # 10. Live enforcement readiness (network) -------------------------------
    print("[live] ArmorIQ enforcement readiness")
    if args.local_only:
        r.skip("ArmorIQ reachability + MCP registration", "--local-only")
    else:
        try:
            from armoriq.client_setup import get_client

            client = get_client()
            mcps = client.list_mcps()
            registered = {m.get("id") or m.get("name") for m in (mcps or [])}
            r.ok("ArmorIQ SDK + API key authenticated", f"{len(registered)} MCP(s) registered")
            missing = REQUIRED_MCPS - registered
            if not missing:
                r.ok("all required MCPs registered",
                     "live enforcement (Phase 8/9) can be exercised end-to-end")
            else:
                r.warn("required MCPs not registered",
                       "missing: " + ", ".join(sorted(missing)) + " - LIVE ENFORCEMENT NOT READY")
                r.warn(
                    "registration",
                    "register log-mcp/diagnostic-mcp/remediation-mcp on the ArmorIQ "
                    "platform with public HTTPS URLs the proxy can reach.",
                )
        except Exception as exc:  # noqa: BLE001
            r.fail("ArmorIQ reachability", f"{type(exc).__name__}: {exc}")
            r.warn("LIVE ENFORCEMENT NOT VERIFIED", "cannot reach the ArmorIQ platform")

    print()
    if r.failures == 0:
        print("RESULT: READY (local + infrastructure)" if r.warnings == 0
              else f"RESULT: READY WITH WARNINGS ({r.warnings} warning(s))")
        print("Live enforcement status is reported above - never assumed.")
        return 0
    print(f"RESULT: FAILED ({r.failures} failure(s), {r.warnings} warning(s))")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())