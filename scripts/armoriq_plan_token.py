"""Phase 5 - full intent handshake for a single incident (needs a real key).

Mirrors exactly what the Commander does on /incident, as a standalone script so
the ArmorIQ account can be verified end-to-end once a real ARMORIQ_API_KEY is
available: explicit 4-step plan -> capture_plan() -> get_intent_token().

The intent token itself is SENSITIVE (it carries raw_token/jwt_token) and is
NEVER printed or logged here - only its status, plan_hash prefix, token_id, and
expiry are shown.

Usage:
    python scripts/armoriq_plan_token.py --incident-id demo-1 --service auth-api
    python scripts/armoriq_plan_token.py --local-only   # no network

Exit codes:
    0  token ready (or --local-only local checks passed)
    1  handshake failed (see output)
    2  configuration missing
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from armoriq.client_setup import get_api_key, get_client  # noqa: E402
from armoriq.plan import (  # noqa: E402
    PlanValidationError,
    armoriq_configured,
    build_incident_plan,
    capture_execution_plan,
    generate_intent_token,
    validate_plan,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="AegisOps intent-token handshake (Phase 5)")
    parser.add_argument("--incident-id", default="demo-1")
    parser.add_argument("--service", default="auth-api")
    parser.add_argument("--local-only", action="store_true", help="skip the network token step")
    parser.add_argument("--validity-seconds", type=float, default=300.0)
    args = parser.parse_args()

    if not armoriq_configured():
        print("ARMORIQ_API_KEY is not set. Copy .env.example to .env and set it.")
        return 2

    incident = SimpleNamespace(incident_id=args.incident_id, service=args.service)
    plan = build_incident_plan(incident)
    try:
        validate_plan(plan)
    except PlanValidationError as exc:
        print(f"plan validation failed: {exc}")
        return 1
    print(f"plan: {len(plan['steps'])} steps -> {[s['action'] for s in plan['steps']]}")

    try:
        client = get_client()
        plan_capture = capture_execution_plan(client, incident)
        print(f"capture_plan: ok (plan_id={getattr(plan_capture, 'plan_id', 'n/a')})")
    except Exception as exc:  # noqa: BLE001 - surface the SDK message
        print(f"capture_plan failed: {type(exc).__name__}: {exc}")
        return 1

    if args.local_only:
        print("get_intent_token: skipped (--local-only)")
        return 0

    try:
        token = generate_intent_token(client, plan_capture, validity_seconds=args.validity_seconds)
    except Exception as exc:  # noqa: BLE001
        print(f"get_intent_token failed: {type(exc).__name__}: {exc}")
        return 1

    # Only non-sensitive token metadata is ever shown.
    print(
        f"get_intent_token: ready  token_id={getattr(token, 'token_id', 'n/a')} "
        f"plan_hash={str(getattr(token, 'plan_hash', ''))[:16]}... "
        f"expires_at={getattr(token, 'expires_at', 'n/a')}"
    )
    print("The token itself is held only in memory and never logged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())