#!/usr/bin/env sh
# Run one complete incident end to end with the real (unguarded) multi-agent
# system: break auth-api -> Log Agent investigates -> Diagnosis Agent reasons
# (Gemini if AEGISOPS_GEMINI_API_KEY is set, otherwise the explicitly-marked
# deterministic test fallback) -> Remediation Agent restarts via MCP ->
# the Docker container restarts for real -> auth-api recovers -> Commander
# marks the incident RESOLVED. The Commander also builds and captures the
# explicit 4-step plan (Phase 5 intent handshake; needs ARMORIQ_API_KEY for a
# real intent token, otherwise reported as not_configured - never faked).
# With a working ARMORIQ_API_KEY, Phase 6/7 activate: the Commander delegates
# three scoped authorities (log/diagnosis/remediation) and the children invoke
# their MCP actions through ArmorIQ (governed path); otherwise the run stays
# unguarded (Phase 4 baseline) and that is reported honestly as 0 delegations.
#
# Usage:
#   scripts/run_incident.sh [incident_id]
set -eu
cd "$(dirname "$0")/.."

INCIDENT_ID="${1:-inc-$(date +%s)}"

PYTHON=.venv/Scripts/python.exe
[ -x "$PYTHON" ] || PYTHON=.venv/bin/python

echo "== AegisOps unguarded incident run: $INCIDENT_ID =="

if [ -z "${AEGISOPS_GEMINI_API_KEY:-}" ]; then
  export AEGISOPS_LLM_FALLBACK=test
  echo "NOTE: no AEGISOPS_GEMINI_API_KEY set - the Diagnosis Agent will use the"
  echo "      explicitly-marked deterministic TEST fallback (diagnosis is NOT"
  echo "      model-generated). Set AEGISOPS_GEMINI_API_KEY for real Gemini"
  echo "      diagnosis. Restarting agents so they pick up the fallback setting..."
  scripts/stop_agents.sh >/dev/null 2>&1 || true
fi

echo "[1/6] Ensuring infrastructure is running..."
scripts/start_env.sh >/dev/null
scripts/start_mcps.sh >/dev/null
scripts/start_agents.sh >/dev/null

echo "[2/6] Breaking auth-api..."
curl -fsS -X POST http://localhost:8080/break >/dev/null

echo "[3/6] Waiting for /health to report unhealthy..."
unhealthy=""
for _ in $(seq 1 30); do
  code=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/health || true)
  if [ "$code" = "503" ]; then
    unhealthy=1
    break
  fi
  sleep 0.5
done
[ -n "$unhealthy" ] || { echo "ERROR: auth-api never went unhealthy" >&2; exit 1; }
echo "      /health -> 503 (unhealthy)"

echo "[4/6] Submitting incident to Commander..."
response=$(curl -fsS -X POST http://127.0.0.1:8094/incident \
  -H "Content-Type: application/json" \
  -d "{\"incident_id\":\"$INCIDENT_ID\",\"service\":\"auth-api\",\"severity\":\"high\",\"description\":\"auth-api unhealthy\"}")

echo "[5/6] Incident result:"
echo "$response" | "$PYTHON" -c "import json,sys; d=json.load(sys.stdin); print('  status        :', d['status']); print('  incident_id   :', d['incident_id']); print('  evidence items:', len((d.get('investigation') or {}).get('evidence', []))); diag=d.get('diagnosis') or {}; print('  diagnosis     :', diag.get('diagnosis','')); print('  llm_source    :', diag.get('llm_source')); rem=d.get('remediation') or {}; print('  remediation   :', (('noop=' + str(rem.get('noop')) + ' success=' + str(rem.get('success'))) if rem.get('noop') is not None else 'none needed'), (rem.get('started_at') or '')); print('  verification  :', (d.get('verification') or {}).get('status')); plan=d.get('plan') or {}; print('  plan          :', str(len(plan.get('steps', []))) + ' steps captured (' + ', '.join(s.get('action','') for s in plan.get('steps', [])) + ')'); ts=d.get('intent_token_status'); print('  intent token  :', ts, (d.get('intent_token_expires_at') or ('(' + (d.get('intent_token_error') or '') + ')' if ts != 'ready' else ''))); deps=d.get('delegations') or []; print('  delegations   :', (str(len(deps)) + ' (governed=True, ' + ', '.join(x.get('agent','') + ':' + ','.join(x.get('allowed_actions', [])) for x in deps) + ')') if deps else ('0 (governed=False)' + ((' - ' + d.get('delegation_error')) if d.get('delegation_error') else ''))); print('  error         :', d.get('error'))" 2>/dev/null \
  || echo "$response" | sed 's/^/  /'

case "$response" in
  *'"status":"RESOLVED"'*) echo "[6/6] Incident RESOLVED." ;;
  *) echo "[6/6] Incident FAILED - see agent logs under logs/agents/"; exit 1 ;;
esac

echo "== Final health check =="
curl -fsS http://localhost:8080/health
echo