"""AegisOps API — Pydantic response models (frontend-facing).

These are the PUBLIC response shapes.  NEVER expose internal implementation
objects, tokens, secrets, raw database rows, or internal identifiers.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

__all__: list[str] = [
    "ErrorDetail",
    "ErrorResponse",
    "HealthResponse",
    "ReadinessResponse",
    "ComponentStatus",
    "SystemStatusResponse",
    "IncidentSummary",
    "IncidentListResponse",
    "TimelineEventResponse",
    "DiagnosisResponse",
    "AgentActionResponse",
    "RemediationResponse",
    "IncidentDetailResponse",
    "AuditEventResponse",
    "AuditListResponse",
    "AuthorityEntry",
    "AuthorityResponse",
    "ServiceStatusResponse",
    "AgentStatusResponse",
    "MCPStatusResponse",
    "ConfigurationResponse",
    "LoginRequest",
    "LoginResponse",
    "SessionResponse",
]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str = ""


class ErrorResponse(BaseModel):
    error: ErrorDetail


# ---------------------------------------------------------------------------
# Health / readiness / system
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    service: str
    status: str  # healthy | degraded | offline
    uptime_seconds: int


class ReadinessResponse(BaseModel):
    status: str  # ready | not_ready
    checks: dict[str, str]  # component -> status


class ComponentStatus(BaseModel):
    name: str
    status: str  # healthy | degraded | offline | not_configured
    detail: str = ""


class SystemStatusResponse(BaseModel):
    overall: str
    components: list[ComponentStatus]


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------

class IncidentSummary(BaseModel):
    id: str
    service: str
    status: str
    severity: str
    created_at: str
    updated_at: str
    summary: str = ""
    governed: bool = False
    error: str | None = None


class IncidentListResponse(BaseModel):
    incidents: list[IncidentSummary]
    total: int
    limit: int
    offset: int


class TimelineEventResponse(BaseModel):
    ts: float
    stage: str
    status: str
    detail: str = ""
    formatted_time: str = ""


class DiagnosisResponse(BaseModel):
    diagnosis: str = ""
    confidence: float = 0.0
    root_cause: str = ""
    requires_remediation: bool = False
    recommended_action: str = ""
    target_service: str = ""
    llm_source: str = ""
    governed_restart_attempted: bool = False
    governed_restart_blocked: bool = False
    governed_restart_error: str | None = None


class AgentActionResponse(BaseModel):
    agent: str
    requested_action: str
    authority_actions: list[str] = []
    result: str  # allowed | blocked | error
    reason: str = ""


class RemediationResponse(BaseModel):
    operation: str = ""
    success: bool = False
    noop: bool = False
    started_at: str | None = None
    health: dict | None = None


class IncidentDetailResponse(BaseModel):
    id: str
    service: str
    status: str
    severity: str
    description: str = ""
    created_at: str
    updated_at: str
    resolved_at: str | None = None
    summary: str = ""
    diagnosis: DiagnosisResponse | None = None
    remediation: RemediationResponse | None = None
    timeline: list[TimelineEventResponse] = []
    authorization_events: list[AgentActionResponse] = []
    intent_token_status: str = ""
    governed: bool = False
    error: str | None = None


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

class AuditEventResponse(BaseModel):
    incident_id: str
    agent: str
    parent_agent: str | None = None
    action: str
    status: str
    delegation_id: str | None = None
    error_type: str | None = None
    detail: str = ""
    created_at: str


class AuditListResponse(BaseModel):
    events: list[AuditEventResponse]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Authority
# ---------------------------------------------------------------------------

class AuthorityEntry(BaseModel):
    agent: str
    allowed_actions: list[str]
    steps: list[str]


class AuthorityResponse(BaseModel):
    plan_actions: list[str]
    delegations: list[AuthorityEntry]
    note: str = ""


# ---------------------------------------------------------------------------
# Services / agents / MCP
# ---------------------------------------------------------------------------

class ServiceStatusResponse(BaseModel):
    name: str
    health: str
    container: str | None = None
    started_at: str | None = None
    restart_count: int | None = None
    image: str | None = None
    last_incident: str | None = None


class AgentStatusResponse(BaseModel):
    name: str
    status: str
    port: int
    error: str = ""


class MCPStatusResponse(BaseModel):
    name: str
    port: int
    status: str  # registered | online | offline | unknown
    reachable: bool = False
    error: str = ""


# ---------------------------------------------------------------------------
# Configuration / session
# ---------------------------------------------------------------------------

class ConfigurationResponse(BaseModel):
    gemini_configured: bool
    gemini_model: str = ""
    armoriq_configured: bool
    armoriq_connected: bool = False
    database: str = ""
    agents: int = 0
    mcps: int = 0
    authentication: str = ""  # enabled | disabled
    version: str = ""


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str


class SessionResponse(BaseModel):
    authenticated: bool
    username: str = ""