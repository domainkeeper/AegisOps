import { useApi } from '../hooks/useApi';
import { api } from '../services/api';
import { LoadingState } from '../components/LoadingState';
import { ErrorState } from '../components/ErrorState';
import type { AuthorityEntry } from '../types/api';

export function Security() {
  const { data, loading, error, refresh } = useApi(() => api.authority(), []);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={refresh} />;
  if (!data) return <ErrorState message="Failed to load authority data" />;

  // The backend returns `authority_model` but the type is `AuthorityResponse`
  // Cast to access the actual response structure
  const raw = data as unknown as Record<string, unknown>;
  const authority = (raw.authority_model as AuthorityEntry[] | undefined) ?? [];
  const planActions = (raw.plan_actions as string[] | undefined) ?? [];
  const note = (raw.note as string | undefined) ?? '';

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Security Authority Model</div>
          <div className="page-subtitle">Observational view of the authorization hierarchy</div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header">Plan Actions</div>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
          Top-level actions defined in the root plan that agents may be delegated to execute.
        </p>
        {planActions.length === 0 ? (
          <div className="empty-state">No plan actions defined</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            {planActions.map((action, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '0.5rem 0.75rem',
                  background: 'var(--bg-primary)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius)',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.85rem',
                }}
              >
                <span style={{ color: 'var(--accent)', fontWeight: 600 }}>{i + 1}.</span>
                {action}
              </div>
            ))}
          </div>
        )}
      </div>

      {authority.length === 0 ? (
        <div className="card">
          <div className="empty-state">No delegation entries configured</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {authority.map((entry: AuthorityEntry, i: number) => (
            <div
              key={i}
              className="card"
              style={{
                borderLeft: `3px solid ${i === 0 ? 'var(--accent)' : i === 1 ? 'var(--green)' : 'var(--purple)'}`,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
                <span
                  style={{
                    width: '24px',
                    height: '24px',
                    borderRadius: '50%',
                    background: 'var(--bg-primary)',
                    border: '1px solid var(--border)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    color: 'var(--text-muted)',
                  }}
                >
                  {i + 1}
                </span>
                <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>{entry.agent}</span>
              </div>

              {entry.steps && entry.steps.length > 0 && (
                <div style={{ marginBottom: '0.75rem' }}>
                  <div
                    style={{
                      fontSize: '0.7rem',
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em',
                      color: 'var(--text-muted)',
                      marginBottom: '0.3rem',
                    }}
                  >
                    Steps
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }}>
                    {entry.steps.map((step: string, si: number) => (
                      <span
                        key={si}
                        style={{
                          fontFamily: 'var(--font-mono)',
                          fontSize: '0.8rem',
                          background: 'var(--bg-primary)',
                          border: '1px solid var(--border)',
                          borderRadius: '3px',
                          padding: '0.2rem 0.5rem',
                        }}
                      >
                        {step}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div>
                <div
                  style={{
                    fontSize: '0.7rem',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    color: 'var(--text-muted)',
                    marginBottom: '0.3rem',
                  }}
                >
                  Allowed Actions
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }}>
                  {(entry.allowed_actions ?? []).map((action: string, ai: number) => (
                    <span
                      key={ai}
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.8rem',
                        background: 'rgba(62,207,142,0.08)',
                        border: '1px solid rgba(62,207,142,0.2)',
                        borderRadius: '3px',
                        padding: '0.2rem 0.5rem',
                        color: 'var(--green)',
                      }}
                    >
                      {action}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {note && (
        <div
          className="card"
          style={{
            marginTop: '1.5rem',
            borderColor: 'rgba(245,166,35,0.3)',
            background: 'rgba(245,166,35,0.03)',
          }}
        >
          <div className="card-header" style={{ color: 'var(--yellow)' }}>Note</div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{note}</p>
        </div>
      )}
    </div>
  );
}