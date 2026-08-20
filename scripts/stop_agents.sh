#!/usr/bin/env sh
# Stop the background agent processes started by scripts/start_agents.sh.
set -eu
cd "$(dirname "$0")/.."

for name in remediation-agent diagnosis-agent log-agent commander; do
  if [ -f "logs/agents/$name.pid" ]; then
    pid=$(cat "logs/agents/$name.pid")
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid"
      echo "stopped $name (pid $pid)"
    else
      echo "$name not running"
    fi
    rm -f "logs/agents/$name.pid"
  fi
done
echo "Agents stopped."