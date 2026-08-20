#!/usr/bin/env sh
# AegisOps authorization enforcement demonstration (Phase 8 + 9).
#
# One deterministic script, two scenes, no edits mid-run:
#
#   Scene 1 (Phase 8 - BLOCKED): the Diagnosis Agent deliberately attempts
#     restart_service with ITS OWN delegated authority. The attempt goes
#     Agent -> ArmorIQ invoke() -> authorization -> MCP. The Diagnosis
#     authority does not include restart_service, so ArmorIQ rejects it. The
#     script proves nothing happened: the Docker container's StartedAt is
#     unchanged and the audit mirror holds a status="blocked" row.
#
#   Scene 2 (Phase 9 - ALLOWED): the Remediation Agent performs the SAME
#     restart_service action with ITS OWN delegated authority. ArmorIQ accepts
#     it, the remediation MCP executes a REAL docker restart, StartedAt
#     changes, and auth-api /health returns healthy. The audit mirror holds a
#     status="success" row.
#
# The difference between the two scenes is ONLY the cryptographically
# delegated authority attached to each agent's token - never keywords, agent
# names, or local policy checks.
#
# Failure behavior: a real ARMORIQ_API_KEY and a reachable ArmorIQ proxy are
# REQUIRED. If the platform is unavailable or governed mode cannot activate,
# the demo fails honestly and reports it - there is NO fallback from governed
# to unguarded during this demonstration.
#
# Usage:
#   scripts/run_enforcement_demo.sh [incident_id]
set -eu
cd "$(dirname "$0")/.."

INCIDENT_ID="${1:-demo-$(date +%s)}"

PYTHON=.venv/Scripts/python.exe
[ -x "$PYTHON" ] || PYTHON=.venv/bin/python

AUDIT_DB="${AEGISOPS_AUDIT_DB:-$(pwd)/database/audit.db}"

if [ -z "${ARMORIQ_API_KEY:-}" ]; then
  echo "ERROR: ARMORIQ_API_KEY is required for the enforcement demo." >&2
  echo "       The demonstration never fakes blocked/allowed outcomes and" >&2
  echo "       never falls back to the unguarded path." >&2
  exit 1
fi

echo "== AegisOps authorization enforcement demo: $INCIDENT_ID =="
echo "(same capability: restart_service - different delegated authority: blocked vs allowed)"

if [ -z "${AEGISOPS_GEMINI_API_KEY:-}" ]; then
  export AEGISOPS_LLM_FALLBACK=test
  echo "NOTE: no AEGISOPS_GEMINI_API_KEY set - deterministic TEST diagnosis fallback."
  echo "      (authorization decisions never depend on the LLM)"
  scripts/stop_agents.sh >/dev/null 2>&1 || true
fi

started_at_before=$(docker inspect -f '{{.State.StartedAt}}' auth-api 2>/dev/null || echo "unknown")

echo "[1/8] Ensuring infrastructure is running..."
scripts/start_env.sh >/dev/null
scripts/start_mcps.sh >/dev/null
scripts/start_agents.sh >/dev/null

echo "[2/8] Breaking auth-api..."
curl -fsS -X POST http://localhost:8080/break >/dev/null

echo "[3/8] Waiting for /health to report unhealthy..."
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

echo "[4/8] Submitting incident to Commander (governed mode)..."
response=$(curl -fsS -X POST http://127.0.0.1:8094/incident \
  -H "Content-Type: application/json" \
  -d "{\"incident_id\":\"$INCIDENT_ID\",\"service\":\"auth-api\",\"severity\":\"high\",\"description\":\"auth-api unhealthy\"}")

echo "[5/8] SCENE 1 - Diagnosis Agent attempts restart_service with its own authority:"
echo "$response" | "$PYTHON" -c "import json,sys; d=json.load(sys.stdin); diag=d.get('diagnosis') or {}; print('  governed           :', d.get('governed')); print('  attempt recorded   :', diag.get('governed_restart_attempted')); print('  blocked by ArmorIQ :', diag.get('governed_restart_blocked')); err=diag.get('governed_restart_error') or ''; print('  verified exception :', err.split('(')[1].split(')')[0] if '(' in err else err)" 2>/dev/null \
  || true
case "$response" in
  *'"governed_restart_blocked":true'*) echo "  => BLOCKED: ArmorIQ rejected the out-of-authority action" ;;
  *'"governed":false'*)
    echo "ERROR: governed mode did not activate - the demo cannot continue." >&2
    echo "$response" >&2
    exit 1 ;;
  *) echo "  => NOT BLOCKED - unexpected; see incident result above (honest report)" ;;
esac

started_at_after_scene1=$(docker inspect -f '{{.State.StartedAt}}' auth-api 2>/dev/null || echo "unknown")
echo "  docker StartedAt before scene 1: $started_at_before"
echo "  docker StartedAt after  scene 1: $started_at_after_scene1"
if [ "$started_at_before" != "unknown" ] && [ "$started_at_before" = "$started_at_after_scene1" ]; then
  echo "  => PROOF: the container was NOT restarted by the blocked attempt"
else
  echo "  => WARNING: container StartedAt changed during scene 1 - investigate!" >&2
fi

echo "[6/8] SCENE 2 - Remediation Agent performs restart_service with its own authority:"
echo "$response" | "$PYTHON" -c "import json,sys; d=json.load(sys.stdin); rem=d.get('remediation') or {}; print('  remediation attempt :', rem.get('attempted')); print('  remediation success :', rem.get('success')); print('  restarted service   :', rem.get('service')); print('  incident status     :', d.get('status'))" 2>/dev/null \
  || echo "$response" | sed 's/^/  /'
case "$response" in
  *'"status":"RESOLVED"'*) echo "  => ALLOWED: ArmorIQ accepted the authorized restart" ;;
  *) echo "  => remediation did not succeed - see incident result above (honest report)" >&2 ;;
esac

started_at_after=$(docker inspect -f '{{.State.StartedAt}}' auth-api 2>/dev/null || echo "unknown")
echo "  docker StartedAt before scene 2: $started_at_after_scene1"
echo "  docker StartedAt after  scene 2: $started_at_after"
if [ "$started_at_after_scene1" != "unknown" ] && [ "$started_at_after_scene1" != "$started_at_after" ]; then
  echo "  => PROOF: the container WAS restarted by the authorized action"
else
  echo "  => WARNING: container StartedAt did not change - investigate!" >&2
fi

echo "[7/8] Final health check:"
curl -fsS http://localhost:8080/health || true
echo

echo "[8/8] Audit mirror for this incident:"
AEGISOPS_AUDIT_DB="$AUDIT_DB" "$PYTHON" -c "
import sys
sys.path.insert(0, '.')
from database.audit import get_store
rows = [r for r in get_store().recent(500) if r.get('incident_id') == '$INCIDENT_ID']
if not rows:
    print('  (no audit rows found - unexpected for a governed run)')
for r in rows:
    print('  %s | %-16s | %-32s | %-9s | %s' % (
        r.get('created_at', '')[:19], r.get('agent', ''), r.get('action', ''),
        r.get('status', ''), r.get('error_type', '') or ''))
" 2>/dev/null || true

case "$response" in
  *'"governed_restart_blocked":true'*'"status":"RESOLVED"'*)
    echo "== DEMO COMPLETE: unauthorized attempt BLOCKED, authorized recovery ALLOWED ==" ;;
  *)
    echo "== DEMO INCOMPLETE - see messages above ==" >&2
    exit 1 ;;
esac