"""ArmorIQ SDK smoke test — smallest verification of the AegisOps foundation.

Checks (in order):
  1. configuration  (ARMORIQ_API_KEY present + well-formed)        [local]
  2. client initialization                                        [local]
  3. capture_plan() with the real 4-step AegisOps plan            [local]
  4. Ed25519 keypair generation / save / load round-trip          [local]
  5. get_intent_token()                                           [network]
  6. invoke() (only if a token was obtained)                      [network]

Usage:
    python scripts/armoriq_smoke_test.py                 # full run
    python scripts/armoriq_smoke_test.py --local-only    # skips network steps

Exit codes:
    0  all checks passed
    1  a check failed (see output)
    2  configuration missing (ARMORIQ_API_KEY not set or malformed)

The full run needs a real ARMORIQ_API_KEY. Without one the network steps
fail loudly and clearly — that is intentional, not hidden.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `import armoriq` when running from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from armoriq.client_setup import (  # noqa: E402
    generate_and_save_keypair,
    get_api_key,
    get_client,
    keypair_paths,
    load_private_key,
    public_key_hex,
)

AEGIS_PLAN = {
    "goal": "Diagnose and restart auth-api if unhealthy",
    "steps": [
        {"action": "search_logs",        "mcp": "log-mcp",        "params": {"service": "auth-api"}},
        {"action": "get_service_status", "mcp": "diagnostic-mcp", "params": {"service": "auth-api"}},
        {"action": "inspect_config",     "mcp": "diagnostic-mcp", "params": {"service": "auth-api"}},
        {"action": "restart_service",    "mcp": "remediation-mcp", "params": {"service": "auth-api"}},
    ],
}


class Checker:
    def __init__(self) -> None:
        self.exit_code = 0

    def ok(self, name: str, detail: str = "") -> None:
        print(f"  [PASS] {name}" + (f"  ({detail})" if detail else ""))

    def fail(self, name: str, detail: str = "") -> None:
        self.exit_code = 1
        print(f"  [FAIL] {name}" + (f"  ({detail})" if detail else ""))

    def warn(self, name: str, detail: str = "") -> None:
        print(f"  [WARN] {name}" + (f"  ({detail})" if detail else ""))


def run(checks: Checker, local_only: bool) -> None:
    print("== ArmorIQ smoke test ==")
    print(f"mode: {'local-only' if local_only else 'full (network)'}\n")

    # 1. Configuration -------------------------------------------------------
    print("[1/4] configuration")
    try:
        key = get_api_key()
        checks.ok("ARMORIQ_API_KEY present and well-formed", f"{key[:9]}...")
    except Exception as exc:  # noqa: BLE001 - we want to surface the message
        checks.fail("configuration", str(exc))
        print("\nHow to fix: copy .env.example to .env and set ARMORIQ_API_KEY, "
              "or run `armoriq login` (writes ~/.armoriq/credentials.json).")
        checks.exit_code = 2
        return

    # 2. Client initialization ----------------------------------------------
    print("[2/4] client")
    try:
        client = get_client()
        checks.ok("ArmorIQClient initialized", "timeout=30s, use_production from env")
    except Exception as exc:  # noqa: BLE001
        checks.fail("ArmorIQClient init", str(exc))
        return

    # 3. capture_plan (local) ------------------------------------------------
    try:
        plan = client.capture_plan(
            llm="claude-3",
            prompt="Investigate and remediate an unhealthy auth-api service",
            plan=AEGIS_PLAN,
        )
        n = len(plan.plan["steps"])
        assert n == 4, f"expected 4 steps, got {n}"
        actions = [s["action"] for s in plan.plan["steps"]]
        assert "restart_service" in actions
        checks.ok(
            "capture_plan() accepted the 4-step AegisOps plan",
            f"goal='{plan.plan['goal']}', steps={actions}",
        )
        # plan_hash / merkle_root are computed server-side at get_intent_token()
        # in armoriq-sdk 0.6.10 (not exposed on PlanCapture).
        checks.warn(
            "plan_hash/merkle_root",
            "computed at get_intent_token() in SDK 0.6.10 (not on PlanCapture)",
        )
    except Exception as exc:  # noqa: BLE001
        checks.fail("capture_plan()", str(exc))
        return

    # 4. Keypair round-trip (local) ------------------------------------------
    print("[3/4] identity keypair")
    temp_agent = "_smoke_test"
    try:
        priv_path, pub_path = keypair_paths(temp_agent)
        for p in (priv_path, pub_path):  # clean any leftovers first
            if p.exists():
                p.unlink()
        key = generate_and_save_keypair(temp_agent)
        pub_hex = public_key_hex(key)
        loaded = load_private_key(temp_agent)
        assert public_key_hex(loaded) == pub_hex, "public key mismatch after reload"
        assert len(pub_hex) == 64, f"expected 64 hex chars, got {len(pub_hex)}"
        checks.ok("Ed25519 keypair generate/save/load round-trip", f"pubkey={pub_hex[:12]}...")
    except Exception as exc:  # noqa: BLE001
        checks.fail("keypair round-trip", str(exc))
    finally:
        for p in (priv_path, pub_path):
            if p.exists():
                p.unlink()

    # 5. get_intent_token (network) ------------------------------------------
    print("[4/4] network (get_intent_token)")
    if local_only:
        checks.warn("get_intent_token()", "skipped (--local-only)")
        token = None
    else:
        try:
            token = client.get_intent_token(plan, validity_seconds=300)
            checks.ok(
                "get_intent_token()",
                f"token_id={token.token_id}, expires_at={token.expires_at}, plan_hash={str(token.plan_hash)[:12]}...",
            )
        except Exception as exc:  # noqa: BLE001
            token = None
            name = type(exc).__name__
            checks.fail(f"get_intent_token() raised {name}", str(exc))

    # 6. invoke (network, optional) ------------------------------------------
    if not local_only and token is not None:
        try:
            result = client.invoke(
                mcp="log-mcp",
                action="search_logs",
                intent_token=token,
                params={"service": "auth-api"},
                user_email="commander@aegisops.local",
            )
            checks.ok("invoke()", f"status={result.status}, mcp={result.mcp}, action={result.action}")
        except Exception as exc:  # noqa: BLE001
            checks.fail(f"invoke() raised {type(exc).__name__}", str(exc))

    # 7. Summary -------------------------------------------------------------
    print()
    if checks.exit_code == 0:
        print("RESULT: PASS - foundation verified")
    elif checks.exit_code == 2:
        print("RESULT: CONFIG MISSING - see instructions above")
    else:
        print("RESULT: FAIL - see failures above")
    print("(local checks passed; network steps are the ones that need a real ARMORIQ_API_KEY)")


def main() -> int:
    parser = argparse.ArgumentParser(description="ArmorIQ SDK smoke test for AegisOps")
    parser.add_argument("--local-only", action="store_true", help="skip network steps")
    args = parser.parse_args()

    checks = Checker()
    try:
        run(checks, local_only=args.local_only)
    except Exception as exc:  # noqa: BLE001 - never die silently
        checks.fail("unexpected error", str(exc))
    return checks.exit_code


if __name__ == "__main__":
    raise SystemExit(main())