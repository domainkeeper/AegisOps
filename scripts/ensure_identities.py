"""Phase 5 - establish the four agent identities (keypairs + email scopes).

For each AegisOps agent role this:
  1. ensures an Ed25519 keypair exists under .keys/<role>/ (generated if
     missing, never regenerated if present),
  2. prints the PUBLIC key hex (safe to share - it is the binding material
     Phase 6 delegation will use),
  3. prints the resolved email scope (AEGISOPS_<ROLE>_EMAIL or the PLAN §5
     convention <role>@aegisops.local).

Security rules: private keys are never printed or logged. .keys/ is gitignored.

Usage:  python scripts/ensure_identities.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from armoriq.client_setup import AGENT_ROLES, agent_email, ensure_keypair, public_key_hex  # noqa: E402

if __name__ == "__main__":
    print("== AegisOps agent identities ==")
    for role in AGENT_ROLES:
        key = ensure_keypair(role)
        email = agent_email(role)
        print(f"  {role:<16} pubkey={public_key_hex(key)[:16]}...  email={email}")
    print("\nDone. Public keys are safe to share; private keys stay in .keys/ (gitignored).")