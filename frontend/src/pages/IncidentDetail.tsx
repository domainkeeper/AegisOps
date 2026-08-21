import { useState } from 'react';
import { useApi } from '../hooks/useApi';
import { api } from '../services/api';
import { StatusBadge } from '../components/StatusBadge';
import { Timeline } from '../components/Timeline';
import { LoadingState } from '../components/LoadingState';
import { ErrorState } from '../components/ErrorState';
import type { AgentAction } from '../types/api';

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
            {inc.service} &middot; Created {new Date(inc.created_at).toLocaleString()}
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
              {inc.diagnosis.diagnosis && (
                <div>
                  <div className="card-header">Diagnosis</div>
                  <div style={{ fontSize: '0.9rem', lineHeight: 1.6 }}>{inc.diagnosis.diagnosis}</div>
                </div>
              )}
              {inc.diagnosis.root_cause && (
                <div>
                  <div className="card-header">Root Cause</div>
                  <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>{inc.diagnosis.root_cause}</div>
                </div>
              )}
              {inc.diagnosis.recommended_action && (
                <div>
                  <div className="card-header">Recommended Action</div>
                  <div style={{ fontSize: '0.9rem', color: 'var(--accent)' }}>{inc.diagnosis.recommended_action}</div>
                </div>
              )}
              <div className="grid-3">
                {inc.diagnosis.confidence !== undefined && (
                  <div className="metric-card">
                    <div className="metric-value">{Math.round(inc.diagnosis.confidence * 100)}%</div>
                    <div className="metric-label">Confidence</div>
                  </div>
                )}
                {inc.diagnosis.llm_source && (
                  <div className="metric-card">
                    <div className="metric-value" style={{ fontSize: '1rem' }}>{inc.diagnosis.llm_source}</div>
                    <div className="metric-label">LLM Source</div>
                  </div>
                )}
                {inc.diagnosis.requires_remediation !== undefined && (
                  <div className="metric-card">
                    <div className="metric-value">{inc.diagnosis.requires_remediation ? 'Yes' : 'No'}</div>
                    <div className="metric-label">Remediation Required</div>
                  </div>
                )}
              </div>
              {inc.diagnosis.governed_restart_attempted && (
                <div style={{ marginTop: '0.5rem' }}>
                  <div className="card-header">Governed Restart</div>
                  <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    <StatusBadge status={inc.diagnosis.governed_restart_blocked ? 'blocked' : 'allowed'} />
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                      {inc.diagnosis.governed_restart_blocked
                        ? 'Restart was blocked by security policy'
                        : 'Restart was authorized'}
                    </span>
                  </div>
                  {inc.diagnosis.governed_restart_error && (
                    <div style={{ fontSize: '0.8rem', color: 'var(--red)', marginTop: '0.25rem' }}>
                      {inc.diagnosis.governed_restart_error}
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="empty-state">No diagnosis data available</div>
          )}
        </div>
      )}

      {activeTab === 'Authorization' && (
        <div>
          {inc.authorization_events && inc.authorization_events.length > 0 ? (
            <div>
              <div className="card" style={{ marginBottom: '1rem' }}>
                <div className="card-header">Authorization Decision Summary</div>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                  Each agent's requested action and the authority system's decision. This is the central security
                  visualization showing what was blocked vs. allowed.
                </p>
              </div>
              <div className="grid-2">
                {inc.authorization_events
                  .filter(e => e.result === 'blocked')
                  .map((ev, i) => (
                    <AuthorizationCard key={`blocked-${i}`} event={ev} />
                  ))}
                {inc.authorization_events
                  .filter(e => e.result === 'allowed')
                  .map((ev, i) => (
                    <AuthorizationCard key={`allowed-${i}`} event={ev} />
                  ))}
                {inc.authorization_events
                  .filter(e => e.result === 'error')
                  .map((ev, i) => (
                    <AuthorizationCard key={`error-${i}`} event={ev} />
                  ))}
              </div>
            </div>
          ) : (
            <div className="card">
              <div className="empty-state">No authorization events recorded for this incident</div>
            </div>
          )}
        </div>
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
          </div>
        </div>
      )}

      {activeTab === 'Audit' && (
        <IncidentAudit incidentId={incidentId} />
      )}
    </div>
  );
}

function AuthorizationCard({ event }: { event: AgentAction }) {
  const borderColor =
    event.result === 'allowed'
      ? 'rgba(62,207,142,0.3)'
      : event.result === 'blocked'
        ? 'rgba(231,76,60,0.3)'
        : 'rgba(230,126,34,0.3)';

  const bgColor =
    event.result === 'allowed'
      ? 'rgba(62,207,142,0.05)'
      : event.result === 'blocked'
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
        <StatusBadge status={event.result} />
      </div>
      <div style={{ marginBottom: '0.75rem' }}>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.15rem' }}>Requested Action</div>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', background: 'var(--bg-primary)', padding: '0.2rem 0.5rem', borderRadius: '4px' }}>
          {event.requested_action}
        </span>
      </div>
      {event.authority_actions.length > 0 && (
        <div style={{ marginBottom: '0.5rem' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>Authority Actions</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }}>
            {event.authority_actions.map((a, i) => (
              <span
                key={i}
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.75rem',
                  background: 'var(--bg-primary)',
                  border: '1px solid var(--border)',
                  borderRadius: '3px',
                  padding: '0.15rem 0.4rem',
                }}
              >
                {a}
              </span>
            ))}
          </div>
        </div>
      )}
      <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', borderTop: '1px solid var(--border)', paddingTop: '0.5rem', marginTop: '0.25rem' }}>
        {event.reason}
      </div>
    </div>
  );
}

function IncidentAudit({ incidentId }: { incidentId: string }) {
  const { data, loading, error, refresh } = useApi(() => api.getIncidentAudit(incidentId), [incidentId]);
  const [expanded, setExpanded] = useState(false);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={refresh} />;
  if (!data || data.length === 0) return <div className="empty-state">No audit events for this incident</div>;

  const displayed = expanded ? data : data.slice(0, 20);

  return (
    <div className="card">
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>Audit Events ({data.length})</span>
        {data.length > 20 && (
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
                {new Date(ev.created_at).toLocaleString()}
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
    </div>
  );
}