# Current State

## Project Status

**Phase 1 (ArmorIQ SDK verification + project foundation) — completed.**

The ArmorIQ SDK has been verified against the official docs (docs.armoriq.ai, current) and the installed
package (`armoriq-sdk 0.6.10`). The Python environment, client/identity foundation, and a smoke test are in
place. The full agent workflow is NOT implemented.

## Completed

- `PLAN.md`, `ARCHITECTURE.md`, `README.md`, `CURRENT_STATE.md` created (architecture phase).
- **ArmorIQ SDK verified (2026-08-19)** — package, client init, all four core method signatures, exceptions,
  proxy model, MCP registration + wire format. See ARCHITECTURE.md §8 for the full verified list.
- **Environment established** — venv on **Python 3.12.10** (SDK does not support 3.14); `requirements.txt`
  pins `armoriq-sdk==0.6.10` + `python-dotenv==1.2.3`; `.env.example` documents `ARMORIQ_API_KEY` and
  optional endpoint overrides; `.gitignore` covers `.env`, `.venv`, `.keys/`, `.armoriq/`, `*.db`.
- **Identity foundation** — `armoriq/client_setup.py`: env loading, API-key validation (must start
  `ak_live_`/`ak_test_`/`ak_claw_`), client factory, Ed25519 keypair generate/save/load helpers (PEM private +
  raw-hex public, stored in gitignored `.keys/`). Round-trip verified.
- **Smoke test** — `scripts/armoriq_smoke_test.py`:
  - `--local-only` run: **PASS** (config, client init, `capture_plan()` with the real 4-step plan, keypair round-trip).
  - full run with a placeholder key: fails clearly at `get_intent_token()` with `InvalidTokenException`
    ("Invalid or expired API key") — proving the network path is reached and errors surface as exceptions.

## In Progress

- Nothing. Phase 1 is complete. Waiting for Phase 2 to start.

## Not Started

- Docker infrastructure (`auth-api` with `/health`, `/break`, `/fix`)
- MCP servers (wire format verified: JSON-RPC 2.0 + SSE; not built, not registered)
- Agent processes (Commander, Log, Diagnosis, Remediation) + HTTP transport
- ArmorIQ integration beyond the foundation (plan capture/token/delegate/invoke wiring, agent keypair provisioning)
- Database (`schema.sql`, `db.py`, SQLite)
- Tests (MCP tools, authorization security path, happy path, e2e)
- Demo/reset scripts
- Trail viewer

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

1. **Phase 2 — Docker infrastructure**: build `auth-api` (FastAPI) with `/health`, `/break`, `/fix`;
   prove break → `docker restart auth-api` → heal manually. No ArmorIQ involved.
2. Resolve the MCP connectivity question (tunnel vs self-hosted proxy vs direct) before Phase 3.
3. Phase 3 — MCP servers in the verified JSON-RPC/SSE format + registration on the platform.

## Blockers

- No real `ARMORIQ_API_KEY` yet — needed to verify the network path (token issuance/delegation/invoke) and the
  MCP registration flow. Everything else proceeds without it.

## Definition of Ready (Phase 2)

Phase 2 may begin when:

- [ ] Docker is available on the machine
- [ ] No dependency on ArmorIQ — Phase 2 is pure Docker/auth-api work

Definition of Ready (Phase 3 — MCPs):

- [ ] Phase 2 complete (auth-api healthy/broken states provable)
- [ ] MCP connectivity decision made (tunnel / self-hosted proxy / direct)
- [ ] Platform account + API key available for MCP registration (or a decision to defer registration)

Definition of Ready (Phase 5+ — ArmorIQ wiring):

- [ ] Real `ARMORIQ_API_KEY` obtained
- [ ] MCPs registered on the platform with exact names (`log-mcp`, `diagnostic-mcp`, `remediation-mcp`)