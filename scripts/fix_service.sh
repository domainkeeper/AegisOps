#!/usr/bin/env sh
# Application-level recovery: restore auth-api health without restarting the container.
set -eu

echo "== Fixing auth-api =="
curl -fsS -X POST http://localhost:8080/fix
echo
echo "Health now:"
curl -sS http://localhost:8080/health
echo