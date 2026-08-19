#!/usr/bin/env sh
# Start the three AegisOps MCP servers (log-mcp, diagnostic-mcp, remediation-mcp)
# as background processes. PIDs and logs go to ./logs. Requires the venv
# (pip install -r requirements.txt) and a running auth-api (scripts/start_env.sh).
set -eu
cd "$(dirname "$0")/.."

PYTHON=.venv/Scripts/python.exe
[ -x "$PYTHON" ] || PYTHON=.venv/bin/python

mkdir -p logs

start_one() {
  name="$1"
  module="$2"
  if [ -f "logs/$name.pid" ] && kill -0 "$(cat "logs/$name.pid")" 2>/dev/null; then
    echo "$name already running (pid $(cat "logs/$name.pid"))"
    return
  fi
  "$PYTHON" -m "$module" >"logs/$name.log" 2>&1 &
  echo $! >"logs/$name.pid"
  echo "started $name (pid $!)"
}

start_one log-mcp mcp_servers.log_mcp
start_one diagnostic-mcp mcp_servers.diagnostic_mcp
start_one remediation-mcp mcp_servers.remediation_mcp

INIT='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"start-probe","version":"0"}}}'

for port in 8081 8082 8083; do
  ok=""
  for _ in $(seq 1 40); do
    if curl -fsS -X POST "http://127.0.0.1:$port/mcp" \
        -H "Content-Type: application/json" \
        -H "Accept: application/json, text/event-stream" \
        -d "$INIT" 2>/dev/null | grep -q '"result"'; then
      ok=1
      break
    fi
    sleep 0.5
  done
  [ -n "$ok" ] || { echo "ERROR: MCP on port $port did not come up" >&2; exit 1; }
done

echo "MCP servers ready: log-mcp :8081, diagnostic-mcp :8082, remediation-mcp :8083"