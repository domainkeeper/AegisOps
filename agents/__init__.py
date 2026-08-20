"""AegisOps agents package.

Phase 4 - the unguarded multi-agent system. Four independent processes that
collaborate over plain HTTP to resolve an auth-api incident end to end:

    commander (8094) -> log_agent (8091) -> log_mcp (8081)
    commander      -> diagnosis_agent (8092) -> diagnostic_mcp (8082)
    diagnosis_agent -> remediation_mcp (8083)  # UNGUARDED baseline attempt
    commander      -> remediation_agent (8093) -> remediation_mcp (8083)

There is intentionally NO ArmorIQ enforcement here. The Diagnosis Agent can
perform the remediation itself; later phases insert ArmorIQ and turn that exact
path into the BLOCKED demonstration.
"""

from agents.common import (  # noqa: F401
    COMMANDER_URL,
    DIAGNOSIS_AGENT_URL,
    DIAGNOSTIC_MCP_URL,
    LOG_AGENT_URL,
    LOG_MCP_URL,
    REMEDIATION_AGENT_URL,
    REMEDIATION_MCP_URL,
    AgentError,
    DiagnosisRequest,
    DiagnosisResult,
    EvidenceLine,
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