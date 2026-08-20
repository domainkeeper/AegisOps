"""Shared contracts, logging, and transport helpers for the AegisOps agent layer.

Design rules (ARCHITECTURE.md §8, PLAN.md §5/§10):
- Agents communicate only over plain HTTP with structured JSON request/response
  contracts (no message brokers, no service discovery).
- Tool execution happens ONLY through the MCP layer (Agent -> MCP -> Docker).
  Agents never shell out to docker directly.
- Failures are surfaced as structured errors to the Commander, which marks the
  incident RESOLVED or FAILED - nothing is silently swallowed.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any

import httpx
from mcp import Client
from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Endpoints (env-overridable so agents can be deployed on different hosts)
# ---------------------------------------------------------------------------


def _env_url(name: str, default: str) -> str:
    return os.environ.get(name, default).rstrip("/")


LOG_AGENT_URL = _env_url("AEGISOPS_LOG_AGENT_URL", "http://127.0.0.1:8091")
DIAGNOSIS_AGENT_URL = _env_url("AEGISOPS_DIAGNOSIS_AGENT_URL", "http://127.0.0.1:8092")
REMEDIATION_AGENT_URL = _env_url("AEGISOPS_REMEDIATION_AGENT_URL", "http://127.0.0.1:8093")
COMMANDER_URL = _env_url("AEGISOPS_COMMANDER_URL", "http://127.0.0.1:8094")

LOG_MCP_URL = _env_url("AEGISOPS_LOG_MCP_URL", "http://127.0.0.1:8081/mcp")
DIAGNOSTIC_MCP_URL = _env_url("AEGISOPS_DIAGNOSTIC_MCP_URL", "http://127.0.0.1:8082/mcp")
REMEDIATION_MCP_URL = _env_url("AEGISOPS_REMEDIATION_MCP_URL", "http://127.0.0.1:8083/mcp")

# The only service the agents know about in this phase. The MCP layer is the
# enforcement point for service names; this is a local guard so agent code
# never even attempts anything else.
SERVICE_ALLOWLIST: tuple[str, ...] = ("auth-api",)

# The ONLY remediation actions the model / agents may request in this phase:
# "none" (no remediation) or "restart_service" (the single MCP write capability).
ALLOWED_REMEDIATION_ACTIONS: tuple[str, ...] = ("none", "restart_service")

DEFAULT_TIMEOUT_S = 30.0
MCP_TIMEOUT_S = 20.0

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class AgentError(Exception):
    """An agent-level failure that should be surfaced as a structured error."""


class MCPToolError(AgentError):
    """A tool call to the MCP layer failed (transport, server, or tool error)."""


# ---------------------------------------------------------------------------
# Contracts (ARCHITECTURE.md §8 - request/response schemas)
# ---------------------------------------------------------------------------


class Incident(BaseModel):
    """What the system is asked to resolve."""

    incident_id: str = Field(min_length=1, max_length=128)
    service: str = Field(min_length=1, max_length=64)
    description: str = ""
    severity: str = "medium"
    timestamp: str = ""

    @field_validator("severity")
    @classmethod
    def _severity(cls, v: str) -> str:
        if v not in {"low", "medium", "high", "critical"}:
            raise ValueError("severity must be one of: low, medium, high, critical")
        return v


class InvestigationRequest(BaseModel):
    incident_id: str = Field(min_length=1, max_length=128)
    service: str = Field(min_length=1, max_length=64)
    keyword: str | None = None
    limit: int = 50

    @field_validator("limit")
    @classmethod
    def _limit(cls, v: int) -> int:
        if not 1 <= v <= 500:
            raise ValueError("limit must be between 1 and 500")
        return v


class EvidenceLine(BaseModel):
    index: int
    text: str


class InvestigationResult(BaseModel):
    incident_id: str
    service: str
    evidence: list[EvidenceLine] = []
    summary: str = ""
    status: str = "ok"
    error: str | None = None


class DiagnosisRequest(BaseModel):
    incident_id: str = Field(min_length=1, max_length=128)
    service: str = Field(min_length=1, max_length=64)
    evidence: list[EvidenceLine] = []
    status: dict[str, Any] = {}
    state: dict[str, Any] = {}


class DiagnosisResult(BaseModel):
    incident_id: str
    service: str
    diagnosis: str = ""
    confidence: float = 0.0
    root_cause: str = ""
    requires_remediation: bool = False
    recommended_action: str = "none"
    target_service: str = ""
    remediation_attempted: bool = False
    remediation_result: dict[str, Any] | None = None
    llm_source: str = "none"  # "llm" | "fallback" | "none"
    status: str = "ok"
    error: str | None = None


class RemediationRequest(BaseModel):
    incident_id: str = Field(min_length=1, max_length=128)
    service: str = Field(min_length=1, max_length=64)


class RemediationResult(BaseModel):
    incident_id: str
    service: str
    operation: str = "restart_service"
    success: bool = False
    noop: bool = False
    container: str | None = None
    started_at_before: str | None = None
    started_at: str | None = None
    health: dict[str, Any] | None = None
    status: str = "ok"
    error: str | None = None


class TimelineEvent(BaseModel):
    ts: float
    stage: str
    status: str
    detail: str = ""


class IncidentResult(BaseModel):
    incident_id: str
    status: str  # RESOLVED | FAILED
    service: str
    investigation: InvestigationResult | None = None
    diagnosis: DiagnosisResult | None = None
    remediation: RemediationResult | None = None
    verification: dict[str, Any] | None = None
    timeline: list[TimelineEvent] = []
    error: str | None = None


# ---------------------------------------------------------------------------
# Structured logging
# ---------------------------------------------------------------------------


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int(record.msecs):03d}Z",
            "agent": getattr(record, "agent", None),
            "incident_id": getattr(record, "incident_id", None),
            "operation": getattr(record, "operation", None),
            "status": getattr(record, "status", None),
            "level": record.levelname,
        }
        extra = getattr(record, "extra", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def make_logger(agent: str) -> logging.Logger:
    """Per-agent JSON-line logger: stdout plus logs/agents/<agent>.log."""
    logger = logging.getLogger(f"aegisops.agents.{agent}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        fmt = JsonFormatter()
        stream = logging.StreamHandler(sys.stdout)
        stream.setFormatter(fmt)
        logger.addHandler(stream)

        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "agents")
        os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.FileHandler(os.path.join(log_dir, f"{agent}.log"), encoding="utf-8")
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
    return logger


def log_event(
    logger: logging.Logger,
    incident_id: str | None,
    operation: str,
    status: str,
    **extra: Any,
) -> None:
    logger.info(
        "event",
        extra={"agent": logger.name.rsplit(".", 1)[-1], "incident_id": incident_id,
               "operation": operation, "status": status, "extra": extra},
    )


# ---------------------------------------------------------------------------
# Transport helpers
# ---------------------------------------------------------------------------


async def call_mcp(url: str, tool: str, arguments: dict, timeout: float = MCP_TIMEOUT_S) -> dict:
    """Invoke a single MCP tool and return its parsed JSON payload.

    Agent -> MCP -> Docker. Agents never talk to Docker directly.
    """
    try:
        async with Client(url) as client:
            result = await client.call_tool(tool, arguments)
    except Exception as exc:
        raise MCPToolError(f"{tool} via {url} failed: {exc}") from exc

    if result.is_error:
        text = result.content[0].text if result.content else "MCP tool error"
        raise MCPToolError(f"{tool} failed: {text}")
    for item in result.content:
        if item.type == "text":
            try:
                return json.loads(item.text)
            except json.JSONDecodeError as exc:
                raise MCPToolError(f"{tool} returned non-JSON text") from exc
    raise MCPToolError(f"{tool} returned no text content")


async def post_json(url: str, payload: dict, timeout: float = DEFAULT_TIMEOUT_S) -> dict:
    """POST a structured request body and return the parsed JSON response."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload)
    except httpx.HTTPError as exc:
        raise AgentError(f"POST {url} failed: {exc}") from exc
    if resp.status_code != 200:
        raise AgentError(f"POST {url} -> HTTP {resp.status_code}: {resp.text[:300]}")
    try:
        return resp.json()
    except json.JSONDecodeError as exc:
        raise AgentError(f"POST {url} returned non-JSON body") from exc