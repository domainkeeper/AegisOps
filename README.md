# AegisOps

**Autonomous incident response with cryptographically enforced agent authority.**

*Track: ArmorIQ — Problem 2: "Who authorized that?"*

> **CAPABLE ≠ AUTHORIZED.**

---

## Problem

Autonomous agents can now investigate and act on real infrastructure. But capability is not the same as
authority: an agent that *can* restart a service is not the same as an agent that *may* restart it.
When agents make real-world changes, the question that matters is: **who authorized that?**

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

## Agents

| Agent | Identity | Authority (delegated `allowed_actions`) |
|---|---|---|
| Commander | own Ed25519 keypair + ArmorIQ client | Root intent token over the full captured plan; the only agent that calls `delegate()` |
| Log Agent | own keypair + client | `search_logs` |
| Diagnosis Agent | own keypair + client | `get_service_status`, `inspect_config` — **no restart** |
| Remediation Agent | own keypair + client | `restart_service` (granted by Commander only after diagnosis) |

Each agent is a separate process with its own keypair. No agent can self-escalate.

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

## Demo Scenario

1. `auth-api` container is broken (`POST /break`)
2. Commander captures the plan and delegates scoped tokens
3. Log + Diagnosis Agents investigate (read-only)
4. Diagnosis Agent's LLM concludes "restart needed" — and attempts the restart with its own token → **blocked**, logged to the audit trail
5. Commander explicitly delegates restart authority → Remediation Agent restarts → container heals (`/health` green)
6. The full audit trail (plan → delegations → blocked → allowed) is shown

## Planned Stack

- **Language:** Python (separate agent processes)
- **Authorization:** ArmorIQ SDK (`armoriq-sdk`) + Ed25519 keypairs (`cryptography`)
- **Infrastructure:** Docker (`auth-api` FastAPI service)
- **MCPs:** three small tool services (Log, Diagnostic, Remediation)
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
- **Full agent workflow not implemented yet.**

## Current Status

| Area | Status |
|---|---|
| Plan | **Implemented** (`PLAN.md`) |
| Architecture | **Implemented** (`ARCHITECTURE.md`) |
| Python environment + SDK install | **Implemented** (verified on Python 3.12, `armoriq-sdk 0.6.10`) |
| Client/identity foundation | **Implemented** (`armoriq/client_setup.py`, keypair round-trip verified) |
| SDK smoke test | **Implemented** (local path passes; network path needs a real key) |
| Docker infrastructure | **Planned** |
| MCP tools | **Planned** (wire format verified) |
| Agent processes | **Planned** |
| ArmorIQ plan/delegate/invoke wiring | **Planned** |
| Database | **Planned** |
| Tests | **Planned** |
| Demo scripts | **Planned** |

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

## Demo

_Planned._ Will cover: `scripts/start_env.sh`, `scripts/break_service.sh`, `scripts/run_incident.sh`, `scripts/reset_demo.sh` — and what to expect at each step.

---

See [PLAN.md](PLAN.md) for the full plan, [ARCHITECTURE.md](ARCHITECTURE.md) for the technical blueprint, and [CURRENT_STATE.md](CURRENT_STATE.md) for live project status.