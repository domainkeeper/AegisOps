const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';
export class ApiError extends Error {
    status;
    constructor(status, message) {
        super(message);
        this.status = status;
    }
}
async function request(path, options) {
    const token = localStorage.getItem('aegisops_token');
    const headers = {
        'Content-Type': 'application/json',
        ...options?.headers,
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    const resp = await fetch(`${API_BASE}${path}`, { ...options, headers });
    if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new ApiError(resp.status, body?.error?.message || resp.statusText);
    }
    return resp.json();
}
export const api = {
    health: () => request('/health/live'),
    ready: () => request('/health/ready'),
    systemStatus: () => request('/system/status'),
    configuration: () => request('/system/configuration'),
    listIncidents: (params) => {
        const q = new URLSearchParams();
        if (params?.limit !== undefined)
            q.set('limit', String(params.limit));
        if (params?.offset !== undefined)
            q.set('offset', String(params.offset));
        if (params?.status)
            q.set('status', params.status);
        return request(`/incidents?${q}`);
    },
    getIncident: (id) => request(`/incidents/${id}`),
    createIncident: (data) => request('/incidents', { method: 'POST', body: JSON.stringify(data) }),
    getIncidentTimeline: (id) => request(`/incidents/${id}/timeline`),
    getIncidentAudit: (id) => request(`/incidents/${id}/audit`),
    listAudit: (params) => {
        const q = new URLSearchParams();
        if (params?.limit !== undefined)
            q.set('limit', String(params.limit));
        if (params?.offset !== undefined)
            q.set('offset', String(params.offset));
        if (params?.incident_id)
            q.set('incident_id', params.incident_id);
        if (params?.status)
            q.set('status', params.status);
        return request(`/audit?${q}`);
    },
    authority: () => request('/security/authority'),
    services: () => request('/services'),
    agents: () => request('/agents'),
    mcps: () => request('/mcps'),
    login: (username, password) => request('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
    }),
    session: () => request('/auth/session'),
    logout: () => request('/auth/logout', { method: 'POST' }),
};
