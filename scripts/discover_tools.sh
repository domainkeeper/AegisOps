#!/usr/bin/env sh
# Discover the tools exposed by one MCP server (streamable HTTP + SSE).
# Usage: scripts/discover_tools.sh <log-mcp|diagnostic-mcp|remediation-mcp>
set -eu
cd "$(dirname "$0")/.."

name="${1:?usage: discover_tools.sh <log-mcp|diagnostic-mcp|remediation-mcp>}"
port=""
case "$name" in
  log-mcp) port=8081 ;;
  diagnostic-mcp) port=8082 ;;
  remediation-mcp) port=8083 ;;
  *) echo "unknown MCP '$name' (log-mcp, diagnostic-mcp, remediation-mcp)" >&2; exit 1 ;;
esac

INIT='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"discover","version":"0"}}}'
LIST='{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'

# Streamable HTTP (2025-era) requires the Mcp-Session-Id from initialize on later calls.
SESSION=$(curl -fsS -i -X POST "http://127.0.0.1:$port/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d "$INIT" | tr -d '\r' | sed -n 's/^mcp-session-id: //p' | head -n1)

curl -fsS -X POST "http://127.0.0.1:$port/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  ${SESSION:+-H "Mcp-Session-Id: $SESSION"} \
  -d "$LIST" | grep '^data:' | sed 's/^data: //' | .venv/Scripts/python.exe -c "
import json, sys
resp = json.load(sys.stdin)
for tool in resp['result']['tools']:
    print(f\"{tool['name']}: {tool.get('description', '').splitlines()[0]}\")
    print(f\"    input: {json.dumps(tool.get('inputSchema', {}))}\")
"