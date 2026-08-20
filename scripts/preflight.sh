#!/usr/bin/env sh
# AegisOps preflight readiness report (wraps scripts/preflight.py).
# Usage: scripts/preflight.sh [--local-only]
set -eu
cd "$(dirname "$0")/.."

PYTHON=.venv/Scripts/python.exe
[ -x "$PYTHON" ] || PYTHON=.venv/bin/python

"$PYTHON" scripts/preflight.py "$@"