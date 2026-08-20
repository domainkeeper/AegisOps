# Current State

## Project Status

**Phase 6 + 7 (ArmorIQ delegation + governed invocation + audit mirror) — completed (2026-08-20).**
**Phase 8 + 9 (enforcement demonstration: blocked diagnosis attempt / allowed remediation) — code +
offline tests completed (2026-08-20); live verification pending MCP registration.**

Phase 2 built the real incident infrastructure (`auth-api` + Docker + scripts). Phase 3 built the MCP layer
(three servers, four tools, real restart, official MCP SDK). Phase 4 built the four-agent system on top:
separate Commander/Log/Diagnosis/Remediation processes communicating over plain HTTP, with the Diagnosis
Agent's LLM-backed reasoning and the **unguarded** restart attempt that really restarts the container. One
complete incident now runs from break → investigation → diagnosis → restart → verification → RESOLVED with a
single command (`scripts/run_incident.sh`). Phase 5 added the four agent identities (Ed25519 keypairs +
email scopes) and the Commander's explicit 4-step execution plan captured with ArmorIQ (`capture_plan` →
`get_intent_token`). Phase 6 added the authority model: the Commander delegates three narrowly-scoped
authorities from the root intent token (`delegate_subtree()` ×3, live-verified mechanism, diagnosis scope
deliberately excludes `restart_service`). Phase 7 wired the governed path: when a child holds a delegation
it invokes its MCP actions **through ArmorIQ** (`invoke()` → proxy → MCP), and every governed/audit-relevant
event is mirrored into a local SQLite audit mirror (safe metadata only; ArmorIQ stays the source of truth).
Phase 8 turned the Diagnosis Agent's restart attempt into a deliberate governed probe: it submits
`restart_service("auth-api")` with its own read-only authority, ArmorIQ **blocks** it, the outcome is
recorded on the `DiagnosisResult` (`governed_restart_attempted/blocked/error/result`) and audited
(`status="blocked"`) — never fatal, never faked, no keyword filtering, no local policy layer pretending to
be ArmorIQ. Phase 9: the Remediation Agent performs the identical call with its own authority — ArmorIQ
**allows** it and the container really restarts. With no ArmorIQ credentials the entire system runs the
unguarded Phase 4 baseline unchanged and reports it honestly (`delegations: []`, `governed: false`).

**Live-verified against the real ArmorIQ platform (2026-08-20):** the `.env` `ARMORIQ_API_KEY` is a real,
working `ak_live_...` key — real intent tokens were issued (`scripts/armoriq_plan_token.py`) and real
delegations were minted. The legacy `delegate()` path is DEAD on this platform (400 `parentToken is
required`); `delegate_subtree()` is the working mechanism. `invoke()` currently cannot reach the MCPs
(`Internal Proxy Error`) because no MCPs are registered yet — the user will register `log-mcp`,
`diagnostic-mcp`, `remediation-mcp` with public tunnel URLs; the live blocked/allowed run then completes
Phase 8/9 (`tests/test_live_authorization.py`, self-skipping; `scripts/run_enforcement_demo.sh`).

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
    flow.
  - **Demo verified** — `scripts/run_incident.sh` (Git Bash) completed a real run: break → 503 → incident
    received → evidence (4 items) → fallback diagnosis → real restart → verification healthy → RESOLVED,
    with the 4-step plan captured and `intent_token_status: not_configured` (no real key on this machine).
- **Phase 6 (2026-08-20) — ArmorIQ delegation (the authority model)**:
  - **`armoriq/delegation.py`** — the central authority matrix (an Architecture Decision, enforced in code
    + tests): `log_agent → ["search_logs"]`, `diagnosis_agent → ["get_service_status",
    "inspect_service_state"]`, `remediation_agent → ["restart_service"]`. `create_delegations()` verifies
    the scope against `_VERIFIED_SCOPES` **before any network call** (`ScopeValidationError`), binds each
    delegation to the child's own Ed25519 public key (`ensure_keypair`), and calls the **live-verified**
    `delegate_subtree(intent_token, delegate_public_key=..., subtree_path=..., validity_seconds=...,
    target_agent=...)` — each delegation is a SUBTREE of the captured plan (`subtree_path_for()`: log
    `"0"`, diagnosis `"1,2"`, remediation `"3"`). The legacy `delegate()` payload is rejected by the live
    platform (400 `parentToken is required`) and is not used. Delegated-token validity:
    `AEGISOPS_DELEGATION_VALIDITY` (default 300s, shorter than the root token per SDK design).
  - **Commander delegation** — `IncidentContext` keeps the root token in memory only (`_root_token`); after
    a successful intent handshake the Commander delegates to all three children (`_delegate_intents`,
    best-effort: any failure records `delegation_error` + audit row and the incident continues **unguarded**
    — never faked, never aborted). `IncidentResult` exposes only safe metadata: `delegations` (agent,
    delegation_id, allowed_actions, expires_at, status), `delegation_error`, `governed`.
  - **Child authority** — each dispatch carries a `DelegatedAuthority` payload (delegation_id + scope +
    serialized token) over the local agent HTTP channel to the owning child only; never logged, never
    serialized in responses.
- **Phase 7 (2026-08-20) — governed invocation + audit mirror**:
  - **`invoke_governed()`** (`agents/common.py`) — the single governed call path: `IntentToken.model_validate`
    → `client.invoke(mcp, action, token, params, user_email=<child email>)` → parse the verified
    `MCPInvocationResult`. ArmorIQ rejections are never swallowed: the verified exception type is recorded
    (`ArmorIQException` base caught, `type(exc).__name__` kept, no hardcoded block class), an audit row is
    written (`blocked` for `PolicyBlockedException`, `error` otherwise), and an `AgentError` surfaces into
    the incident result. Local SDK fail-closed checks (`TokenExpiredException`, `IntentMismatchException`,
    missing proofs) behave the same way.
  - **Mode selection — no env flag** — a request carries `authority` → the agent uses the governed path;
    otherwise the Phase 4 unguarded direct-MCP path runs unchanged (regression-preserving by construction).
    Governed mode: Log Agent calls `log-mcp.search_logs` through ArmorIQ; Diagnosis Agent calls
    `diagnostic-mcp.get_service_status` + `inspect_service_state` through ArmorIQ; Remediation Agent calls
    `remediation-mcp.restart_service` through ArmorIQ (its health-check probe stays a direct read-only MCP
    call).
  - **Audit mirror** — `database/audit.py` + `database/__init__.py`: SQLite `audit_events` table
    (incident_id, agent, parent_agent, action, status, delegation_id, error_type, detail, created_at), env
    `AEGISOPS_AUDIT_DB` (default `database/audit.db`, gitignored). Safe metadata only: the store refuses
    tokens/keys/signatures (`_FORBIDDEN_FIELDS`, asserted by tests). Writes are best-effort and never break
    the incident flow. This is a thin local mirror — ArmorIQ remains the source of truth.
  - **Tests** — `tests/test_phase67.py` (20 tests): exact subtree scopes ("0"/"1,2"/"3"), diagnosis excludes
    `restart_service`, remediation includes it, delegation bound to each child's own public key, safe
    metadata only, scope validation blocks before any network call, delegation failure → unguarded +
    recorded, token material never in `IncidentResult`, governed success propagates MCP results,
    blocked/invalid-token surface + audit rows with the verified error type, audit mirror never stores
    secrets, Phase 8 probe (blocked/unreachable/unexpected-allowance all recorded, never fatal), E2E asserts
    `delegations: []` + `governed: false` on the no-key run. Full suite: **113 tests pass** (offline;
    `tests/test_live_authorization.py` adds 3 live tests that self-skip without the live prerequisites).
  - **Test hygiene** — the suite now reclaims the agent/MCP ports at session start so stale processes left
    by demo scripts can never poison results.
- **Phase 8 (2026-08-20) — the violation + enforcement (Diagnosis Agent's blocked restart attempt)**:
  - `attempt_governed_restart()` in `agents/diagnosis_agent.py` — the deliberate probe: the Diagnosis Agent
    submits `restart_service("auth-api")` through `invoke_governed` with ITS OWN delegated authority
    (read-only scope). ArmorIQ must reject it; whatever the platform decides is recorded honestly on
    `DiagnosisResult` (`governed_restart_attempted/blocked/error/result`) — the probe is never fatal, never
    faked, and there is no keyword filter, agent-name check, or local policy layer. If ArmorIQ is
    unreachable the failure is recorded and the incident fails honestly — no governed→unguarded downgrade
    during the demonstration. `invoke_governed` audits the attempt (`status="blocked"`, verified exception
    type).
  - `scripts/run_enforcement_demo.sh` — one deterministic run, two scenes: Scene 1 (blocked, proof: Docker
    `StartedAt` unchanged) and Scene 2 (allowed, proof: `StartedAt` changed, `/health` healthy), with the
    audit mirror printed. Fails honestly if governed mode cannot activate.
  - Offline tests: `test_phase8_blocked_attempt_recorded_and_not_fatal`,
    `test_phase8_unreachable_attempt_recorded_not_fatal`,
    `test_phase8_unexpected_allowance_surfaces_honestly` in `tests/test_phase67.py`.
- **Phase 9 (2026-08-20) — authorized remediation**: the Remediation Agent performs the SAME
  `restart_service("auth-api")` with its own delegation; the governed path already executes the real
  restart through `remediation-mcp` (Phase 7). `tests/test_live_authorization.py` (3 live tests,
  self-skipping): real delegations with exact scopes, live blocked (StartedAt unchanged + audit blocked),
  live allowed (StartedAt changed + /health 200 + audit success). The live rejection exception class is
  OBSERVED and recorded by these tests — never hardcoded before it is seen.

## In Progress

- **Live Phase 8/9 enforcement run** — real key obtained and verified (real intent tokens + real subtree
  delegations minted 2026-08-20); the run is blocked only on registering the three MCPs (`log-mcp`,
  `diagnostic-mcp`, `remediation-mcp`) with public HTTPS tunnel URLs so the hosted ArmorIQ proxy can reach
  them. The user will register them; `tests/test_live_authorization.py` then verifies blocked + allowed
  live, and `scripts/run_enforcement_demo.sh` runs the two-scene demonstration.

## Not Started

- Phase 10 — testing + audit trail viewer + demo polish.
- Trail viewer (Phase 10).
- Real Gemini diagnosis has never been exercised end-to-end (no `AEGISOPS_GEMINI_API_KEY` on this machine).
- Token-expiry demonstration, post-diagnosis re-delegation, onward delegation (explicitly OUT of scope for
  Phases 8/9 — see PLAN §13).

## Architecture Decisions

| # | Decision |
|---|---|
| 1 | Four separate agent processes, each with its own Ed25519 keypair and its own `ArmorIQClient` — implemented Phase 5 |
| 2 | Inter-agent transport: simple HTTP (`/run_task` endpoint per agent) — implemented Phase 4 |
| 3 | `capture_plan()` receives an explicit plan artifact we construct (SDK does not invent plans) — implemented Phase 5 |
| 4 | The unauthorized-restart attempt is deterministic (hardcoded control flow); LLM only produces the diagnosis rationale — implemented Phase 4 |
| 5 | SQLite is a thin mirror of ArmorIQ results; ArmorIQ is the source of truth for authorization — implemented Phase 7 (mirror) |
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
| 25 | **NEW (Phase 6):** central authority matrix — log `["search_logs"]`, diagnosis `["get_service_status","inspect_service_state"]`, remediation `["restart_service"]`; validated before any network call; diagnosis MUST NOT hold `restart_service` |
| 26 | **NEW (Phase 6):** each delegation is bound to the child's own Ed25519 public key and the delegated token is held in memory only; `IncidentResult` carries safe metadata only |
| 27 | **NEW (Phase 6):** delegation is best-effort — a failure keeps the incident unguarded (Phase 4 baseline) and is reported honestly (`delegation_error`, audit row); never faked, never blocking |
| 28 | **NEW (Phase 7):** mode selection by authority presence, not an env flag — request carries a delegation → governed `invoke()`; otherwise the Phase 4 direct-MCP path runs unchanged |
| 29 | **NEW (Phase 7):** governed rejections are surfaced, never swallowed — the verified `ArmorIQException` type is recorded, audited, and raised as `AgentError`; no hardcoded block class in the code path |
| 30 | **NEW (Phase 7):** SQLite audit mirror stores safe metadata only (`_FORBIDDEN_FIELDS` enforced + tested); best-effort writes; ArmorIQ remains the authorization source of truth |

## Verified SDK Details

All verified against docs.armoriq.ai + installed `armoriq-sdk 0.6.10` (signatures introspected, source
read), 2026-08-19/20:

- Package `armoriq-sdk` (PyPI), ships the `armoriq` CLI; Python `>=3.10,<3.14`; v0.6.10 installed.
- `ArmorIQClient(api_key=...)`, env `ARMORIQ_API_KEY`, or `~/.armoriq/credentials.json` (from `armoriq login`);
  `from_config("armoriq.yaml")`; one-key + `for_user(email)` identity model (`user_id`/`agent_id` deprecated).
- `capture_plan(llm, prompt, plan, metadata=None) -> PlanCapture` — local, no network; plan must contain `steps`.
  In 0.6.10 PlanCapture exposes only plan/llm/prompt/metadata (no plan_hash/merkle_root on the object).
- `get_intent_token(plan_capture, policy=None, validity_seconds=60.0) -> IntentToken` — network; token carries
  `plan_hash`, `step_proofs`, `expires_at`, etc. The token object is SENSITIVE (`raw_token`/`jwt_token`) and is
  never logged or serialized in this project.
- `delegate_subtree(intent_token, *, delegate_public_key, subtree_path, validity_seconds=3600, parent_plan,
  plan_id, intent_reference, target_agent)` — **network, LIVE-VERIFIED 2026-08-20**: posts
  `parentToken`/`delegatePublicKey`/`validitySeconds`/`subtreePath`/`planId` to `/iap/trust/delegate` and
  mints real subtree-bounded delegated tokens (`trust_id`, `inclusion_proof`, `subtree_root`,
  `delegated_token` with `subtree_delegation` metadata that `invoke()` auto-attaches as X-CSRG-Subtree-*
  headers). The legacy `delegate()` payload is DEAD on this platform (400 `parentToken is required`).
  `delegate_public_key` is a raw-bytes-hex Ed25519 public key. Subtree paths tested live: `"0"`, `"1,2"`,
  `"3"`, `"1,2,3"`, `"*"` all minted.
- `list_mcps()` — network; returns the registered MCPs on the platform (currently `[]` — nothing registered
  yet; the user will register the three MCP servers).
- `invoke(mcp, action, intent_token, params=None, merkle_proof=None, user_email=None) -> MCPInvocationResult` —
  network (proxy `/invoke`); **local fail-closed checks run before any network call**:
  `TokenExpiredException` if the token is expired, `IntentMismatchException` if the action is not in the
  plan steps, `MCPInvocationException` if neither `merkle_proof` nor `step_proofs` is available. Blocked by
  policy → `PolicyBlockedException`; 401/403 → `InvalidTokenException`; 409 → `IntentMismatchException`;
  proxy error payload → `MCPInvocationException`; MCP tool error → result with `status: "error"`. Result
  fields: `mcp/action/result/status/execution_time/verified/metadata`.
- Proxy endpoint resolution: `proxy_endpoints[mcp]` → env `<MCP>_PROXY_URL` → `default_proxy_endpoint`
  (`PROXY_ENDPOINT` env or `https://proxy.armoriq.ai`). The proxy is a hosted, stateless reverse proxy;
  MCPs must be pre-registered (dashboard or `armoriq register`) and speak JSON-RPC 2.0 + SSE.
- Blocked/denied actions are exceptions (`IntentMismatchException`, `PolicyBlockedException`,
  `TokenExpiredException`, `InvalidTokenException`, `DelegationException`, `MCPInvocationException`; base
  `ArmorIQException`).
- **MCP connectivity (Phase 3):** registered MCPs require a public HTTPS URL; hosted proxy cannot reach
  localhost; self-hosting the ArmorIQ stack is officially supported; local MCP development needs no ArmorIQ.
- **MCP transport (Phase 3):** official MCP Python SDK `mcp==2.0.0` (Streamable HTTP, SSE responses,
  2025-era `initialize`/`tools/list`/`tools/call` + 2026-era protocol served from one server).

## Known Unknowns / Limitations (Phase 8 + 9)

- **Live invoke() enforcement not yet run** — real intent tokens and real subtree delegations have been
  minted live, but `invoke()` cannot reach the MCPs until they are registered on the platform with public
  tunnel URLs (proxy returns `Internal Proxy Error`/`MCPInvocationException` while `list_mcps()` is empty).
  The blocked/allowed live proof is staged in `tests/test_live_authorization.py` and
  `scripts/run_enforcement_demo.sh`.
- Which exact exception a delegated-token scope violation raises in production (`IntentMismatchException` vs
  `PolicyBlockedException`) — OBSERVED live by `tests/test_live_authorization.py` (no hardcoded class) and
  recorded in the audit row's `error_type`; run pending MCP registration.
- Whether the hosted proxy requires per-MCP `PROXY_URL` config or accepts the default endpoint once MCPs are
  registered — needs the live run.
- Real Gemini diagnosis not exercised — no `AEGISOPS_GEMINI_API_KEY` on this machine; all runs used the
  explicitly-marked deterministic test fallback (`llm_source: "fallback"`). The Gemini path is unit-tested
  via stubs, not live-tested. (Authorization decisions never depend on the LLM.)
- Which tunnel provider (if any) will be used when the hosted proxy must reach the MCPs — deployment concern,
  not yet decided; the user will register the MCPs with tunnel URLs.
- Commander keeps one incident in memory (no persistence; single-incident demo scope by design).
- Agent logs are per-process files under `logs/agents/`; no centralized observability (by design).
- The audit mirror is a thin local SQLite mirror (safe metadata only) — it is not a replacement for the
  ArmorIQ audit trail.

## Next Steps

1. **Phases 5–7 — identities, plan, delegation, governed invocation, audit mirror — DONE.**
2. **Phase 8 — violation + enforcement — DONE (code + offline tests)**: deliberate governed restart probe
   (`attempt_governed_restart`), honest blocked/error/allowed recording on `DiagnosisResult`, audit
   `status="blocked"`, `scripts/run_enforcement_demo.sh`.
3. **Phase 9 — authorized remediation — DONE (code + offline tests)**: same action, different delegated
   authority, allowed path already wired (Phase 7); `tests/test_live_authorization.py` staged.
4. **Live Phase 8/9 run** (BLOCKED on MCP registration with tunnel URLs — the user registers
   `log-mcp`/`diagnostic-mcp`/`remediation-mcp`): run `tests/test_live_authorization.py -m live` and
   `scripts/run_enforcement_demo.sh`; record the observed rejection exception; verify StartedAt unchanged
   (blocked) / changed (allowed) + audit rows.
5. Phase 10 — testing + audit trail + demo polish (only after the live run).

## Blockers

- **MCP registration with public tunnel URLs** — the only remaining blocker for the live Phase 8/9 run: the
  hosted ArmorIQ proxy cannot reach localhost, so `log-mcp`/`diagnostic-mcp`/`remediation-mcp` must be
  registered on the platform with HTTPS URLs reachable by the proxy. The user will register them.
- No `AEGISOPS_GEMINI_API_KEY` on this machine — needed to exercise a real Gemini diagnosis (not required
  for authorization, which never depends on the LLM).

## Definition of Ready (Phase 8 — violation + enforcement demonstration)

- [x] Phase 6 + 7 complete (delegation + governed invocation + audit mirror implemented; 113 tests pass)
- [x] Diagnosis Agent's delegation excludes `restart_service` (enforced + tested)
- [x] Governed invocation surfaces ArmorIQ rejections with the verified exception type (stub-tested)
- [x] Real `ARMORIQ_API_KEY` obtained and verified (real intent tokens + real subtree delegations minted live)
- [x] Phase 8 probe implemented + offline-tested (blocked/unreachable/unexpected-allowance all recorded,
      never fatal; audit `status="blocked"`; no keyword filtering, no local policy layer)
- [x] Phase 9 allowed path implemented (same action, different delegated authority; real restart already
      proven unguarded + governed via MCP)
- [x] Live test staged (`tests/test_live_authorization.py` — self-skipping; observes the REAL exception class)
- [x] Demo script staged (`scripts/run_enforcement_demo.sh` — Scene 1 blocked / Scene 2 allowed with Docker
      StartedAt proof; fails honestly if governed mode cannot activate)
- [ ] MCPs registered on the platform with exact names (`log-mcp`, `diagnostic-mcp`, `remediation-mcp`)
      + public HTTPS tunnel URLs
- [ ] Live blocked path reproduced (Diagnosis Agent's governed `restart_service` attempt denied, StartedAt
      unchanged, audit blocked)
- [ ] Live allowed path reproduced (Remediation Agent's `restart_service` accepted, StartedAt changed,
      /health healthy, audit success)