#!/usr/bin/env sh
# Stop the background MCP servers started by scripts/start_mcps.sh.
set -eu
cd "$(dirname "$0")/.."

for name in remediation-mcp diagnostic-mcp log-mcp; do
  if [ -f "logs/$name.pid" ]; then
    pid=$(cat "logs/$name.pid")
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid"
      echo "stopped $name (pid $pid)"
    else
      echo "$name not running"
    fi
    rm -f "logs/$name.pid"
  fi
done
echo "MCP servers stopped."