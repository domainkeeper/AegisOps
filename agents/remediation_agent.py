"""Remediation Agent - separate process (port 8093).

Responsibilities (PLAN.md §5/§10, ARCHITECTURE.md §8):
- Receive a remediation request over HTTP.
- Idempotency check: consult diagnostic-mcp first; if the service is already
  healthy, log a no-op instead of restarting twice.
- Otherwise call remediation-mcp ``restart_service`` - the REAL docker restart
  happens in the MCP layer, never via a direct subprocess from this agent.

Agent -> MCP -> Docker. This agent never shells out to docker itself.
"""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from agents.common import (
    DIAGNOSTIC_MCP_URL,
    REMEDIATION_MCP_URL,
    MCPToolError,
    RemediationRequest,
    RemediationResult,
    call_mcp,
    log_event,
    make_logger,
)

app = FastAPI(title="remediation-agent", version="0.4.0")
logger = make_logger("remediation-agent")


@app.get("/health")
async def health() -> dict:
    return {"agent": "remediation-agent", "status": "ok"}


@app.post("/run_task")
async def run_task(req: RemediationRequest) -> RemediationResult:
    log_event(logger, req.incident_id, "restart_started", "running", service=req.service)
    try:
        status = await call_mcp(DIAGNOSTIC_MCP_URL, "get_service_status", {"service": req.service})

        if status.get("http_code") == 200:
            log_event(logger, req.incident_id, "restart_skipped_noop", "ok",
                      reason="service already healthy", service=req.service)
            return RemediationResult(
                incident_id=req.incident_id,
                service=req.service,
                success=True,
                noop=True,
                health=status,
                status="ok",
            )

        result = await call_mcp(
            REMEDIATION_MCP_URL, "restart_service", {"service_name": req.service}
        )
        log_event(logger, req.incident_id, "restart_completed", "ok",
                  container=result.get("container"),
                  started_at=result.get("started_at"))
        return RemediationResult(
            incident_id=req.incident_id,
            service=req.service,
            operation=result.get("operation", "restart_service"),
            success=bool(result.get("success")),
            container=result.get("container"),
            started_at_before=result.get("started_at_before"),
            started_at=result.get("started_at"),
            health=result.get("health"),
            status="ok",
        )
    except MCPToolError as exc:
        log_event(logger, req.incident_id, "restart_failed", "error", error=str(exc))
        return RemediationResult(
            incident_id=req.incident_id,
            service=req.service,
            status="error",
            error=str(exc),
        )


if __name__ == "__main__":
    import os
    import sys

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("AEGISOPS_AGENT_PORT", "8093")),
                log_level="warning")