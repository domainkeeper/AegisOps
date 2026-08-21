export interface ComponentStatus {
  name: string;
  status: 'healthy' | 'degraded' | 'offline' | 'not_configured';
  detail: string;
}

export interface SystemStatus {
  overall: string;
  components: ComponentStatus[];
}

export interface IncidentSummary {
  id: string;
  service: string;
  status: string;
  severity: string;
  created_at: string;
  updated_at: string;
  summary?: string;
  governed?: boolean;
  error?: string | null;
}

export interface IncidentListResponse {
  incidents: IncidentSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface TimelineEvent {
  ts: number;
  stage: string;
  status: string;
  detail?: string;
  formatted_time?: string;
}

export interface DiagnosisData {
  diagnosis?: string;
  confidence?: number;
  root_cause?: string;
  requires_remediation?: boolean;
  recommended_action?: string;
  target_service?: string;
  llm_source?: string;
  governed_restart_attempted?: boolean;
  governed_restart_blocked?: boolean;
  governed_restart_error?: string | null;
}

export interface AgentAction {
  agent: string;
  requested_action: string;
  authority_actions: string[];
  result: 'allowed' | 'blocked' | 'error';
  reason: string;
}

export interface IncidentDetail {
  id: string;
  service: string;
  status: string;
  severity: string;
  description?: string;
  created_at: string;
  updated_at: string;
  resolved_at?: string | null;
  summary?: string;
  diagnosis?: DiagnosisData | null;
  timeline?: TimelineEvent[];
  authorization_events?: AgentAction[];
  intent_token_status?: string;
  governed?: boolean;
  error?: string | null;
}

export interface AuditEvent {
  incident_id: string;
  agent: string;
  parent_agent?: string | null;
  action: string;
  status: string;
  delegation_id?: string | null;
  error_type?: string | null;
  detail?: string;
  created_at: string;
}

export interface AuditListResponse {
  events: AuditEvent[];
  total: number;
  limit: number;
  offset: number;
}

export interface AuthorityEntry {
  agent: string;
  allowed_actions: string[];
  steps: string[];
}

export interface AuthorityResponse {
  plan_actions: string[];
  delegations: AuthorityEntry[];
  note: string;
}

export interface ServiceStatus {
  name: string;
  health: string;
  container?: string | null;
  started_at?: string | null;
  restart_count?: number | null;
  image?: string | null;
  last_incident?: string | null;
}

export interface AgentStatus {
  log_agent: { status: string };
  diagnosis_agent: { status: string };
  remediation_agent: { status: string };
  commander: { status: string };
}

export interface MCPStatus {
  log_mcp: { status: string };
  diagnostic_mcp: { status: string };
  remediation_mcp: { status: string };
}

export interface LoginResponse {
  token: string;
  username: string;
}

export interface SessionResponse {
  authenticated: boolean;
  username?: string;
  mode?: string;
}