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
Commander Agent ──── capture_plan() → get_intent_token() → delegate() × 3
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

Four genuinely separate processes communicating over plain HTTP. This is the current **unguarded** state
(Phase 4): every agent can reach every capability, and the Diagnosis Agent's restart attempt **succeeds**.
The ArmorIQ enforcement phases will convert exactly that path into the blocked demonstration.

| Agent | Process (port) | Talks to (HTTP → MCP) | Role |
|---|---|---|---|
| Commander | `agents/commander.py` (8094) | all three agents, `diagnostic-mcp` | Orchestrator: receives incident, drives investigation → diagnosis → remediation → verification, marks RESOLVED/FAILED |
| Log Agent | `agents/log_agent.py` (8091) | `log-mcp` | Fetches log evidence, returns a compact structured summary |
| Diagnosis Agent | `agents/diagnosis_agent.py` (8092) | `diagnostic-mcp`, `remediation-mcp` | Inspects state, reasons over evidence (LLM), and in this unguarded phase performs the remediation itself |
| Remediation Agent | `agents/remediation_agent.py` (8093) | `diagnostic-mcp`, `remediation-mcp` | Executes the restart through the MCP (idempotency guard: healthy service → no-op) |

Agent → MCP → Docker. No agent ever runs `docker` directly; there is no shell tool anywhere.

**LLM (Diagnosis Agent only):** an OpenAI-compatible wrapper (`agents/llm.py`) — `AEGISOPS_LLM_API_KEY`,
`AEGISOPS_LLM_BASE_URL`, `AEGISOPS_LLM_MODEL` (default `gpt-4o-mini`). The model interprets evidence and
returns a strict JSON diagnosis which is validated against a schema + an action allowlist
(`none` / `restart_service` only). The model never executes anything. With no key configured, the agent
fails clearly — or uses the **explicitly-marked deterministic TEST fallback** when `AEGISOPS_LLM_FALLBACK=test`
is set (always labelled `llm_source: "fallback"`, never presented as model-generated).

## ArmorIQ's Role

ArmorIQ is the source of truth for authorization:

- `capture_plan()` — Commander captures the explicit incident plan (goal + steps)
- `get_intent_token()` — plan is canonicalized, hashed, Merkle-proved, and signed
- `delegate()` — Commander mints scoped, time-limited tokens bound to each child agent's public key
- `invoke()` — every tool call is verified at the ArmorIQ Proxy; out-of-scope calls are **blocked**

## Core Security Concept

The Diagnosis Agent attempts `restart_service("auth-api")`. The Remediation Agent also calls
`restart_service("auth-api")`. Same action. Same parameters. Same tool.

The first is **blocked** by ArmorIQ. The second **succeeds**. The only difference is which
cryptographically-signed token was presented — enforcement is keyed on the token's allow-list and signed
plan proof, never on the text of the request and never on what an LLM intends.

## Incident Scenario (current, unguarded)

1. `auth-api` container is broken (`POST /break`) — `/health` → 503
2. The incident is submitted to the Commander (`POST /incident`)
3. Commander asks the Log Agent to investigate → log evidence
4. Commander sends the evidence to the Diagnosis Agent → service state + LLM/fallback reasoning
5. Diagnosis concludes a restart is needed — and (unguarded baseline) **attempts `restart_service("auth-api")` itself** → succeeds
6. Commander asks the Remediation Agent to confirm → service already healthy, idempotent no-op
7. Commander verifies `/health` and marks the incident **RESOLVED**

This exact unguarded baseline is the proof that the workflow works before authorization is inserted. In the
ArmorIQ phases the Diagnosis Agent's restart attempt will be **blocked** (its delegated token has no
`restart_service` authority) and only the Remediation Agent's separately-delegated call will succeed.

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
  complete incident flow over HTTP; the Diagnosis Agent reasons (LLM or marked fallback) and performs the
  unguarded restart; the container really restarts and the incident reaches RESOLVED. 39 agent tests pass.
- **ArmorIQ enforcement not implemented yet** — that is the next phase.

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
| Multi-agent orchestration (unguarded) | **Implemented** (4 processes, HTTP contracts, LLM diagnosis, real restart; 39 tests incl. full E2E) |
| ArmorIQ plan/delegate/invoke wiring | **Planned** |
| Database | **Planned** |
| Demo scripts | **Implemented** (`run_incident.sh` runs one complete incident end to end) |

## Setup

```bash
# Requires Python 3.10 - 3.13 (armoriq-sdk does not support 3.14)
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt

# Configure
copy .env.example .env            # Windows
# then set ARMORIQ_API_KEY=ak_... (or run `armoriq login`)
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
# Set AEGISOPS_LLM_API_KEY first for real LLM diagnosis; without it the
# Diagnosis Agent uses the explicitly-marked test fallback (set
# AEGISOPS_LLM_FALLBACK=test) or fails clearly.

# Run one complete incident end to end (no manual steps):
scripts/run_incident.sh     # break -> investigate -> diagnose -> restart -> verify -> RESOLVED

# Automated verification (from repo root, requires running Docker):
python -m pytest tests/test_infrastructure.py -v      # 5 tests - infra lifecycle
python -m pytest tests/test_mcp_spike.py -v           # 4 tests - transport spike
python -m pytest tests/test_mcp_tools.py -v           # 13 tests - MCPs incl. real restart
python -m pytest tests/test_agents_unit.py -v         # 31 tests - contracts, LLM validation, fallback
python -m pytest tests/test_agents_integration.py -v  # 7 tests - real agent processes + MCPs + Docker
python -m pytest tests/test_e2e.py -v                 # 1 test - full incident, real restart, RESOLVED
python -m pytest tests/                               # everything (61 tests)
```

## Demo

```bash
scripts/run_incident.sh
```

One command, zero manual steps: it ensures infrastructure + MCPs + agents are up, breaks `auth-api`, waits
until `/health` reports unhealthy, submits the incident, and prints the final result (RESOLVED) with the
evidence count, diagnosis text, LLM source, and verification. The auth-api Docker container genuinely
restarts in the middle of the flow. No LLM key is required — with `AEGISOPS_LLM_API_KEY` unset it prints a
notice and uses the explicitly-marked deterministic test fallback for the diagnosis.

---

See [PLAN.md](PLAN.md) for the full plan, [ARCHITECTURE.md](ARCHITECTURE.md) for the technical blueprint, and [CURRENT_STATE.md](CURRENT_STATE.md) for live project status.
