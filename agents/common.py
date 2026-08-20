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

import asyncio
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


class ArmorIQRejection(AgentError):
    """ArmorIQ rejected a governed invoke() call (blocked, invalid, expired...).

    Carries the VERIFIED exception type from the SDK (e.g.
    ``PolicyBlockedException``) as structured metadata - it is the SDK's own
    class name, never a local guess. ``blocked`` is a convenience flag for the
    single case we treat as an explicit policy block.
    """

    def __init__(self, message: str, error_type: str, blocked: bool = False) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.blocked = blocked


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
    authority: "DelegatedAuthority | None" = None

    @field_validator("limit")
    @classmethod
    def _limit(cls, v: int) -> int:
        if not 1 <= v <= 500:
            raise ValueError("limit must be between 1 and 500")
        return v


class DelegatedAuthority(BaseModel):
    """A delegated token handed to a child agent for the governed path.

    SENSITIVE: `token` is the serialized IntentToken. It is transported only
    to the owning child over the local agent HTTP channel, kept in memory,
    and NEVER logged, persisted, or returned in API responses.
    """

    agent: str = Field(min_length=1, max_length=64)
    delegation_id: str = Field(min_length=1, max_length=128)
    allowed_actions: list[str] = []
    expires_at: float = 0.0
    target_agent: str | None = None
    token: dict[str, Any] = {}


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
    authority: DelegatedAuthority | None = None


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
    # Phase 8: the deliberate governed restart attempt (same action as the
    # Remediation Agent, different authority). Recorded honestly - blocked or
    # otherwise - never fabricated and never silently skipped.
    governed_restart_attempted: bool = False
    governed_restart_blocked: bool = False
    governed_restart_error: str | None = None
    governed_restart_result: dict[str, Any] | None = None
    status: str = "ok"
    error: str | None = None


class RemediationRequest(BaseModel):
    incident_id: str = Field(min_length=1, max_length=128)
    service: str = Field(min_length=1, max_length=64)
    authority: DelegatedAuthority | None = None


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
    # Phase 5 (intent, not enforcement): the explicit execution plan the
    # Commander captured with ArmorIQ, plus the status of the intent-token
    # handshake. The token itself is NEVER included here or logged.
    plan: dict[str, Any] | None = None
    intent_token_status: str = "not_configured"  # ready | error | not_configured
    intent_token_expires_at: str | None = None
    intent_token_error: str | None = None
    # Phase 6 (delegation): safe metadata only - delegation ids, scopes,
    # expiry. Tokens are never serialized here.
    delegations: list[dict[str, Any]] = []
    delegation_error: str | None = None
    governed: bool = False  # True when this run went Agent -> ArmorIQ -> MCP
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

RETRY_ATTEMPTS = 2
RETRY_BACKOFF_S = 0.5


def _is_transient(exc: BaseException) -> bool:
    """True for transport-level failures worth one bounded retry.

    Deliberately narrow: tool/validation failures and authorization rejections
    are NEVER retried - retrying would duplicate a side effect (e.g. a restart)
    or hide a real denial. Only connection/read/network errors qualify.
    """
    return isinstance(
        exc,
        (
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.RemoteProtocolError,
            httpx.TransportError,
            ConnectionError,
            TimeoutError,
        ),
    ) or (
        isinstance(exc, OSError)
        and getattr(exc, "winerror", None) in (10061, 10054)  # refused / reset on Windows
        or getattr(exc, "errno", None) in (104, 111, 32)  # reset / refused / broken pipe
    )


async def call_mcp(url: str, tool: str, arguments: dict, timeout: float = MCP_TIMEOUT_S) -> dict:
    """Invoke a single MCP tool and return its parsed JSON payload.

    Agent -> MCP -> Docker. Agents never talk to Docker directly.
    A bounded retry covers transient transport failures only (server not yet
    up, connection reset); tool errors and rejections are surfaced as-is.
    """
    last_error: Exception | None = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            async with Client(url, read_timeout_seconds=timeout) as client:
                result = await client.call_tool(tool, arguments)
        except Exception as exc:
            last_error = exc
            if attempt + 1 < RETRY_ATTEMPTS and _is_transient(exc):
                await asyncio.sleep(RETRY_BACKOFF_S * (attempt + 1))
                continue
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
    raise MCPToolError(f"{tool} via {url} failed: {last_error}")  # pragma: no cover


async def post_json(url: str, payload: dict, timeout: float = DEFAULT_TIMEOUT_S) -> dict:
    """POST a structured request body and return the parsed JSON response.

    A bounded retry covers transient transport failures (peer starting up,
    dropped connection) and HTTP 5xx; 4xx responses are never retried.
    """
    last_error: AgentError | None = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=payload)
        except httpx.HTTPError as exc:
            last_error = AgentError(f"POST {url} failed: {exc}")
            if attempt + 1 < RETRY_ATTEMPTS and _is_transient(exc):
                await asyncio.sleep(RETRY_BACKOFF_S * (attempt + 1))
                continue
            raise last_error from exc
        if resp.status_code >= 500:
            last_error = AgentError(f"POST {url} -> HTTP {resp.status_code}: {resp.text[:300]}")
            if attempt + 1 < RETRY_ATTEMPTS:
                await asyncio.sleep(RETRY_BACKOFF_S * (attempt + 1))
                continue
            raise last_error
        if resp.status_code != 200:
            raise AgentError(f"POST {url} -> HTTP {resp.status_code}: {resp.text[:300]}")
        try:
            return resp.json()
        except json.JSONDecodeError as exc:
            raise AgentError(f"POST {url} returned non-JSON body") from exc
    raise last_error  # type: ignore[misc]  # pragma: no cover


def invoke_governed(
    *,
    agent: str,
    authority: DelegatedAuthority,
    mcp: str,
    action: str,
    params: dict,
    incident_id: str,
) -> dict:
    """Agent -> ArmorIQ invoke() -> MCP -> real resource (governed path).

    Uses the child's delegated token (received over HTTP from the Commander)
    and the child's own per-agent email scope. Verified against armoriq-sdk
    0.6.10: invoke(mcp, action, intent_token, params, merkle_proof, user_email).

    Local defense-in-depth (never a substitute for ArmorIQ's decision):
    - the authority must be bound to THIS agent's identity (no token
      substitution / cross-agent reuse),
    - an authority that is already expired fails fast with a clear error
      (the SDK also rejects expired tokens; this surfaces it before the call),
    - any SDK failure - authorization denial, transport error, malformed
      response - is recorded in the local audit mirror with its VERIFIED
      exception type and raised as ``ArmorIQRejection`` so the Commander marks
      the incident FAILED. No exception class is guessed locally for the block
      case: the SDK's own class name flows through as structured metadata.

    Deliberately NOT checked here: whether ``action`` is inside the authority's
    ``allowed_actions``. The Phase 8 probe (Diagnosis Agent deliberately
    attempting ``restart_service`` with its own, narrower authority) depends on
    ArmorIQ - not this layer - being the enforcement point.
    """
    from armoriq.client_setup import agent_email, get_client
    from armoriq_sdk import ArmorIQException
    from armoriq_sdk.models import IntentToken
    from database.audit import audit

    # Identity binding: a delegated authority is minted for one child and must
    # only ever be used by that child.
    if authority.agent != agent:
        raise ArmorIQRejection(
            f"delegated authority for '{authority.agent}' cannot be used by '{agent}'",
            error_type="IdentityMismatchError",
        )

    token = IntentToken.model_validate(authority.token)
    email = agent_email(agent)

    # Expiry pre-check: fail fast and honestly before the network call. The SDK
    # also enforces this (TokenExpiredException); this guard keeps the failure
    # local, immediate, and clearly attributed.
    if authority.expires_at and time.time() > authority.expires_at:
        audit(
            incident_id=incident_id,
            agent=agent,
            parent_agent="commander",
            action=f"{mcp}.{action}",
            status="error",
            delegation_id=authority.delegation_id,
            error_type="TokenExpiredException",
            detail="delegated authority expired before invoke",
        )
        raise ArmorIQRejection(
            f"delegated authority expired (expires_at={authority.expires_at:.0f})",
            error_type="TokenExpiredException",
        )

    try:
        result = get_client().invoke(
            mcp=mcp,
            action=action,
            intent_token=token,
            params=params,
            user_email=email,
        )
    except ArmorIQException as exc:
        error_type = type(exc).__name__
        blocked = error_type == "PolicyBlockedException"
        audit(
            incident_id=incident_id,
            agent=agent,
            parent_agent="commander",
            action=f"{mcp}.{action}",
            status="blocked" if blocked else "error",
            delegation_id=authority.delegation_id,
            error_type=error_type,
            detail=str(exc)[:400],
        )
        raise ArmorIQRejection(
            f"ArmorIQ governed call {mcp}.{action} rejected ({error_type}): {exc}",
            error_type=error_type,
            blocked=blocked,
        ) from exc
    except Exception as exc:  # noqa: BLE001 - any SDK/transport failure is surfaced honestly
        error_type = type(exc).__name__
        audit(
            incident_id=incident_id,
            agent=agent,
            parent_agent="commander",
            action=f"{mcp}.{action}",
            status="error",
            delegation_id=authority.delegation_id,
            error_type=error_type,
            detail=str(exc)[:400],
        )
        raise ArmorIQRejection(
            f"ArmorIQ governed call {mcp}.{action} failed ({error_type}): {exc}",
            error_type=error_type,
        ) from exc

    audit(
        incident_id=incident_id,
        agent=agent,
        parent_agent="commander",
        action=f"{mcp}.{action}",
        status="success",
        delegation_id=authority.delegation_id,
        error_type=None,
        detail=f"verified={getattr(result, 'verified', None)}, execution_time={getattr(result, 'execution_time', None)}",
    )

    payload = getattr(result, "result", None)
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise AgentError(f"ArmorIQ invoke {mcp}.{action} returned non-JSON payload") from exc
    if isinstance(payload, dict):
        return payload
    raise AgentError(f"ArmorIQ invoke {mcp}.{action} returned unexpected payload type")