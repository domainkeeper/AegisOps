import { useState } from 'react';
import { useApi } from '../hooks/useApi';
import { api } from '../services/api';
import { StatusBadge } from '../components/StatusBadge';
import { Timeline } from '../components/Timeline';
import { LoadingState } from '../components/LoadingState';
import { ErrorState } from '../components/ErrorState';
import type { AuditEvent } from '../types/api';

interface Props {
  incidentId: string;
}

const TABS = ['Timeline', 'Diagnosis', 'Authorization', 'Service', 'Audit'] as const;
type Tab = (typeof TABS)[number];

export function IncidentDetail({ incidentId }: Props) {
  const { data, loading, error, refresh } = useApi(() => api.getIncident(incidentId), [incidentId]);
  const [activeTab, setActiveTab] = useState<Tab>('Authorization');

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={refresh} />;
  if (!data) return <ErrorState message="Incident not found" />;

  const inc = data;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title" style={{ fontFamily: 'var(--font-mono)', fontSize: '1.1rem' }}>
            {inc.id}
          </div>
          <div className="page-subtitle">
            {inc.service} &middot; Created {inc.created_at ? new Date(inc.created_at).toLocaleString() : '-'}
            {inc.resolved_at && <> &middot; Resolved {new Date(inc.resolved_at).toLocaleString()}</>}
          </div>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <StatusBadge status={inc.status} />
          <StatusBadge status={inc.severity} />
          {inc.governed !== undefined && (
            <StatusBadge status={inc.governed ? 'governed' : 'ungoverned'} />
          )}
        </div>
      </div>

      {inc.error && (
        <div className="error-state" style={{ marginBottom: '1rem' }}>{inc.error}</div>
      )}

      <div className="tabs">
        {TABS.map(tab => (
          <div
            key={tab}
            className={`tab ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </div>
        ))}
      </div>

      {activeTab === 'Timeline' && (
        <div className="card">
          {inc.timeline && inc.timeline.length > 0 ? (
            <Timeline events={inc.timeline} />
          ) : (
            <div className="empty-state">No timeline events recorded</div>
          )}
        </div>
      )}

      {activeTab === 'Diagnosis' && (
        <div className="card">
          {inc.diagnosis ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <div className="card-header">Diagnosis</div>
                <div style={{ fontSize: '0.9rem', lineHeight: 1.6 }}>{inc.diagnosis}</div>
              </div>
              {inc.recommended_action && (
                <div>
                  <div className="card-header">Recommended Action</div>
                  <div style={{ fontSize: '0.9rem', color: 'var(--accent)' }}>{inc.recommended_action}</div>
                </div>
              )}
              {inc.resolution && (
                <div>
                  <div className="card-header">Resolution</div>
                  <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>{inc.resolution}</div>
                </div>
              )}
              <div className="grid-3">
                {inc.intent_token_status && (
                  <div className="metric-card">
                    <div className="metric-value">{inc.intent_token_status}</div>
                    <div className="metric-label">Intent Token</div>
                  </div>
                )}
                {inc.governed !== undefined && (
                  <div className="metric-card">
                    <div className="metric-value">{inc.governed ? 'Yes' : 'No'}</div>
                    <div className="metric-label">Governed</div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="empty-state">No diagnosis data available</div>
          )}
        </div>
      )}

      {activeTab === 'Authorization' && (
        <AuthorizationEvents incidentId={incidentId} />
      )}

      {activeTab === 'Service' && (
        <div className="card">
          <div className="card-header">Service Information</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Service</div>
              <div style={{ fontSize: '0.95rem' }}>{inc.service || 'N/A'}</div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Status</div>
              <StatusBadge status={inc.status} />
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Severity</div>
              <StatusBadge status={inc.severity} />
            </div>
            {inc.description && (
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Description</div>
                <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>{inc.description}</div>
              </div>
            )}
            {inc.intent_token_status && (
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Intent Token</div>
                <StatusBadge status={inc.intent_token_status} />
              </div>
            )}
            {inc.governed !== undefined && (
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Governed</div>
                <StatusBadge status={inc.governed ? 'governed' : 'ungoverned'} />
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'Audit' && (
        <IncidentAudit incidentId={incidentId} />
      )}
    </div>
  );
}

function AuthorizationEvents({ incidentId }: { incidentId: string }) {
  const { data, loading, error, refresh } = useApi(() => api.getIncidentAudit(incidentId), [incidentId]);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={refresh} />;
  if (!data || !data.audit_events || data.audit_events.length === 0) {
    return <div className="card"><div className="empty-state">No authorization events recorded for this incident</div></div>;
  }

  const events = data.audit_events;
  const blocked = events.filter(e => e.status === 'blocked');
  const allowed = events.filter(e => e.status === 'allowed' || e.status === 'success');
  const errors = events.filter(e => e.status === 'error' || e.status === 'failed');

  return (
    <div>
      <div className="card" style={{ marginBottom: '1rem' }}>
        <div className="card-header">Authorization Decision Summary</div>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
          Each agent's requested action and the authority system's decision. This is the central security
          visualization showing what was blocked vs. allowed.
        </p>
      </div>
      <div className="grid-2">
        {blocked.map((ev, i) => (
          <AuditEventCard key={`blocked-${i}`} event={ev} />
        ))}
        {allowed.map((ev, i) => (
          <AuditEventCard key={`allowed-${i}`} event={ev} />
        ))}
        {errors.map((ev, i) => (
          <AuditEventCard key={`error-${i}`} event={ev} />
        ))}
      </div>
    </div>
  );
}

function AuditEventCard({ event }: { event: AuditEvent }) {
  const borderColor =
    event.status === 'allowed' || event.status === 'success'
      ? 'rgba(62,207,142,0.3)'
      : event.status === 'blocked'
        ? 'rgba(231,76,60,0.3)'
        : 'rgba(230,126,34,0.3)';

  const bgColor =
    event.status === 'allowed' || event.status === 'success'
      ? 'rgba(62,207,142,0.05)'
      : event.status === 'blocked'
        ? 'rgba(231,76,60,0.05)'
        : 'rgba(230,126,34,0.05)';

  return (
    <div
      className="card"
      style={{
        borderColor,
        background: bgColor,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
        <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{event.agent}</span>
        <StatusBadge status={event.status} />
      </div>
      <div style={{ marginBottom: '0.75rem' }}>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.15rem' }}>Requested Action</div>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', background: 'var(--bg-primary)', padding: '0.2rem 0.5rem', borderRadius: '4px' }}>
          {event.action}
        </span>
      </div>
      <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', borderTop: '1px solid var(--border)', paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        {event.detail || event.error_type || '-'}
      </div>
    </div>
  );
}

function IncidentAudit({ incidentId }: { incidentId: string }) {
  const { data, loading, error, refresh } = useApi(() => api.getIncidentAudit(incidentId), [incidentId]);
  const [expanded, setExpanded] = useState(false);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={refresh} />;
  if (!data || !data.audit_events || data.audit_events.length === 0) return <div className="empty-state">No audit events for this incident</div>;

  const events = data.audit_events;
  const displayed = expanded ? events : events.slice(0, 20);

  return (
    <div className="card">
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>Audit Events ({events.length})</span>
        {events.length > 20 && (
          <button className="btn" onClick={() => setExpanded(!expanded)} style={{ fontSize: '0.75rem', padding: '0.2rem 0.6rem' }}>
            {expanded ? 'Collapse' : 'Show All'}
          </button>
        )}
      </div>
      <table className="data-table">
        <thead>
          <tr>
            <th>Time</th>
            <th>Agent</th>
            <th>Action</th>
            <th>Status</th>
            <th>Detail</th>
          </tr>
        </thead>
        <tbody>
          {displayed.map((ev, i) => (
            <tr key={i}>
              <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
                {ev.created_at ? new Date(ev.created_at).toLocaleString() : '-'}
              </td>
              <td>{ev.agent}</td>
              <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>{ev.action}</td>
              <td><StatusBadge status={ev.status} /></td>
              <td style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {ev.detail || ev.error_type || '-'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {events.length > 20 && (
        <div style={{ marginTop: '0.5rem', textAlign: 'center' }}>
          <button className="btn" onClick={() => setExpanded(!expanded)} style={{ fontSize: '0.75rem', padding: '0.2rem 0.6rem' }}>
            {expanded ? 'Collapse' : 'Show All'}
          </button>
        </div>
      )}
    </div>
  );
}