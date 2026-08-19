#!/usr/bin/env sh
# Invoke one tool on one MCP server and print the JSON result.
# Usage: scripts/call_mcp_tool.sh <log-mcp|diagnostic-mcp|remediation-mcp> <tool> '<json-args>'
set -eu
cd "$(dirname "$0")/.."

name="${1:?usage: call_mcp_tool.sh <mcp-name> <tool> '<json-args>'}"
tool="${2:?usage: call_mcp_tool.sh <mcp-name> <tool> '<json-args>'}"
args="${3:?usage: call_mcp_tool.sh <mcp-name> <tool> '<json-args>'}"

port=""
case "$name" in
  log-mcp) port=8081 ;;
  diagnostic-mcp) port=8082 ;;
  remediation-mcp) port=8083 ;;
  *) echo "unknown MCP '$name' (log-mcp, diagnostic-mcp, remediation-mcp)" >&2; exit 1 ;;
esac

INIT='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"caller","version":"0"}}}'
CALL=$(printf '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"%s","arguments":%s}}' "$tool" "$args")

SESSION=$(curl -fsS -i -X POST "http://127.0.0.1:$port/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d "$INIT" | tr -d '\r' | sed -n 's/^mcp-session-id: //p' | head -n1)

curl -fsS -X POST "http://127.0.0.1:$port/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  ${SESSION:+-H "Mcp-Session-Id: $SESSION"} \
  -d "$CALL" | grep '^data:' | sed 's/^data: //' | .venv/Scripts/python.exe -c "
import json, sys
resp = json.load(sys.stdin)
if 'error' in resp:
    print(f\"ERROR {resp['error']}\")
    sys.exit(1)
for item in resp['result']['content']:
    if item['type'] == 'text':
        print(item['text'])
"