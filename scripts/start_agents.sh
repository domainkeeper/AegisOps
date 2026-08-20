#!/usr/bin/env sh
# Start the four AegisOps agent processes (commander, log-agent, diagnosis-agent,
# remediation-agent) as background processes. PIDs and logs go to ./logs/agents.
# Requires the venv and the MCP servers (scripts/start_mcps.sh) plus a running
# auth-api (scripts/start_env.sh).
set -eu
cd "$(dirname "$0")/.."

PYTHON=.venv/Scripts/python.exe
[ -x "$PYTHON" ] || PYTHON=.venv/bin/python

mkdir -p logs/agents

start_one() {
  name="$1"
  module="$2"
  if [ -f "logs/agents/$name.pid" ] && kill -0 "$(cat "logs/agents/$name.pid")" 2>/dev/null; then
    echo "$name already running (pid $(cat "logs/agents/$name.pid"))"
    return
  fi
  "$PYTHON" -m "$module" >"logs/agents/$name.log" 2>&1 &
  echo $! >"logs/agents/$name.pid"
  echo "started $name (pid $!)"
}

start_one commander agents.commander
start_one log-agent agents.log_agent
start_one diagnosis-agent agents.diagnosis_agent
start_one remediation-agent agents.remediation_agent

for port in 8091 8092 8093 8094; do
  ok=""
  for _ in $(seq 1 40); do
    if curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
      ok=1
      break
    fi
    sleep 0.5
  done
  [ -n "$ok" ] || { echo "ERROR: agent on port $port did not come up" >&2; exit 1; }
done

echo "Agents ready: log-agent :8091, diagnosis-agent :8092, remediation-agent :8093, commander :8094"