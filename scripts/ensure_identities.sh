#!/usr/bin/env sh
# Phase 5: establish the four agent identities - per-agent Ed25519 keypairs
# (.keys/<role>/, generated if missing) and the resolved email scopes.
# Public keys are printed (safe to share); private keys are never printed.
set -eu
cd "$(dirname "$0")/.."

PYTHON=.venv/Scripts/python.exe
[ -x "$PYTHON" ] || PYTHON=.venv/bin/python

"$PYTHON" scripts/ensure_identities.py