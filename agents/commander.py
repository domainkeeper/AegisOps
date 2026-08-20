"""Commander Agent - separate process (port 8094), the orchestrator.

Responsibilities (PLAN.md §5, ARCHITECTURE.md §8):
1. Receive an incident over HTTP.
2. Create/maintain the incident context (in-memory; single incident at a time
   in this phase).
3. Ask the Log Agent for evidence (HTTP).
4. Send the evidence to the Diagnosis Agent (HTTP).
5. Receive the diagnosis.
6. Determine whether remediation is needed.
7. Ask the Remediation Agent to perform it (HTTP) - the Commander NEVER runs
   docker itself, it delegates.
8. Verify the resulting service health (via diagnostic-mcp).
9. Mark the incident RESOLVED or FAILED.

Orchestration is deterministic. Failures are surfaced as structured errors and
always result in an explicit RESOLVED / FAILED outcome - nothing is silently
swallowed.
"""

from __future__ import annotations

import time

import uvicorn
from fastapi import FastAPI

from agents.common import (
    DIAGNOSTIC_MCP_URL,
    DIAGNOSIS_AGENT_URL,
    LOG_AGENT_URL,
    REMEDIATION_AGENT_URL,
    AgentError,
    DiagnosisRequest,
    DiagnosisResult,
    Incident,
    IncidentResult,
    InvestigationRequest,
    InvestigationResult,
    MCPToolError,
    RemediationRequest,
    RemediationResult,
    TimelineEvent,
    call_mcp,
    log_event,
    make_logger,
    post_json,
)

app = FastAPI(title="commander-agent", version="0.4.0")
logger = make_logger("commander-agent")

RESOLVED = "RESOLVED"
FAILED = "FAILED"


class IncidentContext:
    """In-memory incident state with an explicit lifecycle and a timeline."""

    def __init__(self, incident: Incident) -> None:
        self.incident = incident
        self.status = "RECEIVED"
        self.timeline: list[TimelineEvent] = []
        self.investigation: InvestigationResult | None = None
        self.diagnosis: DiagnosisResult | None = None
        self.remediation: RemediationResult | None = None
        self.verification: dict | None = None
        self.plan: dict | None = None
        self.intent_token_status: str = "not_configured"
        self.intent_token_expires_at: str | None = None
        self.intent_token_error: str | None = None
        self.error: str | None = None

    def stage(self, name: str, status: str, detail: str = "") -> None:
        self.timeline.append(TimelineEvent(ts=time.time(), stage=name, status=status, detail=detail))


def _to_error_result(ctx: IncidentContext) -> IncidentResult:
    return IncidentResult(
        incident_id=ctx.incident.incident_id,
        status=ctx.status,
        service=ctx.incident.service,
        investigation=ctx.investigation,
        diagnosis=ctx.diagnosis,
        remediation=ctx.remediation,
        verification=ctx.verification,
        plan=ctx.plan,
        intent_token_status=ctx.intent_token_status,
        intent_token_expires_at=ctx.intent_token_expires_at,
        intent_token_error=ctx.intent_token_error,
        timeline=ctx.timeline,
        error=ctx.error,
    )


def _capture_intent(ctx: IncidentContext) -> None:
    """Phase 5 intent handshake: explicit plan -> ArmorIQ capture -> intent token.

    Best-effort and NON-BLOCKING for the unguarded orchestration: any failure
    sets intent_token_status="error"/"not_configured" with a clear message but
    never aborts the incident. The token object itself is never retained or
    logged (it carries raw_token/jwt_token); only its status/expiry are kept.
    """
    from armoriq import plan as plan_mod  # lazy: keeps agent startup armoriq-free

    ctx.plan = plan_mod.build_incident_plan(ctx.incident)
    try:
        plan_mod.plan_ok_for_capture(ctx.plan)
    except plan_mod.PlanValidationError as exc:
        ctx.intent_token_status = "error"
        ctx.intent_token_error = f"plan validation failed: {exc}"
        ctx.stage("intent_capture", "error", detail=ctx.intent_token_error)
        log_event(logger, ctx.incident.incident_id, "intent_capture", "error",
                  error=ctx.intent_token_error)
        return

    if not plan_mod.armoriq_configured():
        ctx.intent_token_status = "not_configured"
        ctx.intent_token_error = (
            "ARMORIQ_API_KEY is not set; plan captured locally only (no intent token). "
            "See .env.example and README 'ACTION REQUIRED'."
        )
        ctx.stage("intent_capture", "not_configured", detail=ctx.intent_token_error)
        log_event(logger, ctx.incident.incident_id, "intent_capture", "not_configured")
        return

    try:
        from armoriq.client_setup import get_client

        client = get_client()
        plan_capture = plan_mod.capture_execution_plan(client, ctx.incident)
        token = plan_mod.generate_intent_token(client, plan_capture)
    except Exception as exc:
        ctx.intent_token_status = "error"
        ctx.intent_token_error = f"intent token handshake failed: {exc}"
        ctx.stage("intent_capture", "error", detail=ctx.intent_token_error)
        log_event(logger, ctx.incident.incident_id, "intent_capture", "error",
                  error=ctx.intent_token_error)
        return

    # Keep only non-sensitive state. The token is never stored on the context.
    ctx.intent_token_status = "ready"
    ctx.intent_token_expires_at = getattr(token, "expires_at", None) or ""
    ctx.stage("intent_capture", "ready",
              detail=f"intent token ready, expires_at={ctx.intent_token_expires_at}")
    log_event(logger, ctx.incident.incident_id, "intent_capture", "ready",
              expires_at=ctx.intent_token_expires_at)


def _validate_result(model, payload: dict, label: str) -> None:
    """Fail fast on invalid responses from a peer agent (AgentError)."""
    try:
        model.model_validate(payload)
    except Exception as exc:
        raise AgentError(f"invalid response from {label}: {exc}") from exc


@app.get("/health")
async def health() -> dict:
    return {"agent": "commander-agent", "status": "ok"}


@app.post("/incident")
async def handle_incident(incident: Incident) -> IncidentResult:
    ctx = IncidentContext(incident)
    log_event(logger, incident.incident_id, "incident_received", "running",
              service=incident.service, severity=incident.severity,
              description=incident.description)
    ctx.stage("incident_received", "ok")

    # Phase 5 intent handshake (best-effort, never blocks orchestration).
    _capture_intent(ctx)

    try:
        # 3. Log Agent: gather evidence
        ctx.status = "INVESTIGATING"
        ctx.stage("investigating", "running")
        resp = await post_json(
            LOG_AGENT_URL + "/run_task",
            InvestigationRequest(incident_id=incident.incident_id, service=incident.service)
            .model_dump(),
        )
        _validate_result(InvestigationResult, resp, "log-agent")
        ctx.investigation = InvestigationResult.model_validate(resp)
        if ctx.investigation.status == "error":
            raise AgentError(f"log-agent failed: {ctx.investigation.error}")
        ctx.stage("investigated", "ok", detail=f"{len(ctx.investigation.evidence)} evidence items")
        log_event(logger, incident.incident_id, "investigation_completed", "ok",
                  evidence_count=len(ctx.investigation.evidence))

        # 4-5. Diagnosis Agent: evidence + state -> diagnosis
        ctx.status = "DIAGNOSING"
        ctx.stage("diagnosing", "running")
        resp = await post_json(
            DIAGNOSIS_AGENT_URL + "/run_task",
            DiagnosisRequest(
                incident_id=incident.incident_id,
                service=incident.service,
                evidence=ctx.investigation.evidence,
            ).model_dump(),
        )
        _validate_result(DiagnosisResult, resp, "diagnosis-agent")
        ctx.diagnosis = DiagnosisResult.model_validate(resp)
        if ctx.diagnosis.status == "error":
            raise AgentError(f"diagnosis-agent failed: {ctx.diagnosis.error}")
        ctx.stage("diagnosed", "ok",
                  detail=f"requires_remediation={ctx.diagnosis.requires_remediation}")
        log_event(logger, incident.incident_id, "diagnosis_completed", "ok",
                  requires_remediation=ctx.diagnosis.requires_remediation,
                  llm_source=ctx.diagnosis.llm_source)

        # 6-7. Remediation Agent: execute remediation if needed
        if ctx.diagnosis.requires_remediation:
            ctx.status = "REMEDIATING"
            ctx.stage("remediating", "running")
            resp = await post_json(
                REMEDIATION_AGENT_URL + "/run_task",
                RemediationRequest(incident_id=incident.incident_id, service=incident.service)
                .model_dump(),
            )
            _validate_result(RemediationResult, resp, "remediation-agent")
            ctx.remediation = RemediationResult.model_validate(resp)
            if ctx.remediation.status == "error" or not ctx.remediation.success:
                raise AgentError(
                    f"remediation-agent failed: {ctx.remediation.error or 'restart unsuccessful'}"
                )
            ctx.stage("remediated", "ok",
                      detail=f"noop={ctx.remediation.noop}, started_at={ctx.remediation.started_at}")
            log_event(logger, incident.incident_id, "remediation_completed", "ok",
                      noop=ctx.remediation.noop, success=ctx.remediation.success)
        else:
            log_event(logger, incident.incident_id, "remediation_skipped", "ok",
                      reason="diagnosis found nothing to remediate")

        # 8. Verify recovery
        ctx.status = "VERIFYING"
        ctx.stage("verifying", "running")
        ctx.verification = await call_mcp(
            DIAGNOSTIC_MCP_URL, "get_service_status", {"service": incident.service}
        )
        if ctx.verification.get("http_code") != 200:
            raise AgentError(
                f"service not healthy after remediation: HTTP {ctx.verification.get('http_code')}"
            )
        ctx.stage("verified", "ok", detail=f"http_code={ctx.verification.get('http_code')}")
        log_event(logger, incident.incident_id, "service_verified", "ok",
                  http_code=ctx.verification.get("http_code"))

        # 9. Resolved
        ctx.status = RESOLVED
        ctx.stage("incident_resolved", "ok")
        log_event(logger, incident.incident_id, "incident_resolved", "ok")

    except (AgentError, MCPToolError) as exc:
        ctx.status = FAILED
        ctx.error = str(exc)
        ctx.stage("incident_failed", "error", detail=str(exc))
        log_event(logger, incident.incident_id, "incident_failed", "error", error=str(exc))

    return _to_error_result(ctx)


if __name__ == "__main__":
    import os

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("AEGISOPS_AGENT_PORT", "8094")),
                log_level="warning")