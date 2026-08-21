import { useApi } from '../hooks/useApi';
import { api } from '../services/api';
import { StatusBadge } from '../components/StatusBadge';
import { LoadingState } from '../components/LoadingState';
import { ErrorState } from '../components/ErrorState';

export function SystemConfig() {
  const configReq = useApi(() => api.configuration(), []);
  const agentsReq = useApi(() => api.agents(), []);
  const mcpsReq = useApi(() => api.mcps(), []);

  if (configReq.loading && agentsReq.loading && mcpsReq.loading) {
    return <LoadingState />;
  }

  const gemini = configReq.data?.gemini as Record<string, unknown> | undefined;
  const armoriq = configReq.data?.armoriq as Record<string, unknown> | undefined;
  const auth = configReq.data?.auth as Record<string, unknown> | undefined;
  const cors = configReq.data?.cors_origins as string[] | undefined;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">System Configuration</div>
          <div className="page-subtitle">Runtime configuration overview (no secrets shown)</div>
        </div>
      </div>

      <div className="grid-2" style={{ marginBottom: '1.5rem' }}>
        <div className="card">
          <div className="card-header">Gemini</div>
          {configReq.loading ? (
            <LoadingState />
          ) : configReq.error ? (
            <ErrorState message={configReq.error} onRetry={configReq.refresh} />
          ) : !gemini ? (
            <div className="empty-state">Not configured</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <StatusBadge status={gemini.configured ? 'healthy' : 'not_configured'} />
                <span style={{ fontSize: '0.85rem' }}>{gemini.configured ? 'Configured' : 'Not Configured'}</span>
              </div>
               {Boolean(gemini.model) && (
                <div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Model: </span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                    {String(gemini.model as string)}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="card">
          <div className="card-header">ArmorIQ</div>
          {configReq.loading ? (
            <LoadingState />
          ) : configReq.error ? (
            <ErrorState message={configReq.error} onRetry={configReq.refresh} />
          ) : !armoriq ? (
            <div className="empty-state">Not configured</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <StatusBadge status={armoriq.configured ? 'healthy' : 'not_configured'} />
                <span style={{ fontSize: '0.85rem' }}>{armoriq.configured ? 'Configured' : 'Not Configured'}</span>
              </div>
               {Boolean(armoriq.status) && (
                <div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Connection: </span>
                  <StatusBadge status={String(armoriq.status as string)} />
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="grid-2" style={{ marginBottom: '1.5rem' }}>
        <div className="card">
          <div className="card-header">Agents</div>
          {agentsReq.loading ? (
            <LoadingState />
          ) : agentsReq.error ? (
            <ErrorState message={agentsReq.error} onRetry={agentsReq.refresh} />
          ) : !agentsReq.data ? (
            <div className="empty-state">No agent data</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {Object.entries(agentsReq.data).map(([name, info]) => (
                <div key={name} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '0.85rem' }}>{name.replace(/_/g, ' ')}</span>
                  <StatusBadge status={(info as { status: string }).status} />
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card">
          <div className="card-header">MCP Servers</div>
          {mcpsReq.loading ? (
            <LoadingState />
          ) : mcpsReq.error ? (
            <ErrorState message={mcpsReq.error} onRetry={mcpsReq.refresh} />
          ) : !mcpsReq.data ? (
            <div className="empty-state">No MCP data</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {Object.entries(mcpsReq.data).map(([name, info]) => (
                <div key={name} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '0.85rem' }}>{name.replace(/_/g, ' ')}</span>
                  <StatusBadge status={(info as { status: string }).status} />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="card-header">Authentication</div>
          {configReq.loading ? (
            <LoadingState />
          ) : configReq.error ? (
            <ErrorState message={configReq.error} onRetry={configReq.refresh} />
          ) : !auth ? (
            <div className="empty-state">No auth config</div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <StatusBadge status={auth.enabled ? 'healthy' : 'not_configured'} />
              <span style={{ fontSize: '0.85rem' }}>{auth.enabled ? 'Enabled' : 'Disabled'}</span>
            </div>
          )}
        </div>

        <div className="card">
          <div className="card-header">CORS Origins</div>
          {configReq.loading ? (
            <LoadingState />
          ) : configReq.error ? (
            <ErrorState message={configReq.error} onRetry={configReq.refresh} />
          ) : !cors || cors.length === 0 ? (
            <div className="empty-state">No origins configured</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
              {cors.map((origin, i) => (
                <div
                  key={i}
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.8rem',
                    color: 'var(--text-secondary)',
                    padding: '0.2rem 0',
                  }}
                >
                  {origin}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}