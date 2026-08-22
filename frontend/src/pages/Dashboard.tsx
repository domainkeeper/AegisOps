import { useMemo } from 'react';
import { useApi } from '../hooks/useApi';
import { useSSE } from '../hooks/useSSE';
import { api } from '../services/api';
import { StatusBadge } from '../components/StatusBadge';
import { LoadingState } from '../components/LoadingState';
import { ErrorState } from '../components/ErrorState';

export function Dashboard() {
  const statusReq = useApi(() => api.systemStatus(), []);
  const incidentsReq = useApi(() => api.listIncidents({ limit: 10 }), []);
  const auditReq = useApi(() => api.listAudit({ limit: 500 }), []);
  const { events: sseEvents, connected } = useSSE();

  const securitySummary = useMemo(() => {
    if (!auditReq.data?.items) return { authorized: 0, blocked: 0, failed: 0 };
    const events = auditReq.data.items;
    return {
      authorized: events.filter(e => e.status === 'allowed' || e.status === 'authorized' || e.status === 'success').length,
      blocked: events.filter(e => e.status === 'blocked').length,
      failed: events.filter(e => e.status === 'error' || e.status === 'failed').length,
    };
  }, [auditReq.data]);

  const activeIncidents = (incidentsReq.data?.items ?? []).filter(
    inc => inc.status !== 'resolved' && inc.status !== 'closed'
  );

  const systemComponents = useMemo(() => {
    if (!statusReq.data) return [];
    const agents: Record<string, string> = statusReq.data.agents ?? {};
    const mcps: Record<string, string> = statusReq.data.mcps ?? {};
    const armoriq = statusReq.data.armoriq ?? { configured: false };
    const gemini = statusReq.data.gemini ?? { configured: false };
    const auth_api = statusReq.data.auth_api ?? { http: 'unknown', docker: 'unknown' };
    return [
      ...Object.entries(agents).map(([name, status]) => ({ name: `Agent: ${name}`, status, detail: '' })),
      ...Object.entries(mcps).map(([name, status]) => ({ name: `MCP: ${name}`, status, detail: '' })),
      { name: 'ArmorIQ', status: armoriq.configured ? 'healthy' : 'not_configured', detail: armoriq.configured ? 'Configured' : 'Not configured' },
      { name: 'Gemini', status: gemini.configured ? 'healthy' : 'not_configured', detail: gemini.configured ? 'Configured' : 'Not configured' },
      { name: 'auth-api (HTTP)', status: auth_api.http || 'unknown', detail: '' },
      { name: 'auth-api (Docker)', status: auth_api.docker || 'unknown', detail: '' },
    ];
  }, [statusReq.data]);

  if (statusReq.loading && incidentsReq.loading && auditReq.loading) {
    return <LoadingState />;
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Dashboard</div>
          <div className="page-subtitle">System overview and active incidents</div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header">System Status</div>
        {statusReq.loading ? (
          <LoadingState />
        ) : statusReq.error ? (
          <ErrorState message={statusReq.error} onRetry={statusReq.refresh} />
        ) : systemComponents.length === 0 ? (
          <div className="empty-state">No components reported</div>
        ) : (
          <div className="grid-4">
            {systemComponents.map((c, i) => (
              <div key={i} className="card" style={{ padding: '0.75rem 1rem' }}>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>{c.name}</div>
                <StatusBadge status={c.status} />
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>{c.detail}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="grid-2" style={{ marginBottom: '1.5rem' }}>
        <div className="card">
          <div className="card-header">Security Summary</div>
          {auditReq.loading ? (
            <LoadingState />
          ) : auditReq.error ? (
            <ErrorState message={auditReq.error} onRetry={auditReq.refresh} />
          ) : (
            <div className="grid-3">
              <div className="metric-card">
                <div className="metric-value" style={{ color: 'var(--green)' }}>{securitySummary.authorized}</div>
                <div className="metric-label">Authorized</div>
              </div>
              <div className="metric-card">
                <div className="metric-value" style={{ color: 'var(--red)' }}>{securitySummary.blocked}</div>
                <div className="metric-label">Blocked</div>
              </div>
              <div className="metric-card">
                <div className="metric-value" style={{ color: 'var(--orange)' }}>{securitySummary.failed}</div>
                <div className="metric-label">Failed</div>
              </div>
            </div>
          )}
        </div>

        <div className="card">
          <div className="card-header">Active Incidents ({activeIncidents.length})</div>
          {incidentsReq.loading ? (
            <LoadingState />
          ) : incidentsReq.error ? (
            <ErrorState message={incidentsReq.error} onRetry={incidentsReq.refresh} />
          ) : activeIncidents.length === 0 ? (
            <div className="empty-state">No active incidents</div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Service</th>
                  <th>Severity</th>
                  <th>Status</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {activeIncidents.map(inc => (
                  <tr
                    key={inc.id}
                    onClick={() => {
                      window.history.pushState({}, '', `/incidents/${inc.id}`);
                      window.dispatchEvent(new PopStateEvent('popstate'));
                    }}
                    style={{ cursor: 'pointer' }}
                  >
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>{inc.id}</td>
                    <td>{inc.service}</td>
                    <td><StatusBadge status={inc.severity} /></td>
                    <td><StatusBadge status={inc.status} /></td>
                    <td style={{ fontSize: '0.75rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                      {inc.created_at ? new Date(inc.created_at).toLocaleString() : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-header" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          Recent Activity
          <span
            style={{
              fontSize: '0.7rem',
              fontWeight: 400,
              color: connected ? 'var(--green)' : 'var(--text-muted)',
            }}
          >
            {connected ? '● Live' : '○ Disconnected'}
          </span>
        </div>
        {sseEvents.length === 0 ? (
          <div className="empty-state">Waiting for events...</div>
        ) : (
          <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
            {sseEvents.slice(-20).reverse().map(e => (
              <div
                key={e.id}
                style={{
                  display: 'flex',
                  gap: '0.75rem',
                  padding: '0.4rem 0',
                  borderBottom: '1px solid var(--border)',
                  fontSize: '0.8rem',
                  alignItems: 'center',
                }}
              >
                <span
                  style={{
                    color: 'var(--text-muted)',
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.7rem',
                    minWidth: '14ch',
                  }}
                >
                  {e.created_at ? new Date(e.created_at).toLocaleTimeString() : '-'}
                </span>
                <StatusBadge status={e.status} />
                <span style={{ color: 'var(--text-secondary)' }}>{e.agent}</span>
                <span style={{ color: 'var(--text-muted)' }}>{e.action}</span>
                <span
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.75rem',
                    color: 'var(--text-muted)',
                    marginLeft: 'auto',
                  }}
                >
                  {e.incident_id}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}