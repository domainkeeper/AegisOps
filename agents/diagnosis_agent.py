"""Diagnosis Agent - separate process (port 8092).

Responsibilities (PLAN.md §5/§8, ARCHITECTURE.md §8):
- Receive a diagnosis request (incident context + log evidence) over HTTP.
- Call diagnostic-mcp ``get_service_status`` and ``inspect_service_state``.
- Reason over the evidence (LLM when configured; otherwise the explicitly
  marked deterministic TEST fallback) and produce a structured diagnosis.
- If remediation is required, deterministically attempt it through
  remediation-mcp ``restart_service``.

UNGUARDED BASELINE (ARCHITECTURE.md §Unguarded Security Baseline):
In this phase the Diagnosis Agent can reach the remediation capability and the
restart SUCCEEDS. There is no allow/deny rule anywhere - this is pure
agent -> MCP connectivity. In the ArmorIQ-enabled phase the exact same call is
the demonstration that gets BLOCKED, because the diagnosis token will not carry
restart_service authority. Only the Remediation Agent will then be allowed to
restart. Do NOT remove this path; it is the point of Phase 4.
"""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from agents import llm
from agents.common import (
    DIAGNOSTIC_MCP_URL,
    REMEDIATION_MCP_URL,
    AgentError,
    DiagnosisRequest,
    DiagnosisResult,
    MCPToolError,
    call_mcp,
    invoke_governed,
    log_event,
    make_logger,
)

app = FastAPI(title="diagnosis-agent", version="0.4.0")
logger = make_logger("diagnosis-agent")


async def _mcp_call(req: DiagnosisRequest, tool: str, params: dict) -> dict:
    """Governed (Agent -> ArmorIQ invoke -> diagnostic-mcp) when the Commander
    delegated authority to this agent; otherwise the unguarded direct path."""
    if req.authority is not None:
        return invoke_governed(
            agent="diagnosis_agent",
            authority=req.authority,
            mcp="diagnostic-mcp",
            action=tool,
            params=params,
            incident_id=req.incident_id,
        )
    return await call_mcp(DIAGNOSTIC_MCP_URL, tool, params)


async def _gather_state(service: str, incident_id: str, req: DiagnosisRequest | None = None) -> tuple[dict, dict]:
    status = await _mcp_call(req, "get_service_status", {"service": service})
    state = await _mcp_call(req, "inspect_service_state", {"service": service})
    log_event(logger, incident_id, "state_inspected", "ok", http_code=status.get("http_code"),
              running=state.get("running"), health_status=state.get("health_status"))
    return status, state


async def _produce_diagnosis(
    service: str, evidence: list[dict], status: dict, state: dict, incident_id: str
) -> tuple[llm.DiagnosisOutput, str]:
    """LLM when configured; else the marked deterministic fallback; else fail clearly."""
    if llm.configured():
        return await llm.generate_diagnosis(service, evidence, status, state, incident_id), "llm"
    if llm.test_fallback_enabled():
        log_event(logger, incident_id, "llm_unavailable", "fallback",
                  reason="no AEGISOPS_GEMINI_API_KEY set; AEGISOPS_LLM_FALLBACK=test "
                         "selects the deterministic TEST fallback (NOT model-generated)")
        return llm.fallback_diagnosis(service, evidence, status, state, incident_id), "fallback"
    raise AgentError(
        "no LLM configured (AEGISOPS_GEMINI_API_KEY) and AEGISOPS_LLM_FALLBACK is not 'test'; "
        "cannot produce a diagnosis"
    )


@app.get("/health")
async def health() -> dict:
    return {"agent": "diagnosis-agent", "status": "ok"}


@app.post("/run_task")
async def run_task(req: DiagnosisRequest) -> DiagnosisResult:
    log_event(logger, req.incident_id, "diagnosis_started", "running", service=req.service)
    governed = req.authority is not None
    try:
        status, state = await _gather_state(req.service, req.incident_id, req)
        output, llm_source = await _produce_diagnosis(
            req.service, [e.model_dump() for e in req.evidence], status, state, req.incident_id
        )
        log_event(logger, req.incident_id, "diagnosis_produced", "ok",
                  llm_source=llm_source, requires_remediation=output.requires_remediation,
                  recommended_action=output.recommended_action, governed=governed)

        remediation_attempted = False
        remediation_result = None
        if output.requires_remediation:
            if output.recommended_action != "restart_service":
                raise AgentError(
                    f"model requested unsupported action '{output.recommended_action}'"
                )
            if output.target_service != req.service:
                raise AgentError(
                    f"model targeted '{output.target_service}' but incident is about '{req.service}'"
                )
            if governed:
                # Governed mode: this agent's delegated authority intentionally
                # EXCLUDES restart_service (verified authority matrix). The
                # restart is performed only by the Remediation Agent. The
                # deliberate blocked-attempt demonstration arrives in Phase 8.
                log_event(logger, req.incident_id, "remediation_deferred", "ok",
                          reason="governed mode: diagnosis authority excludes restart_service; "
                                 "remediation agent performs the restart")
            else:
                log_event(logger, req.incident_id, "remediation_requested", "running",
                          action=output.recommended_action, target=output.target_service)
                remediation_result = await call_mcp(
                    REMEDIATION_MCP_URL, "restart_service", {"service_name": output.target_service}
                )
                remediation_attempted = True
                log_event(logger, req.incident_id, "remediation_attempted", "ok",
                          success=bool(remediation_result.get("success")))

        return DiagnosisResult(
            incident_id=req.incident_id,
            service=req.service,
            diagnosis=output.diagnosis,
            confidence=output.confidence,
            root_cause=output.root_cause,
            requires_remediation=output.requires_remediation,
            recommended_action=output.recommended_action,
            target_service=output.target_service,
            remediation_attempted=remediation_attempted,
            remediation_result=remediation_result,
            llm_source=llm_source,
            status="ok",
        )
    except (MCPToolError, AgentError, llm.LLMUnavailableError) as exc:
        log_event(logger, req.incident_id, "diagnosis_failed", "error", error=str(exc))
        return DiagnosisResult(
            incident_id=req.incident_id,
            service=req.service,
            status="error",
            error=str(exc),
        )


if __name__ == "__main__":
    import os

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("AEGISOPS_AGENT_PORT", "8092")),
                log_level="warning")