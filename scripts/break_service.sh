#!/usr/bin/env sh
# Simulate an incident: put auth-api into an unhealthy state.
set -eu

echo "== Breaking auth-api =="
curl -fsS -X POST http://localhost:8080/break
echo
echo "Health now:"
curl -sS http://localhost:8080/health
echo