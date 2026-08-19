#!/usr/bin/env sh
# Report whether each MCP server responds to an initialize handshake.
set -eu
cd "$(dirname "$0")/.."

INIT='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"check-probe","version":"0"}}}'

for entry in "log-mcp 8081" "diagnostic-mcp 8082" "remediation-mcp 8083"; do
  set -- $entry
  name="$1"
  port="$2"
  if curl -fsS -X POST "http://127.0.0.1:$port/mcp" \
      -H "Content-Type: application/json" \
      -H "Accept: application/json, text/event-stream" \
      -d "$INIT" 2>/dev/null | grep -q '"result"'; then
    echo "$name :$port OK"
  else
    echo "$name :$port DOWN"
  fi
done