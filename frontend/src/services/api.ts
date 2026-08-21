import type {
  SystemStatus,
  IncidentListResponse,
  IncidentDetail,
  TimelineEvent,
  AuditEvent,
  AuditListResponse,
  AuthorityResponse,
  ServiceStatus,
  AgentStatus,
  MCPStatus,
  LoginResponse,
  SessionResponse,
} from '../types/api';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem('aegisops_token');
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string>),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const resp = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new ApiError(resp.status, body?.error?.message || resp.statusText);
  }
  return resp.json() as Promise<T>;
}

export const api = {
  health: () => request<Record<string, unknown>>('/health/live'),
  ready: () => request<Record<string, unknown>>('/health/ready'),
  systemStatus: () => request<SystemStatus>('/system/status'),
  configuration: () => request<Record<string, unknown>>('/system/configuration'),

  listIncidents: (params?: { limit?: number; offset?: number; status?: string }) => {
    const q = new URLSearchParams();
    if (params?.limit !== undefined) q.set('limit', String(params.limit));
    if (params?.offset !== undefined) q.set('offset', String(params.offset));
    if (params?.status) q.set('status', params.status);
    return request<IncidentListResponse>(`/incidents?${q}`);
  },

  getIncident: (id: string) => request<IncidentDetail>(`/incidents/${id}`),

  createIncident: (data: {
    incident_id: string;
    service?: string;
    severity?: string;
    description?: string;
  }) => request<IncidentDetail>('/incidents', { method: 'POST', body: JSON.stringify(data) }),

  getIncidentTimeline: (id: string) => request<TimelineEvent[]>(`/incidents/${id}/timeline`),

  getIncidentAudit: (id: string) => request<AuditEvent[]>(`/incidents/${id}/audit`),

  listAudit: (params?: {
    limit?: number;
    offset?: number;
    incident_id?: string;
    status?: string;
  }) => {
    const q = new URLSearchParams();
    if (params?.limit !== undefined) q.set('limit', String(params.limit));
    if (params?.offset !== undefined) q.set('offset', String(params.offset));
    if (params?.incident_id) q.set('incident_id', params.incident_id);
    if (params?.status) q.set('status', params.status);
    return request<AuditListResponse>(`/audit?${q}`);
  },

  authority: () => request<AuthorityResponse>('/security/authority'),

  services: () => request<ServiceStatus[]>('/services'),

  agents: () => request<AgentStatus>('/agents'),

  mcps: () => request<MCPStatus>('/mcps'),

  login: (username: string, password: string) =>
    request<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),

  session: () => request<SessionResponse>('/auth/session'),

  logout: () => request<Record<string, unknown>>('/auth/logout', { method: 'POST' }),
};