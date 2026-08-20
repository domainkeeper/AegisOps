# AegisOps

**Autonomous incident response with cryptographically enforced agent authority.**

> **CAPABLE ≠ AUTHORIZED.**

---

## Problem

Autonomous agents can now investigate and act on real infrastructure. But capability is not the same as
authority: an agent that *can* restart a service is not the same as an agent that *may* restart it.
When agents make real-world changes, authorization must be proven, not assumed.

## Solution

AegisOps is a multi-agent incident-response system where every agent holds its own cryptographic identity,
and every tool call is authorized against a **signed, scoped token** issued by the ArmorIQ platform. An agent
that tries to exceed its delegated authority is blocked by ArmorIQ — even if its LLM "decides" otherwise.

## Architecture

```
User / demo script
      │
      ▼
Commander Agent ──── capture_plan() → get_intent_token() → delegate_subtree() × 3
      │
      ├────► Log Agent        ──► Log MCP        ──► docker logs / log file          (read)
      ├────► Diagnosis Agent  ──► Diagnostic MCP ──► auth-api /health, docker inspect (read)
      └────► Remediation Agent──► Remediation MCP ──► docker restart auth-api         (write)

All invoke() calls pass through the ArmorIQ Proxy for verification before reaching an MCP.
```

## MCP Layer (implemented)

The capability boundary of AegisOps. Three MCP servers expose **narrowly scoped tools** over the official MCP
protocol (MCP Python SDK `mcp==2.0.0`, Streamable HTTP, SSE responses — the same wire format the ArmorIQ proxy
requires: JSON-RPC 2.0 over HTTP, `event: message`). There is **no generic shell/command tool anywhere**.

| Server | Port | Tools | Nature |
|---|---|---|---|
| `log-mcp` | 8081 | `search_logs(service, keyword?, since?, limit?)` | Read-only (`docker logs`) |
| `diagnostic-mcp` | 8082 | `get_service_status(service)`, `inspect_service_state(service)` | Read-only |
| `remediation-mcp` | 8083 | `restart_service(service_name)` | **Write** — real `docker restart`, allowlist-scoped |

Service names are resolved through an explicit allowlist (`auth-api` only today); anything else — including
injection-shaped names like `"auth-api; rm -rf /"` — is rejected.

**Connectivity:** local development talks to the MCPs directly on localhost. When the hosted ArmorIQ proxy must
invoke them, each MCP needs a public HTTPS URL (registration requirement) — via a tunnel or a reachable deploy;
alternatively the officially supported self-hosted ArmorIQ stack can reach localhost MCPs directly. See
`ARCHITECTURE.md` §7 for the full decision.

## Agents

Four genuinely separate processes communicating over plain HTTP. With ArmorIQ credentials the flow is
**governed**: each agent holds a scoped delegation and every tool call goes Agent → ArmorIQ Proxy → MCP.
Without credentials the **unguarded** Phase 4 baseline runs (every agent can reach every capability) and
that fact is reported honestly. The Phase 8/9 enforcement demonstration exercises exactly the same path in
both modes: blocked for the Diagnosis Agent's restart attempt, allowed for the Remediation Agent's.

| Agent | Process (port) | Talks to (HTTP → MCP) | Role |
|---|---|---|---|
| Commander | `agents/commander.py` (8094) | all three agents, `diagnostic-mcp` | Orchestrator: receives incident, drives investigation → diagnosis → remediation → verification, marks RESOLVED/FAILED |
| Log Agent | `agents/log_agent.py` (8091) | `log-mcp` | Fetches log evidence, returns a compact structured summary |
| Diagnosis Agent | `agents/diagnosis_agent.py` (8092) | `diagnostic-mcp`, `remediation-mcp` | Inspects state, reasons over evidence (LLM); governed: deliberately attempts the restart (blocked + recorded); unguarded: performs the remediation itself |
| Remediation Agent | `agents/remediation_agent.py` (8093) | `diagnostic-mcp`, `remediation-mcp` | Executes the restart through the MCP (idempotency guard: healthy service → no-op) |

Agent → MCP → Docker. No agent ever runs `docker` directly; there is no shell tool anywhere.

**LLM (Diagnosis Agent only):** the official `google-genai` SDK (`agents/llm.py`) against
`gemini-3.5-flash-lite` (the current stable GA Flash-Lite model, verified against the official Gemini API
docs) — configured with `AEGISOPS_GEMINI_API_KEY` and `AEGISOPS_LLM_MODEL`. The model interprets evidence and
returns a strict JSON diagnosis (requested via `response_json_schema`) which is re-validated against a schema
+ an action allowlist (`none` / `restart_service` only). The model never executes anything. With no key
configured, the agent fails clearly — or uses the **explicitly-marked deterministic TEST fallback** when
`AEGISOPS_LLM_FALLBACK=test` is set (always labelled `llm_source: "fallback"`, never presented as
model-generated).

## ArmorIQ's Role

ArmorIQ is the source of truth for authorization. Phase 5 implemented the intent layer; Phases 6–7 added the
authority + governed-invocation layer; Phase 8–9 added the enforcement demonstrations:

- `capture_plan()` — **implemented (Phase 5):** Commander captures the explicit 4-step incident plan
  (goal + steps) — local
- `get_intent_token()` — **implemented (Phase 5):** plan is canonicalized, hashed, Merkle-proved, and signed;
  the token is held in memory as readiness state, never logged or returned
- `delegate_subtree()` — **implemented (Phase 6):** Commander mints three scoped, time-limited tokens via
  the live-verified subtree-delegation mechanism, each bound to a child agent's public key (log:
  `search_logs`; diagnosis: read-only state tools; remediation: `restart_service`) — the legacy `delegate()`
  payload is rejected by the platform (400 `parentToken is required`) and is not used
- `invoke()` — **implemented (Phase 7):** every governed tool call goes through the ArmorIQ Proxy with the
  delegated token; out-of-scope calls are **blocked** by ArmorIQ and the verified exception type is
  surfaced + audited
- **Enforcement demonstration (Phase 8–9):** the Diagnosis Agent deliberately attempts `restart_service`
  with its own (read-only) authority — ArmorIQ **blocks** it, the attempt is recorded + audited, and the
  container is provably untouched. The Remediation Agent then performs the **same action** with its own
  authority — ArmorIQ **allows** it and the container really restarts

## Core Security Concept

The Diagnosis Agent attempts `restart_service("auth-api")`. The Remediation Agent also calls
`restart_service("auth-api")`. Same action. Same parameters. Same tool.

The first is **blocked** by ArmorIQ. The second **succeeds**. The only difference is which
cryptographically-signed token was presented — enforcement is keyed on the token's allow-list and signed
plan proof, never on the text of the request and never on what an LLM intends.

## Incident Scenario (current)

1. `auth-api` container is broken (`POST /break`) — `/health` → 503
2. The incident is submitted to the Commander (`POST /incident`) — it builds the explicit 4-step plan and
   captures it with ArmorIQ (`capture_plan` → `get_intent_token`; honest `not_configured` without a key),
   then delegates three scoped authorities to the children (`delegate_subtree()` ×3; honest
   `delegations: []` + `governed: false` without a key)
3. Commander asks the Log Agent to investigate → log evidence (governed `invoke()` when a delegation is
   held, otherwise the unguarded direct path)
4. Commander sends the evidence to the Diagnosis Agent → service state + LLM/fallback reasoning
5. Diagnosis concludes a restart is needed. **Governed mode:** it deliberately attempts `restart_service`
   with its own read-only authority — ArmorIQ **blocks** it (recorded + audited, never fatal) — and the
   incident continues so the Remediation Agent can act. **Unguarded mode** (no ArmorIQ credentials): it
   performs the restart itself (Phase 4 baseline)
6. Commander asks the Remediation Agent to restart (`restart_service` — governed `invoke()` or direct)
7. Commander verifies `/health` and marks the incident **RESOLVED**

With ArmorIQ credentials the flow is Agent → ArmorIQ Proxy → MCP; without them the identical unguarded
baseline runs and that fact is reported honestly. The Phase 8/9 enforcement demonstration runs the SAME
incident with a real key: the Diagnosis Agent's `restart_service` attempt is **blocked** (its delegated
token has no restart authority) while the Remediation Agent's separately-delegated call **succeeds** — the
same action string, different cryptographically delegated authority, different real-world outcome.

## Planned Stack

- **Language:** Python (separate agent processes)
- **Authorization:** ArmorIQ SDK (`armoriq-sdk`) + Ed25519 keypairs (`cryptography`)
- **Infrastructure:** Docker (`auth-api` FastAPI service)
- **MCPs:** official MCP Python SDK (`mcp==2.0.0`), Streamable HTTP; three servers (`mcp_servers/`)
- **Storage:** SQLite (thin audit mirror), ArmorIQ platform (crypto truth)
- **LLM:** diagnosis rationale only (narrow, deterministic control flow)
- **Transport:** HTTP between agents

## Current Progress

- **Architecture completed** — `PLAN.md` + `ARCHITECTURE.md` define the full system.
- **ArmorIQ SDK verified** — package `armoriq-sdk 0.6.10` installed and confirmed against official docs:
  client init, `capture_plan` / `get_intent_token` / `delegate` / `invoke`, exception model, proxy model,
  MCP registration + wire format (JSON-RPC 2.0 over HTTP/SSE).
- **Foundation established** — Python 3.12 venv, pinned `requirements.txt`, `.env.example`, client/identity
  helpers (`armoriq/client_setup.py`), and a smoke test (`scripts/armoriq_smoke_test.py`) that passes in
  local-only mode. Network steps verified only up to a clean, clear failure without a real API key.
- **Real incident infrastructure built and verified** — `auth-api` (FastAPI) in Docker with `/health`,
  `/break`, `/fix`; a real `docker restart auth-api` recovers the service (proven by tests + manual run).
- **MCP layer built and verified** — transport spike passed; three MCP servers with four tools; the
  `restart_service("auth-api")` tool performs a real Docker restart (start time changes, health recovers).
  ArmorIQ connectivity resolved (see ARCHITECTURE.md §7.2).
- **Unguarded multi-agent system built and verified** — four independent agent processes orchestrate the
  complete incident flow over HTTP; the Diagnosis Agent reasons (Gemini or marked fallback) and performs the
  unguarded restart; the container really restarts and the incident reaches RESOLVED. 42 agent tests pass.
- **Identities + plan + intent token built (Phase 5)** — per-agent Ed25519 keypairs (`.keys/<role>/`,
  gitignored) + email scopes; explicit 4-step plan (`armoriq/plan.py`); Commander `capture_plan()` →
  `get_intent_token()` on every incident with the token never stored/logged/serialized; standalone
  `scripts/ensure_identities.py` and `scripts/armoriq_plan_token.py`; `tests/test_phase5.py`. The LLM
  switched to the verified `gemini-3.5-flash-lite` via `google-genai`.
- **Delegation + governed invocation + audit mirror built (Phases 6–7)** — `armoriq/delegation.py` mints
  the three scoped authorities via the **live-verified `delegate_subtree()` mechanism** (`subtree_path` per
  agent: log `"0"`, diagnosis `"1,2"`, remediation `"3"`; verified scopes, key-bound, tokens in memory
  only); governed agents call `invoke()` through the ArmorIQ proxy when they hold a delegation
  (`invoke_governed`, rejections surfaced + audited, never faked); SQLite audit mirror (`database/audit.py`,
  safe metadata only); no credentials → unguarded Phase 4 baseline unchanged and reported honestly.
  `tests/test_phase67.py`.
- **Enforcement demonstration built (Phases 8–9)** — the Diagnosis Agent deliberately attempts
  `restart_service("auth-api")` with its own read-only authority via `invoke_governed`; the outcome
  (blocked/error/allowed) is recorded on the result (`governed_restart_attempted/blocked/error/result`) and
  audited — never fatal, never faked, no keyword filtering, no local policy layer pretending to be ArmorIQ.
  The Remediation Agent performs the identical action with its own authority. `scripts/run_enforcement_demo.sh`
  drives both scenes in one run and proves the blocked attempt never touches the container (Docker
  `StartedAt`). Live proof still requires the MCPs registered on the ArmorIQ platform with public tunnel
  URLs (see ARCHITECTURE.md §7.2); `tests/test_live_authorization.py` verifies blocked + allowed against the
  real platform and self-skips when the live prerequisites are missing.
- **Final engineering pass (hardening + reliability + tooling)** — defense-in-depth on the governed path
  (cross-agent token substitution rejected, expired authorities fail fast, every SDK failure wrapped +
  audited with its verified type); real timeouts on MCP calls + bounded retry on transient transport
  failures only (never on tool errors or denials); Commander duplicate in-flight rejection + explicit
  incident state machine; SQLite audit query indexes + `by_incident`; LLM evidence sanitization against
  prompt injection (bounds, control-char stripping, DATA-vs-instructions reinforcement); hostile-input MCP
  tests; `scripts/preflight.py` readiness report and `scripts/check_security.py` static scan (event-framing
  wording, secret leakage, shell-execution, gitignore coverage); Windows `.ps1` wrappers; non-root
  `auth-api` container. `tests/test_security.py` (20 tests).

## Current Status

| Area | Status |
|---|---|
| Plan | **Implemented** (`PLAN.md`) |
| Architecture | **Implemented** (`ARCHITECTURE.md`) |
| Python environment + SDK install | **Implemented** (verified on Python 3.12, `armoriq-sdk 0.6.10`, `mcp 2.0.0`) |
| Client/identity foundation | **Implemented** (`armoriq/client_setup.py`, keypair round-trip verified) |
| SDK smoke test | **Implemented** (local path passes; network path needs a real key) |
| Docker infrastructure (`auth-api` + compose + scripts) | **Implemented** (`docker-compose.yml`, `infrastructure/auth_api/`, `scripts/`) |
| Infrastructure tests | **Implemented** (5 tests, all passing — health / break / real restart) |
| MCP tools | **Implemented** (3 servers, 4 tools; 22 tests passing incl. real restart) |
| Multi-agent orchestration (unguarded) | **Implemented** (4 processes, HTTP contracts, Gemini diagnosis, real restart; 42 tests incl. full E2E) |
| Agent identities (Phase 5) | **Implemented** (`.keys/<role>/` Ed25519 keypairs + `AEGISOPS_<ROLE>_EMAIL` scopes) |
| Explicit plan + intent token (Phase 5) | **Implemented** (`armoriq/plan.py`; `capture_plan` → `get_intent_token`; honest ready/error/not_configured) |
| Delegation (Phase 6) | **Implemented** (`armoriq/delegation.py`; live-verified scoped `delegate_subtree()` ×3, key-bound, in-memory tokens, honest delegations/governed) |
| Governed invocation (Phase 7) | **Implemented** (`invoke_governed`; authority-presence mode selection; rejections surfaced + audited, no fake rules) |
| Database | **Implemented** (SQLite audit mirror `database/audit.py`; safe metadata only) |
| Enforcement demonstrations (Phase 8–9) | **Implemented (code + offline tests)** — blocked diagnosis attempt recorded + audited; allowed remediation path. Live verification pending MCP registration with public tunnel URLs (`tests/test_live_authorization.py`, self-skipping) |
| Security-model hardening + reliability (final pass) | **Implemented** — governed-path defense-in-depth, timeouts + bounded retries, duplicate rejection + state machine, audit indexes, prompt-injection sanitization, hostile-input tests, preflight + static checks (`tests/test_security.py`, 20 tests) |
| Demo scripts | **Implemented** (`run_incident.sh` runs one complete incident end to end; `run_enforcement_demo.sh` runs the Phase 8/9 blocked/allowed demonstration; `preflight.sh` + `check_security.sh` + `.ps1` wrappers) |

## Setup

```bash
# Requires Python 3.10 - 3.13 (armoriq-sdk does not support 3.14)
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt

# Configure
copy .env.example .env            # Windows
# then set ARMORIQ_API_KEY=ak_... (or run `armoriq login`)
# and AEGISOPS_GEMINI_API_KEY=... for real Gemini diagnoses
```

## Local Development (Docker)

Requires Docker (engine + Compose). Run the scripts from Git Bash (`C:\Program Files\Git\bin\bash.exe`):

```bash
scripts/start_env.sh        # build + start auth-api, wait until healthy
scripts/check_health.sh     # GET /health
scripts/break_service.sh    # POST /break  -> /health now returns 503
scripts/restart_service.sh  # real `docker restart auth-api` -> recovers (the remediation op)
scripts/fix_service.sh      # POST /fix    -> app-level recovery without a restart
scripts/reset_demo.sh       # compose down -v + up -d --build, back to clean state

# MCP layer (requires auth-api up; runs on 8081/8082/8083)
scripts/start_mcps.sh       # start log-mcp, diagnostic-mcp, remediation-mcp (background)
scripts/check_mcps.sh       # initialize-handshake check per MCP
scripts/discover_tools.sh diagnostic-mcp    # list tools + JSON schemas
scripts/call_mcp_tool.sh log-mcp search_logs '{"service":"auth-api","limit":5}'
scripts/call_mcp_tool.sh remediation-mcp restart_service '{"service_name":"auth-api"}'
scripts/stop_mcps.sh        # stop the MCP servers

# Agents (requires MCPs; runs on 8091/8092/8093/8094)
scripts/start_agents.sh     # start log-agent, diagnosis-agent, remediation-agent, commander
scripts/stop_agents.sh      # stop them
# Set AEGISOPS_GEMINI_API_KEY first for real Gemini diagnosis; without it the
# Diagnosis Agent uses the explicitly-marked test fallback (set
# AEGISOPS_LLM_FALLBACK=test) or fails clearly.

# Phase 5 - agent identities + intent handshake:
scripts/ensure_identities.sh  # (or) python scripts/ensure_identities.py
python scripts/armoriq_plan_token.py --incident-id demo-1 --service auth-api

# Run one complete incident end to end (no manual steps):
scripts/run_incident.sh     # break -> investigate -> diagnose -> restart -> verify -> RESOLVED

# Phase 8/9 enforcement demonstration (REQUIRES a real ARMORIQ_API_KEY; blocked
# diagnosis attempt then authorized remediation recovery, with docker StartedAt
# proof and the audit mirror printed):
scripts/run_enforcement_demo.sh

# Readiness + static security checks:
scripts/preflight.sh          # human-readable readiness report (venv, keys, identities, infra, MCPs, agents, live enforcement status)
scripts/check_security.sh     # static scan: event-framing wording, secret leakage, shell-exec, gitignore coverage

# Windows PowerShell wrappers (call the same scripts via Git Bash):
scripts\preflight.ps1
scripts\check_security.ps1
scripts\run_incident.ps1
scripts\run_enforcement_demo.ps1
scripts\stop_all.ps1

# Automated verification (from repo root, requires running Docker):
python -m pytest tests/test_infrastructure.py -v      # 5 tests - infra lifecycle
python -m pytest tests/test_mcp_spike.py -v           # 4 tests - transport spike
python -m pytest tests/test_mcp_tools.py -v           # 18 tests - MCPs incl. real restart + hostile-input hardening
python -m pytest tests/test_agents_unit.py -v         # 34 tests - contracts, LLM validation, fallback, lifecycle
python -m pytest tests/test_agents_integration.py -v  # 7 tests - real agent processes + MCPs + Docker
python -m pytest tests/test_phase5.py -v              # 29 tests - identities, plan, intent token
python -m pytest tests/test_phase67.py -v             # 20 tests - delegation, governed invoke, audit mirror, Phase 8 probe
python -m pytest tests/test_security.py -v            # 20 tests - security-model hardening + reliability (offline)
python -m pytest tests/test_e2e.py -v                 # 1 test - full incident, real restart, RESOLVED
python -m pytest tests/                               # everything offline (138 tests; 3 live tests self-skip without a real key + registered MCPs)
python -m pytest tests/test_live_authorization.py -m live   # LIVE Phase 8/9 proof (real key + registered MCPs + Docker)
```

## Demo

```bash
scripts/run_incident.sh          # full incident, governed or unguarded
scripts/run_enforcement_demo.sh  # Phase 8/9: blocked diagnosis attempt + allowed recovery
```

`run_incident.sh` is one command with zero manual steps: it ensures infrastructure + MCPs + agents are up,
breaks `auth-api`, waits until `/health` reports unhealthy, submits the incident, and prints the final
result (RESOLVED) with the evidence count, diagnosis text, LLM source, the captured 4-step plan, the
intent-token status, the delegations (governed or unguarded), and the verification. The auth-api Docker
container genuinely restarts in the middle of the flow. No LLM key is required — with
`AEGISOPS_GEMINI_API_KEY` unset it prints a notice and uses the explicitly-marked deterministic test
fallback for the diagnosis. No ArmorIQ key is required either — without one it honestly reports 0
delegations and runs the unguarded baseline.

`run_enforcement_demo.sh` is the authorization demonstration: with a **real** `ARMORIQ_API_KEY` it runs the
same incident and shows both scenes in one deterministic run — Scene 1: the Diagnosis Agent's deliberate
`restart_service` attempt is **blocked** by ArmorIQ (proof: Docker `StartedAt` unchanged, audit row
`status=blocked`); Scene 2: the Remediation Agent's identical call is **allowed** (proof: `StartedAt`
changes, `/health` healthy, audit row `status=success`). The script fails honestly if governed mode cannot
activate — there is no fallback to the unguarded path during the demonstration.

---

See [PLAN.md](PLAN.md) for the full plan, [ARCHITECTURE.md](ARCHITECTURE.md) for the technical blueprint, and [CURRENT_STATE.md](CURRENT_STATE.md) for live project status.
