# Current State

## Project Status

**Phase 3 (MCP tooling layer) — completed (2026-08-19).**

Phase 2 built the real incident infrastructure (`auth-api` + Docker + scripts). Phase 3 built the MCP layer on
top of it: a transport spike was verified first, then three MCP servers (`log-mcp`, `diagnostic-mcp`,
`remediation-mcp`) exposing four narrowly scoped tools, using the official MCP Python SDK
(`mcp==2.0.0`, Streamable HTTP, SSE — the exact wire format the ArmorIQ proxy requires). The
`restart_service("auth-api")` tool performs a **real Docker restart** and is allowlist-scoped; there is no
generic shell tool anywhere. ArmorIQ connectivity was resolved (see below). Agents are NOT implemented yet.

## Completed

- `PLAN.md`, `ARCHITECTURE.md`, `README.md`, `CURRENT_STATE.md` created (architecture phase).
- **Phase 1 (2026-08-19)** — ArmorIQ SDK verified; venv on Python 3.12.10; `armoriq/client_setup.py` identity
  foundation; `scripts/armoriq_smoke_test.py` (`--local-only` PASS; full mode reaches the network and fails
  clearly with `InvalidTokenException` on the placeholder key).
- **Phase 2 (2026-08-19) — real incident infrastructure** — `infrastructure/auth_api/` (FastAPI `/health`
  `/break` `/fix`, in-memory state), Dockerfile, root `docker-compose.yml`, six dev scripts,
  `tests/test_infrastructure.py` (5/5 pass). Real `docker restart auth-api` recovery proven.
- **Phase 3 (2026-08-19) — MCP tooling layer**:
  - **Connectivity resolved** — official ArmorIQ docs verified: registered MCPs need a public HTTPS URL;
    the hosted proxy CANNOT reach localhost. Local development talks to MCPs directly on localhost; the
    ArmorIQ-connected modes are (a) public HTTPS tunnel (deployment concern, no provider hardcoded) or
    (b) the officially supported self-hosted ArmorIQ stack (`use_production=False` / `ARMORIQ_ENV=local`)
    which can reach localhost MCPs. See ARCHITECTURE.md §7.2.
  - **Transport verified** — official MCP Python SDK `mcp==2.0.0` (current stable), Streamable HTTP with SSE
    responses. Raw wire probe confirms ArmorIQ-compatible format (`text/event-stream`, `event: message`,
    JSON-RPC 2.0 `initialize`/`tools/list`/`tools/call`). 2025-era sessions need `Mcp-Session-Id` echo;
    the SDK `Client` does this automatically, dev scripts do it explicitly.
  - **Minimal spike first** — `mcp_servers/spike.py` (`health_check` tool, port 8090) verified end-to-end
    (client → JSON-RPC → discovery → invocation → real auth-api result) before building the real servers.
  - **Three MCP servers** — `mcp_servers/{log_mcp,diagnostic_mcp,remediation_mcp}.py` on ports 8081-8083:
    `search_logs` (read-only, docker logs), `get_service_status` + `inspect_service_state` (read-only,
    redacted), `restart_service` (write, real `docker restart`, allowlist-scoped). Tool `inspect_config`
    from the plan was renamed to `inspect_service_state` (runtime state is safer and more useful than a
    config/env dump; surgical rename applied across docs).
  - **Security boundary** — service names resolve through an explicit `SERVICES` allowlist only; subprocess
    calls use fixed argument lists (no `shell=True`); no `run_shell`/`docker_exec`/`run_command` tool exists.
  - **Dev scripts** — `start_mcps.sh`, `check_mcps.sh`, `discover_tools.sh`, `call_mcp_tool.sh`,
    `stop_mcps.sh`, plus `scripts/spike_probe.py` client probe.
  - **Tests** — `tests/test_mcp_spike.py` (4/4) + `tests/test_mcp_tools.py` (13/13), all passing: transport
    wire format, tool discovery, structured results, unknown/malicious service rejection, missing-param
    rejection, and the centerpiece `test_remediation_real_restart_changes_started_at_and_recovers`
    (break → `restart_service("auth-api")` via real MCP client → **real Docker restart** → `StartedAt`
    changes → `/health` healthy).
  - Package named `mcp_servers/` (not `mcp/`) because the official SDK ships a `mcp` package — a local
    `mcp/` directory shadows it (hit during the spike).

## In Progress

- Nothing. Phase 3 is complete. Waiting for Phase 4 (unguarded agents) to start.

## Not Started

- Agent processes (Commander, Log, Diagnosis, Remediation) + HTTP transport (Phase 4).
- ArmorIQ integration beyond the foundation (plan capture/token/delegate/invoke wiring, agent keypair
  provisioning, per-agent `user_email` scopes; Phases 5-9).
- Database (`schema.sql`, `db.py`, SQLite) — Phase 7.
- Authorization tests (blocked + allowed paths) — Phase 8.
- MCP registration on the ArmorIQ platform (needs a real API key + connectivity mode).
- Trail viewer (Phase 10).

## Architecture Decisions

| # | Decision |
|---|---|
| 1 | Four separate agent processes, each with its own Ed25519 keypair and its own `ArmorIQClient` |
| 2 | Inter-agent transport: simple HTTP (`/run_task` endpoint per agent) |
| 3 | `capture_plan()` receives an explicit plan artifact we construct (SDK does not invent plans) |
| 4 | The unauthorized-restart attempt is deterministic (hardcoded control flow); LLM only produces the diagnosis rationale |
| 5 | SQLite is a thin mirror of ArmorIQ results; ArmorIQ is the source of truth for authorization |
| 6 | **CHANGED:** MCPs must speak JSON-RPC 2.0 over HTTP/SSE and be registered on the platform; plain-HTTP fallback removed (verified against MCP Format Requirements) |
| 7 | Commander dispatch may be hardcoded if time is short; the Diagnosis LLM call is the only "SHOULD HAVE" AI piece |
| 8 | Secrets only in `.env` (gitignored); no Vault/KMS |
| 9 | No generic agent framework; build exactly the PLAN §1 scenario |
| 10 | Trail viewer: terminal output default; minimal HTML page only if Phase 10 has time |
| 11 | **NEW:** venv on Python 3.12 — `armoriq-sdk` requires `>=3.10,<3.14` |
| 12 | **NEW:** per-agent `user_email` scopes (`commander@aegisops.local`, etc.) + per-process keypairs carry agent identity under the SDK's one-key/for_user model |
| 13 | **NEW (Phase 2):** single root `docker-compose.yml`; `auth-api` uses in-memory state so a real restart is observable; Postgres cut (cosmetic only) |
| 14 | **NEW (Phase 2):** future Remediation MCP exposes narrowly scoped `restart_service("auth-api")` — fixed mapping, no generic `run_shell(command)` |
| 15 | **NEW (Phase 3):** MCP layer uses the official MCP Python SDK (`mcp==2.0.0`), Streamable HTTP, SSE responses — the wire format matches ArmorIQ's MCP Format Requirements exactly |
| 16 | **NEW (Phase 3):** local package named `mcp_servers/`, not `mcp/` (shadows the official SDK package) |
| 17 | **NEW (Phase 3):** local dev = direct localhost MCP access; ArmorIQ-connected = public HTTPS tunnel (deployment concern) or self-hosted ArmorIQ stack; hosted proxy cannot reach localhost |
| 18 | **NEW (Phase 3):** `inspect_config` → `inspect_service_state` (read-only runtime state, redacted) — safer and more diagnostic than a config/env dump |

## Verified SDK Details

All verified against docs.armoriq.ai + installed `armoriq-sdk 0.6.10` (signatures introspected), 2026-08-19:

- Package `armoriq-sdk` (PyPI), ships the `armoriq` CLI; Python `>=3.10,<3.14`; v0.6.10 installed.
- `ArmorIQClient(api_key=...)`, env `ARMORIQ_API_KEY`, or `~/.armoriq/credentials.json` (from `armoriq login`);
  `from_config("armoriq.yaml")`; one-key + `for_user(email)` identity model (`user_id`/`agent_id` deprecated).
- `capture_plan(llm, prompt, plan, metadata=None) -> PlanCapture` — local, no network; plan must contain `steps`.
  In 0.6.10 PlanCapture exposes only plan/llm/prompt/metadata (no plan_hash/merkle_root on the object).
- `get_intent_token(plan_capture, policy=None, validity_seconds=60.0) -> IntentToken` — network; token carries
  `plan_hash`, `step_proofs`, `expires_at`, etc.
- `invoke(mcp, action, intent_token, params=None, merkle_proof=None, user_email=None) -> MCPInvocationResult` —
  network; `merkle_proof` auto-generated; result fields `mcp/action/result/status/execution_time/verified/metadata`.
- `delegate(intent_token, delegate_public_key, validity_seconds=3600, allowed_actions=None, target_agent=None,
  subtask=None) -> DelegationResult` — network; `delegate_public_key` is raw-bytes-hex Ed25519 public key.
- Blocked actions are exceptions (`IntentMismatchException`, `PolicyBlockedException`, `TokenExpiredException`,
  `InvalidTokenException`, `DelegationException`, `MCPInvocationException`; base `ArmorIQException`).
- Proxy is a hosted, stateless reverse proxy; MCPs must be pre-registered (dashboard or `armoriq register`) and
  speak JSON-RPC 2.0 + SSE.
- **MCP connectivity (Phase 3):** registered MCPs require a public HTTPS URL; hosted proxy cannot reach
  localhost; self-hosting the ArmorIQ stack is officially supported; local MCP development needs no ArmorIQ.
- **MCP transport (Phase 3):** official MCP Python SDK `mcp==2.0.0` (Streamable HTTP, SSE responses,
  2025-era `initialize`/`tools/list`/`tools/call` + 2026-era protocol served from one server).

## Known Unknowns

- Which exception a delegated-token scope violation raises (`IntentMismatchException` vs `PolicyBlockedException`)
  — needs a runtime test with a real API key (Phase 8).
- Full network path (`get_intent_token` → `delegate` → `invoke`) with a live API key — not tested (no real key).
- Whether `agent_id` still has any effect in 0.6.10 despite deprecation.
- Which tunnel provider (if any) will be used when the hosted proxy must reach the MCPs — deployment concern,
  not yet decided.
- Whether the ArmorIQ proxy's `initialize`/session handling matches the SDK's sessionful streamable HTTP
  (the 2025-era handshake was verified locally; the proxy-side handshake is unverifiable without a real key).

## Next Steps

1. **Phase 4 — Agents, unguarded**: Commander/Log/Diagnosis/Remediation as separate processes calling the MCPs
   directly (no ArmorIQ yet) over HTTP transport; Diagnosis Agent's LLM call decides "restart needed";
   end-to-end: incident → logs → diagnosis → restart → recovery.
2. Phase 5 — ArmorIQ identities + plan (`capture_plan()` → `get_intent_token()`).
3. Phase 6 — ArmorIQ delegation (`delegate()` ×3 with correct `allowed_actions`).
4. Phase 7 — wire `invoke()` into every MCP call + database (`schema.sql`, `db.py`, SQLite).
5. Phase 8 — the violation + enforcement (blocked `restart_service` + audit row).

## Blockers

- No real `ARMORIQ_API_KEY` yet — needed to verify the network path (token issuance/delegation/invoke), the
  MCP registration flow, and the Phase 8 blocked-path exception type. Everything else proceeds without it.
- Hosted-proxy MCP invocation additionally requires the connectivity mode (tunnel vs self-hosted proxy) to be
  exercised end-to-end.

## Definition of Ready (Phase 4 — unguarded agents)

- [x] Phase 2 complete (auth-api healthy/broken states provable)
- [x] Phase 3 complete (MCP transport verified; three servers + four tools; real restart proven)
- [ ] No dependency on ArmorIQ for Phase 4 — agents call MCPs directly over HTTP

Definition of Ready (Phase 5+ — ArmorIQ wiring):

- [ ] Real `ARMORIQ_API_KEY` obtained
- [ ] MCPs registered on the platform with exact names (`log-mcp`, `diagnostic-mcp`, `remediation-mcp`)
- [ ] MCP connectivity mode exercised (tunnel or self-hosted proxy)