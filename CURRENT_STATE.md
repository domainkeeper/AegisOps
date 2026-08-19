# Current State

## Project Status

**Phase 2 (real incident infrastructure) — completed (2026-08-19).**

Phase 1 verified the ArmorIQ SDK (docs + installed `armoriq-sdk 0.6.10`) and established the Python environment,
identity foundation, and smoke test. Phase 2 built the real Docker-based incident environment: `auth-api`
(FastAPI) with `/health`, `/break`, `/fix`, a `Dockerfile`, a root `docker-compose.yml`, six dev scripts,
and five automated infrastructure tests. It is now **proven** that breaking the service makes `/health` return
503 and that a real `docker restart auth-api` recovers it (container start time changes, state resets).
The full agent/MCP/ArmorIQ workflow is NOT implemented yet.

## Completed

- `PLAN.md`, `ARCHITECTURE.md`, `README.md`, `CURRENT_STATE.md` created (architecture phase).
- **Phase 1 (2026-08-19)** — ArmorIQ SDK verified; venv on Python 3.12.10; `armoriq/client_setup.py` identity
  foundation; `scripts/armoriq_smoke_test.py` (`--local-only` PASS; full mode reaches the network and fails
  clearly with `InvalidTokenException` on the placeholder key).
- **Phase 2 (2026-08-19) — real incident infrastructure**:
  - `infrastructure/auth_api/main.py` — FastAPI app with in-memory health state: `GET /health` (200 healthy /
    503 unhealthy), `POST /break` (simulate incident, container keeps running), `POST /fix` (app-level
    recovery), `GET /` info. Port 8080. A real container restart resets state.
  - `infrastructure/auth_api/Dockerfile` (`python:3.12-slim`, pinned `fastapi==0.141.1` + `uvicorn==0.52.4`,
    HEALTHCHECK on `/health`), `requirements.txt`, `.dockerignore`.
  - Root `docker-compose.yml` — single compose source: `auth-api`, `container_name: auth-api`, `8080:8080`,
    `restart: unless-stopped`.
  - Dev scripts (Git Bash): `start_env.sh`, `check_health.sh`, `break_service.sh`, `fix_service.sh`,
    `restart_service.sh` (the real `docker restart auth-api` the future Remediation MCP will wrap),
    `reset_demo.sh` (`down -v && up -d --build`, future: also clears SQLite rows).
  - `tests/test_infrastructure.py` — 5 tests, all **PASS**: container running; /health initially healthy;
    /break → 503 unhealthy; `docker restart` → healthy AND `{{.State.StartedAt}}` changes (real restart
    proven); /fix restores app state. Stdlib-only (urllib + docker subprocess); repo-root CWD.
  - Full lifecycle manually verified end-to-end: start → healthy → break → 503 → restart → healthy → reset.
  - Repo language cleaned: README/ARCHITECTURE/PLAN now read as a standalone product (no hackathon terms).

## In Progress

- Nothing. Phase 2 is complete. Waiting for Phase 3 (MCP servers) to start.

## Not Started

- MCP servers (`log_mcp.py`, `diagnostic_mcp.py`, `remediation_mcp.py`) — JSON-RPC 2.0 + SSE, registered on
  the platform under exact names; connectivity decision pending (tunnel / self-hosted proxy / direct).
- Agent processes (Commander, Log, Diagnosis, Remediation) + HTTP transport.
- ArmorIQ integration beyond the foundation (plan capture/token/delegate/invoke wiring, agent keypair
  provisioning, per-agent `user_email` scopes).
- Database (`schema.sql`, `db.py`, SQLite) — Phase 7.
- Tests beyond infrastructure (MCP tools, authorization security path, happy path, e2e).
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
| 13 | **NEW (Phase 2):** single root `docker-compose.yml` (no infra-local duplicate); `auth-api` uses in-memory state so a real restart is observable; Postgres cut (cosmetic only) |
| 14 | **NEW (Phase 2):** future Remediation MCP exposes narrowly scoped `restart_service("auth-api")` — fixed mapping, no generic `run_shell(command)`; authorization stays upstream at the ArmorIQ Proxy |

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

## Known Unknowns

- Which exception a delegated-token scope violation raises (`IntentMismatchException` vs `PolicyBlockedException`)
  — needs a runtime test with a real API key (Phase 8).
- Whether the hosted proxy can reach MCPs running locally in Docker for the demo (format docs say public HTTPS;
  may need a tunnel or self-hosted proxy). Resolve before Phase 3.
- Full network path (`get_intent_token` → `delegate` → `invoke`) with a live API key — not tested (no real key).
- Whether `agent_id` still has any effect in 0.6.10 despite deprecation.

## Next Steps

1. Resolve the MCP connectivity question (tunnel vs self-hosted proxy vs direct) before Phase 3.
2. **Phase 3 — MCP servers**: `log_mcp.py`, `diagnostic_mcp.py`, `remediation_mcp.py` in the verified
   JSON-RPC/SSE format; `remediation_mcp` wraps `restart_service("auth-api")` (narrowly scoped, no shell);
   register on the platform.
3. Phase 4 — agents over HTTP transport.

## Blockers

- No real `ARMORIQ_API_KEY` yet — needed to verify the network path (token issuance/delegation/invoke) and the
  MCP registration flow. Everything else proceeds without it.

## Definition of Ready (Phase 3 — MCPs)

- [x] Phase 2 complete (auth-api healthy/broken states provable)
- [ ] MCP connectivity decision made (tunnel / self-hosted proxy / direct)
- [ ] Platform account + API key available for MCP registration (or a decision to defer registration)

Definition of Ready (Phase 5+ — ArmorIQ wiring):

- [ ] Real `ARMORIQ_API_KEY` obtained
- [ ] MCPs registered on the platform with exact names (`log-mcp`, `diagnostic-mcp`, `remediation-mcp`)