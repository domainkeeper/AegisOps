# Current State

## Project Status

**Phase 5 (ArmorIQ identities + explicit plan + intent token) — completed (2026-08-20).**

Phase 2 built the real incident infrastructure (`auth-api` + Docker + scripts). Phase 3 built the MCP layer
(three servers, four tools, real restart, official MCP SDK). Phase 4 built the four-agent system on top:
separate Commander/Log/Diagnosis/Remediation processes communicating over plain HTTP, with the Diagnosis
Agent's LLM-backed reasoning and the **unguarded** restart attempt that really restarts the container. One
complete incident now runs from break → investigation → diagnosis → restart → verification → RESOLVED with a
single command (`scripts/run_incident.sh`). Phase 5 added the four agent identities (Ed25519 keypairs +
email scopes) and the Commander's explicit 4-step execution plan captured with ArmorIQ (`capture_plan` →
`get_intent_token`). There is intentionally NO ArmorIQ enforcement yet — Phase 5 is intent, not delegation.

## Completed

- `PLAN.md`, `ARCHITECTURE.md`, `README.md`, `CURRENT_STATE.md` created (architecture phase).
- **Phase 1 (2026-08-19)** — ArmorIQ SDK verified; venv on Python 3.12.10; `armoriq/client_setup.py` identity
  foundation; `scripts/armoriq_smoke_test.py` (`--local-only` PASS; full mode reaches the network and fails
  clearly with `InvalidTokenException` on the placeholder key).
- **Phase 2 (2026-08-19) — real incident infrastructure** — `infrastructure/auth_api/` (FastAPI `/health`
  `/break` `/fix`, in-memory state), Dockerfile, root `docker-compose.yml`, six dev scripts,
  `tests/test_infrastructure.py` (5/5 pass). Real `docker restart auth-api` recovery proven.
- **Phase 3 (2026-08-19) — MCP tooling layer** — connectivity resolved (public HTTPS for registered MCPs;
  local = direct localhost), transport verified (official `mcp==2.0.0` SDK, Streamable HTTP, SSE), spike
  verified, three servers with four tools (incl. real `restart_service`), allowlist + no-shell security
  boundary, dev scripts, `tests/test_mcp_spike.py` (4/4) + `tests/test_mcp_tools.py` (13/13).
- **Phase 4 (2026-08-20) — unguarded multi-agent system**:
  - **Four real processes** — `agents/{commander,log_agent,diagnosis_agent,remediation_agent}.py`
    (ports 8094/8091/8092/8093), each independently executable (`python -m agents.<name>`), each with its
    own FastAPI/uvicorn HTTP endpoint and its own structured JSON log (`logs/agents/<name>.log`).
    Proven separate: `test_agents_are_separate_processes` spawns four and asserts four distinct PIDs.
  - **Communication** — plain HTTP request/response only (no brokers): Commander → Log Agent (investigation),
    Commander → Diagnosis Agent (diagnosis), Commander → Remediation Agent (remediation). Strict pydantic
    contracts (Incident, Investigation/Diagnosis/Remediation request+result, IncidentResult) in
    `agents/common.py`; peer responses validated on receipt; malformed input rejected.
  - **Log Agent** — `search_logs` via log-mcp; returns compact evidence + summary (not a raw dump).
  - **Diagnosis Agent** — `get_service_status` + `inspect_service_state` via diagnostic-mcp; reasons over
    the evidence with the LLM (or the explicitly-marked deterministic TEST fallback); and, because this is
    the **unguarded baseline**, deterministically attempts `restart_service("auth-api")` through
    remediation-mcp itself — **it succeeds** (real `docker restart`, `StartedAt` changes, health recovers).
    No `if agent == "diagnosis"` rule exists anywhere — pure agent→MCP connectivity.
  - **Remediation Agent** — health-checks first (idempotency: healthy → `noop: true`), then restarts via
    remediation-mcp; never shells out to docker.
  - **Commander** — deterministic orchestration with an incident context + timeline
    (RECEIVED → INVESTIGATING → DIAGNOSING → REMEDIATING → VERIFYING → RESOLVED/FAILED); never restarts
    the container itself; every failure produces a structured FAILED result (nothing swallowed).
  - **No shell execution** — agents call MCPs over HTTP only; static tests assert no `subprocess` /
    `os.system` / `shell=True` anywhere in `agents/`.
  - **Scripts** — `start_agents.sh`, `stop_agents.sh`, `run_incident.sh` (one-command full incident).
  - **Tests** — `tests/test_agents_unit.py`, `tests/test_agents_integration.py`, `tests/test_e2e.py`.
- **Phase 5 (2026-08-20) — ArmorIQ identities + explicit plan + intent token**:
  - **Gemini LLM (verified model)** — `agents/llm.py` now uses the official `google-genai` SDK against
    `gemini-3.5-flash-lite` (the current stable GA Flash-Lite model, verified against ai.google.dev,
    2026-08-20; `gemini-3.1-flash-lite` is deprecated in its favour). Structured output via
    `response_json_schema` + local pydantic re-validation (action/service allowlists still enforced
    client-side). Env: `AEGISOPS_GEMINI_API_KEY` (required for real calls), `AEGISOPS_LLM_MODEL` (default
    `gemini-3.5-flash-lite`). The OpenAI-compatible wrapper was removed. The deterministic TEST fallback
    (`AEGISOPS_LLM_FALLBACK=test`, `llm_source: "fallback"`) is unchanged and still never presented as a
    model result.
  - **Four agent identities** — `armoriq/client_setup.py` now provides the per-agent lifecycle: each role
    (`commander`, `log_agent`, `diagnosis_agent`, `remediation_agent`) gets its own Ed25519 keypair under
    `.keys/<role>/` (generated if missing, never regenerated, gitignored) and its own email scope
    (`AEGISOPS_<ROLE>_EMAIL`, defaulting to the PLAN §5 convention `<role>@aegisops.local`). Identity = one
    API key + per-request `for_user(email)` — the SDK's 0.6.10 model (`user_id`/`agent_id` deprecated).
    `scripts/ensure_identities.py` prints the four public keys + emails (private keys never printed).
  - **Explicit execution plan + intent token** — new `armoriq/plan.py` builds the explicit 4-step plan
    (search_logs → get_service_status → inspect_service_state → restart_service), validates it strictly
    (`PlanValidationError` on malformed plans), then performs the ArmorIQ handshake:
    `capture_plan()` (local) → `get_intent_token()` (network). The Commander runs this best-effort at the
    start of every `/incident`: the result is recorded on `IncidentResult` as `plan`,
    `intent_token_status` (`ready` | `error` | `not_configured`), `intent_token_expires_at`,
    `intent_token_error`. The token object itself is NEVER stored on the context, never serialized into
    responses, and never logged (it carries `raw_token`/`jwt_token`). A missing key is reported honestly as
    `not_configured` and never blocks the unguarded Phase 4 flow. `scripts/armoriq_plan_token.py` runs the
    same handshake standalone for account verification (prints only non-sensitive metadata).
  - **Tests** — `tests/test_phase5.py` (identity distinctness/round-trip/gitignore, email conventions,
    plan build/validation, capture/token handshake via stub clients, honest not_configured/error states,
    token material never serialized). E2E now asserts the 4-step plan + `intent_token_status` in the real
    flow. Full suite: **93 tests pass** (63 fast/offline + 30 Docker-dependent).
  - **Demo verified** — `scripts/run_incident.sh` (Git Bash) completed a real run: break → 503 → incident
    received → evidence (4 items) → fallback diagnosis → real restart → verification healthy → RESOLVED,
    with the 4-step plan captured and `intent_token_status: not_configured` (no real key on this machine).

## In Progress

- Nothing. Phase 5 is complete. Waiting for Phase 6 (ArmorIQ delegation) to start.

## Not Started

- ArmorIQ delegation (`delegate()` ×3 with correct `allowed_actions`; diagnosis token excludes
  `restart_service`) — Phase 6.
- `invoke()` wired into every MCP call + database (`schema.sql`, `db.py`, SQLite) — Phase 7.
- Authorization tests (blocked + allowed paths) — Phase 8.
- MCP registration on the ArmorIQ platform (needs a real API key + connectivity mode).
- Trail viewer (Phase 10).
- Real Gemini diagnosis has never been exercised end-to-end (no `AEGISOPS_GEMINI_API_KEY` on this machine).
- Real `get_intent_token` / `delegate` / `invoke` never exercised end-to-end (no real `ARMORIQ_API_KEY`).

## Architecture Decisions

| # | Decision |
|---|---|
| 1 | Four separate agent processes, each with its own Ed25519 keypair and its own `ArmorIQClient` — implemented Phase 5 |
| 2 | Inter-agent transport: simple HTTP (`/run_task` endpoint per agent) — implemented Phase 4 |
| 3 | `capture_plan()` receives an explicit plan artifact we construct (SDK does not invent plans) — implemented Phase 5 |
| 4 | The unauthorized-restart attempt is deterministic (hardcoded control flow); LLM only produces the diagnosis rationale — implemented Phase 4 |
| 5 | SQLite is a thin mirror of ArmorIQ results; ArmorIQ is the source of truth for authorization |
| 6 | **CHANGED:** MCPs must speak JSON-RPC 2.0 over HTTP/SSE and be registered on the platform; plain-HTTP fallback removed (verified against MCP Format Requirements) |
| 7 | Commander dispatch may be hardcoded if time is short; the Diagnosis LLM call is the only "SHOULD HAVE" AI piece |
| 8 | Secrets only in `.env` (gitignored); no Vault/KMS |
| 9 | No generic agent framework; build exactly the PLAN §1 scenario |
| 10 | Trail viewer: terminal output default; minimal HTML page only if Phase 10 has time |
| 11 | **NEW:** venv on Python 3.12 — `armoriq-sdk` requires `>=3.10,<3.14` |
| 12 | **NEW:** per-agent `user_email` scopes (`commander@aegisops.local`, etc.) + per-process keypairs carry agent identity under the SDK's one-key/for_user model — implemented Phase 5 |
| 13 | **NEW (Phase 2):** single root `docker-compose.yml`; `auth-api` uses in-memory state so a real restart is observable; Postgres cut (cosmetic only) |
| 14 | **NEW (Phase 2):** future Remediation MCP exposes narrowly scoped `restart_service("auth-api")` — fixed mapping, no generic `run_shell(command)` |
| 15 | **NEW (Phase 3):** MCP layer uses the official MCP Python SDK (`mcp==2.0.0`), Streamable HTTP, SSE responses — the wire format matches ArmorIQ's MCP Format Requirements exactly |
| 16 | **NEW (Phase 3):** local package named `mcp_servers/`, not `mcp/` (shadows the official SDK package) |
| 17 | **NEW (Phase 3):** local dev = direct localhost MCP access; ArmorIQ-connected = public HTTPS tunnel (deployment concern) or self-hosted ArmorIQ stack; hosted proxy cannot reach localhost |
| 18 | **NEW (Phase 3):** `inspect_config` → `inspect_service_state` (read-only runtime state, redacted) — safer and more diagnostic than a config/env dump |
| 19 | **NEW (Phase 4):** agents are FastAPI/uvicorn processes; agent + MCP URLs env-overridable (`AEGISOPS_*_URL`) |
| 20 | **NEW (Phase 4):** LLM = minimal OpenAI-compatible wrapper (httpx only), env credentials, no provider abstraction framework |
| 21 | **NEW (Phase 4):** no LLM key + `AEGISOPS_LLM_FALLBACK=test` → explicitly-marked deterministic fallback (`llm_source: "fallback"`); otherwise a clear error — never a fake model diagnosis |
| 22 | **NEW (Phase 4):** unguarded baseline — Diagnosis Agent performs the restart itself through remediation-mcp; no in-code allow/deny rules; the ArmorIQ phases turn the exact same call into the blocked demonstration |
| 23 | **NEW (Phase 5):** LLM = official `google-genai` SDK, model `gemini-3.5-flash-lite` (current stable GA, verified 2026-08-20); `AEGISOPS_GEMINI_API_KEY` + `AEGISOPS_LLM_MODEL`; strict `response_json_schema` + local re-validation |
| 24 | **NEW (Phase 5):** the intent-token handshake (`capture_plan` → `get_intent_token`) is best-effort on `/incident`: status is recorded, the token is never stored/serialized/logged, and a missing key (`not_configured`) or failure never blocks the unguarded flow |

## Verified SDK Details

All verified against docs.armoriq.ai + installed `armoriq-sdk 0.6.10` (signatures introspected), 2026-08-19/20:

- Package `armoriq-sdk` (PyPI), ships the `armoriq` CLI; Python `>=3.10,<3.14`; v0.6.10 installed.
- `ArmorIQClient(api_key=...)`, env `ARMORIQ_API_KEY`, or `~/.armoriq/credentials.json` (from `armoriq login`);
  `from_config("armoriq.yaml")`; one-key + `for_user(email)` identity model (`user_id`/`agent_id` deprecated).
- `capture_plan(llm, prompt, plan, metadata=None) -> PlanCapture` — local, no network; plan must contain `steps`.
  In 0.6.10 PlanCapture exposes only plan/llm/prompt/metadata (no plan_hash/merkle_root on the object).
- `get_intent_token(plan_capture, policy=None, validity_seconds=60.0) -> IntentToken` — network; token carries
  `plan_hash`, `step_proofs`, `expires_at`, etc. The token object is SENSITIVE (`raw_token`/`jwt_token`) and is
  never logged or serialized in this project.
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

## Known Unknowns / Limitations (Phase 5)

- **Real Gemini diagnosis not exercised** — no `AEGISOPS_GEMINI_API_KEY` on this machine; all runs used the
  explicitly-marked deterministic test fallback (`llm_source: "fallback"`). The Gemini path (google-genai
  client, `response_json_schema`, validation, failure behavior) is unit-tested via stubs, not live-tested.
- **Real ArmorIQ handshake not exercised** — no real `ARMORIQ_API_KEY`; `get_intent_token()` has never been
  called live. The handshake is built against the verified SDK signatures and fails honestly
  (`intent_token_status: not_configured/error`) without one.
- Which exception a delegated-token scope violation raises (`IntentMismatchException` vs `PolicyBlockedException`)
  — needs a runtime test with a real API key (Phase 8).
- Whether `agent_id` still has any effect in 0.6.10 despite deprecation.
- Which tunnel provider (if any) will be used when the hosted proxy must reach the MCPs — deployment concern,
  not yet decided.
- Commander keeps one incident in memory (no persistence; single-incident demo scope by design).
- Agent logs are per-process files under `logs/agents/`; no centralized observability (by design).

## Next Steps

1. **Phase 5 — ArmorIQ identities + plan — DONE** (keypairs, emails, explicit 4-step plan, capture + token
   handshake, Gemini LLM).
2. Phase 6 — ArmorIQ delegation (`delegate()` ×3 with correct `allowed_actions`; diagnosis token has no
   `restart_service`).
3. Phase 7 — wire `invoke()` into every MCP call + database (`schema.sql`, `db.py`, SQLite).
4. Phase 8 — the violation + enforcement: Diagnosis Agent's restart attempt **blocked**; audit row.
5. Phase 9 — authorized remediation: post-diagnosis delegation → Remediation Agent's restart **allowed**.
6. Phase 10 — testing + audit trail + demo polish.

## Blockers

- No real `ARMORIQ_API_KEY` yet — needed for Phases 6-9 (token issuance/delegation/invoke), the MCP
  registration flow, and the Phase 8 blocked-path exception type. Phase 5 works without it (local capture +
  honest `not_configured`).
- No `AEGISOPS_GEMINI_API_KEY` on this machine — needed to exercise a real Gemini diagnosis.
- Hosted-proxy MCP invocation additionally requires the connectivity mode (tunnel vs self-hosted proxy) to be
  exercised end-to-end.

## Definition of Ready (Phase 6 — ArmorIQ delegation)

- [x] Phase 5 complete (identities + explicit plan + intent-token handshake implemented; 93 tests pass)
- [ ] Real `ARMORIQ_API_KEY` obtained
- [ ] MCPs registered on the platform with exact names (`log-mcp`, `diagnostic-mcp`, `remediation-mcp`)
- [ ] MCP connectivity mode exercised (tunnel or self-hosted proxy)