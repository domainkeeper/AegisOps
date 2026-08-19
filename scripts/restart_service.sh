#!/usr/bin/env sh
# Restart the auth-api container for real and wait for it to recover.
# This is the exact operation the future Remediation MCP's restart_service()
# will perform.
set -eu

echo "== Restarting auth-api container =="
docker restart auth-api

echo "Waiting for /health ..."
for i in $(seq 1 30); do
  if curl -fsS http://localhost:8080/health >/dev/null 2>&1; then
    echo "auth-api is healthy again."
    exit 0
  fi
  sleep 1
done

echo "ERROR: auth-api did not recover after restart." >&2
exit 1