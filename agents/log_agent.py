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
    EvidenceLine,
    InvestigationRequest,
    InvestigationResult,
    MCPToolError,
    call_mcp,
    log_event,
    make_logger,
)

app = FastAPI(title="log-agent", version="0.4.0")
logger = make_logger("log-agent")


@app.get("/health")
async def health() -> dict:
    return {"agent": "log-agent", "status": "ok"}


@app.post("/run_task")
async def run_task(req: InvestigationRequest) -> InvestigationResult:
    log_event(logger, req.incident_id, "investigation_started", "running",
              service=req.service, limit=req.limit)
    try:
        payload = await call_mcp(
            LOG_MCP_URL,
            "search_logs",
            {"service": req.service, "limit": req.limit, "keyword": req.keyword},
        )
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
    except MCPToolError as exc:
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