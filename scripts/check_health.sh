#!/usr/bin/env sh
# Print the current auth-api health response.
set -eu

curl -sS http://localhost:8080/health
echo