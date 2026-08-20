"""Log Agent - separate process (port 8091).

Responsibilities (PLAN.md §5, ARCHITECTURE.md §8):
- Receive an investigation request over HTTP.
- Call log-mcp ``search_logs`` to retrieve recent log lines for the service.
- Return a compact, structured InvestigationResult (evidence + summary), not a
  raw log dump.

Capabilities are intentionally minimal: read-only log retrieval only.
"""

from __future__ import annotations

import sys

import uvicorn
from fastapi import FastAPI

from agents.common import (
    LOG_MCP_URL,
    AgentError,
    EvidenceLine,
    InvestigationRequest,
    InvestigationResult,
    MCPToolError,
    call_mcp,
    invoke_governed,
    log_event,
    make_logger,
)

app = FastAPI(title="log-agent", version="0.4.0")
logger = make_logger("log-agent")


async def _search_logs(req: InvestigationRequest) -> dict:
    """Governed path (Agent -> ArmorIQ invoke -> log-mcp) when the Commander
    handed this agent a delegated authority; otherwise the unguarded direct
    MCP path (Phase 4 baseline, preserved for regression)."""
    if req.authority is not None:
        log_event(logger, req.incident_id, "investigation_governed", "running",
                  delegation_id=req.authority.delegation_id)
        return invoke_governed(
            agent="log_agent",
            authority=req.authority,
            mcp="log-mcp",
            action="search_logs",
            params={"service": req.service, "limit": req.limit, "keyword": req.keyword},
            incident_id=req.incident_id,
        )
    return await call_mcp(
        LOG_MCP_URL,
        "search_logs",
        {"service": req.service, "limit": req.limit, "keyword": req.keyword},
    )


@app.get("/health")
async def health() -> dict:
    return {"agent": "log-agent", "status": "ok"}


@app.post("/run_task")
async def run_task(req: InvestigationRequest) -> InvestigationResult:
    log_event(logger, req.incident_id, "investigation_started", "running",
              service=req.service, limit=req.limit)
    try:
        payload = await _search_logs(req)
        lines = payload.get("lines", [])
        evidence = [EvidenceLine(index=i, text=line) for i, line in enumerate(lines)]
        summary = f"Collected {len(evidence)} log line(s) for service '{req.service}'."
        log_event(logger, req.incident_id, "evidence_collected", "ok", count=len(evidence))
        return InvestigationResult(
            incident_id=req.incident_id,
            service=req.service,
            evidence=evidence,
            summary=summary,
            status="ok",
        )
    except (MCPToolError, AgentError) as exc:
        log_event(logger, req.incident_id, "investigation_failed", "error", error=str(exc))
        return InvestigationResult(
            incident_id=req.incident_id,
            service=req.service,
            status="error",
            error=str(exc),
        )


if __name__ == "__main__":
    import os

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("AEGISOPS_AGENT_PORT", "8091")),
                log_level="warning")