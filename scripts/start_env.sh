#!/usr/bin/env sh
# Start the AegisOps environment and wait for auth-api to become healthy.
set -eu
cd "$(dirname "$0")/.."

echo "== Starting auth-api =="
docker compose up -d --build

echo "Waiting for /health ..."
for i in $(seq 1 30); do
  if curl -fsS http://localhost:8080/health >/dev/null 2>&1; then
    echo "auth-api is up and healthy."
    exit 0
  fi
  sleep 1
done

echo "ERROR: auth-api did not become healthy in time." >&2
exit 1