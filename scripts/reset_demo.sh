#!/usr/bin/env sh
# Reset the environment to a clean state: full compose rebuild, healthy auth-api.
# (Later phases extend this to also clear the local SQLite audit tables.)
set -eu
cd "$(dirname "$0")/.."

echo "== Resetting environment to clean state =="
docker compose down -v
docker compose up -d --build

echo "Waiting for /health ..."
for i in $(seq 1 30); do
  if curl -fsS http://localhost:8080/health >/dev/null 2>&1; then
    echo "Environment reset complete. auth-api healthy."
    exit 0
  fi
  sleep 1
done

echo "ERROR: environment did not come up clean." >&2
exit 1