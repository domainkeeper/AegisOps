#!/usr/bin/env sh
# AegisOps static security checks (wraps scripts/check_security.py).
# Usage: scripts/check_security.sh
set -eu
cd "$(dirname "$0")/.."

PYTHON=.venv/Scripts/python.exe
[ -x "$PYTHON" ] || PYTHON=.venv/bin/python

"$PYTHON" scripts/check_security.py "$@"