# Current State

## Project Status

**Architecture phase — implementation has not started.**

The plan is complete (`PLAN.md`), and the implementation-ready architecture is defined (`ARCHITECTURE.md`).
The repository contains only documentation, project structure placeholders, and config placeholders.
No implementation code exists anywhere.

## Completed

- `PLAN.md` created — full scope, scenario, SDK reality check, one-day implementation plan, priority tiers.
- Project requirements understood and distilled into the MVP definition (ARCHITECTURE.md §1.1).
- Initial architecture defined — agents, delegation model, MCP inventory, ArmorIQ lifecycle, infrastructure, data, security model, failure boundaries, implementation order (ARCHITECTURE.md).
- Project skeleton established — directory structure per PLAN §12 with `.gitkeep` placeholders, `.gitignore`, `.env.example` (placeholder key), placeholder `requirements.txt` and `docker-compose.yml`.
- `ARCHITECTURE.md` created (technical blueprint).
- `README.md` created (public-facing introduction; everything marked Planned).
- `CURRENT_STATE.md` created (this file).

## In Progress

- Nothing is actively being implemented. The next step is to confirm the open verification items, then begin Phase 1 (project skeleton + ArmorIQ setup).

## Not Started

All implementation areas remain untouched:

- Docker infrastructure (`auth-api` with `/health`, `/break`, `/fix`)
- MCP tools (`search_logs`, `get_service_status`, `inspect_config`, `restart_service`)
- Agent processes (Commander, Log, Diagnosis, Remediation) + HTTP transport
- ArmorIQ integration (identities, keypairs, `capture_plan`, `delegate`, `invoke`)
- Database (`schema.sql`, `db.py`, SQLite)
- Tests (MCP tools, authorization security path, happy path, e2e)
- Demo/reset scripts (`start_env.sh`, `break_service.sh`, `run_incident.sh`, `reset_demo.sh`)
- Trail viewer (terminal output or minimal HTML page)

## Architecture Decisions

| # | Decision |
|---|---|
| 1 | Four separate agent processes, each with its own Ed25519 keypair and its own `ArmorIQClient` |
| 2 | Inter-agent transport: simple HTTP (`/run_task` endpoint per agent) |
| 3 | `capture_plan()` receives an explicit plan artifact we construct (SDK does not invent plans) |
| 4 | The unauthorized-restart attempt is deterministic (hardcoded control flow); LLM only produces the diagnosis rationale |
| 5 | SQLite is a thin mirror of ArmorIQ results; ArmorIQ is the source of truth for authorization |
| 6 | MCPs may be plain HTTP tool wrappers (real MCP protocol optional, documented scope cut) |
| 7 | Commander dispatch may be hardcoded if time is short; the Diagnosis LLM call is the only "SHOULD HAVE" AI piece |
| 8 | Secrets only in `.env` (gitignored); no Vault/KMS |
| 9 | No generic agent framework; build exactly the PLAN §1 scenario |
| 10 | Trail viewer: terminal output default; minimal HTML page only if Phase 10 has time |

## Known Unknowns

All ArmorIQ specifics marked `VERIFY AGAINST ARMORIQ SDK` in PLAN.md §0 and ARCHITECTURE.md §15:

- Exact `armoriq-sdk` package name/version on PyPI and install requirements
- Client initialization scope in the installed version: `agent_id`-scoped vs `for_user(email)`-scoped
- Whether MCPs must be pre-registered on `platform.armoriq.ai` before `capture_plan()`/`invoke()` accept them
- Current signatures of `capture_plan`, `get_intent_token`, `delegate`, `invoke`
- Shape of the "blocked" response from `invoke()` (exception vs `success: false`) — drives error handling
- Whether `step_proofs` from `get_intent_token()` must be passed explicitly at `invoke()`

## Next Steps

1. Verify the ArmorIQ SDK items above against `docs.armoriq.ai` (PLAN §0 checklist); confirm API key works with a trivial `capture_plan()`/`get_intent_token()` call.
2. Phase 1 — project skeleton: dependencies, docker-compose skeleton, `.env`, SDK quickstart working.
3. Phase 2 — Docker infrastructure: `auth-api` with `/health` `/break` `/fix`; manually prove break → `docker restart` → heal.
4. Phases 3-10 per ARCHITECTURE.md §16 (full dependency-aware order in PLAN §13).

## Blockers

- **None blocking documentation.** The only implementation blocker is the pending ArmorIQ SDK verification (known unknowns above) — SDK is Beta and may behave differently than current docs.

## Definition of Ready

Implementation (Phase 1) may begin when:

- [ ] `armoriq-sdk` installed and a trivial `capture_plan()` + `get_intent_token()` call succeeds with the real API key
- [ ] MCP pre-registration requirement on `platform.armoriq.ai` confirmed (or waived via docs)
- [ ] Blocked-response shape from `invoke()` confirmed (exception vs result flag) so error handling matches reality
- [ ] Client initialization pattern confirmed (`agent_id` vs `for_user`) for the installed SDK version
- [ ] `DECISION NEEDED` items resolved: optional Postgres (default: cut), trail viewer (default: terminal), prompt-injection beat (default: include), LLM-failure fallback (default: inconclusive → no escalation)
- [ ] Docker available and `docker compose up` starts a skeleton without errors

Until then: do not write agent code, MCP code, or ArmorIQ integration code.