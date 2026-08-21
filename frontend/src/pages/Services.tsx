import { useApi } from '../hooks/useApi';
import { api } from '../services/api';
import { StatusBadge } from '../components/StatusBadge';
import { LoadingState } from '../components/LoadingState';
import { ErrorState } from '../components/ErrorState';

export function Services() {
  const { data, loading, error, refresh } = useApi(() => api.services(), []);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={refresh} />;
  if (!data || data.length === 0) return <div className="empty-state">No services reported</div>;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Services</div>
          <div className="page-subtitle">Service health and container status</div>
        </div>
      </div>

      <div className="grid-4">
        {data.map(svc => (
          <div key={svc.name} className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{svc.name}</span>
              <StatusBadge status={svc.health} />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.8rem' }}>
              {svc.image && (
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Image: </span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                    {svc.image}
                  </span>
                </div>
              )}
              {svc.container && (
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Container: </span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                    {svc.container}
                  </span>
                </div>
              )}
              {svc.started_at && (
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Started: </span>
                  <span style={{ color: 'var(--text-secondary)' }}>
                    {new Date(svc.started_at).toLocaleString()}
                  </span>
                </div>
              )}
              {svc.restart_count !== null && svc.restart_count !== undefined && (
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Restarts: </span>
                  <span style={{ color: 'var(--text-secondary)' }}>{svc.restart_count}</span>
                </div>
              )}
              {svc.last_incident && (
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Last Incident: </span>
                  <a
                    href={`/incidents/${svc.last_incident}`}
                    onClick={e => {
                      e.preventDefault();
                      window.history.pushState({}, '', `/incidents/${svc.last_incident}`);
                      window.dispatchEvent(new PopStateEvent('popstate'));
                    }}
                    style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}
                  >
                    {svc.last_incident}
                  </a>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}