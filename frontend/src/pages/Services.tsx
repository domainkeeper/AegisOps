import { useApi } from '../hooks/useApi';
import { api } from '../services/api';
import { StatusBadge } from '../components/StatusBadge';
import { LoadingState } from '../components/LoadingState';
import { ErrorState } from '../components/ErrorState';

export function Services() {
  const { data, loading, error, refresh } = useApi(() => api.services(), []);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={refresh} />;
  if (!data) return <div className="empty-state">No services reported</div>;

  const services = data.services ?? [];

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Services</div>
          <div className="page-subtitle">Service health and container status</div>
        </div>
      </div>

      {services.length === 0 ? (
        <div className="empty-state">No services reported</div>
      ) : (
        <div className="grid-4">
          {services.map(svc => {
            const healthStatus = typeof svc.health === 'string' ? svc.health : (svc.health as { status?: string } | null)?.status || 'unknown';
            const dockerInfo = svc.docker as { name?: string; state?: string; image?: string } | null | undefined;
            return (
              <div key={svc.name} className="card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                  <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{svc.name}</span>
                  <StatusBadge status={healthStatus} />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.8rem' }}>
                  {dockerInfo?.image && (
                    <div>
                      <span style={{ color: 'var(--text-muted)' }}>Image: </span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                        {dockerInfo.image}
                      </span>
                    </div>
                  )}
                  {dockerInfo?.name && (
                    <div>
                      <span style={{ color: 'var(--text-muted)' }}>Container: </span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                        {dockerInfo.name}
                      </span>
                    </div>
                  )}
                  {dockerInfo?.state && (
                    <div>
                      <span style={{ color: 'var(--text-muted)' }}>State: </span>
                      <span style={{ color: 'var(--text-secondary)' }}>{dockerInfo.state}</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
