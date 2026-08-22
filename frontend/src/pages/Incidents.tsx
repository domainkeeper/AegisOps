import { useState, useCallback } from 'react';
import { useApi } from '../hooks/useApi';
import { api } from '../services/api';
import { StatusBadge } from '../components/StatusBadge';
import { LoadingState } from '../components/LoadingState';
import { ErrorState } from '../components/ErrorState';

export function Incidents() {
  const [page, setPage] = useState(0);
  const [statusFilter, setStatusFilter] = useState('');
  const [serviceFilter, setServiceFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const limit = 25;

  const fetcher = useCallback(
    () => api.listIncidents({ limit, offset: page * limit, status: statusFilter || undefined }),
    [page, statusFilter]
  );
  const { data, loading, error, refresh } = useApi(fetcher, [page, statusFilter]);

  const incidents = data?.items ?? [];
  const total = data?.total ?? 0;

  // Filter by service or search query client-side if needed or use API data
  const filtered = incidents.filter(inc => {
    if (serviceFilter && inc.service !== serviceFilter) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return inc.id.toLowerCase().includes(q) || (inc.description && inc.description.toLowerCase().includes(q));
    }
    return true;
  });

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Incidents</div>
          <div className="page-subtitle">Autonomous incident response records and status</div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: '1.5rem', display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ flex: 1, minWidth: '200px' }}>
          <label htmlFor="search">Search</label>
          <input
            id="search"
            placeholder="Search by ID or description..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
          />
        </div>
        <div style={{ width: '160px' }}>
          <label htmlFor="status-filter">Status</label>
          <select
            id="status-filter"
            value={statusFilter}
            onChange={e => { setStatusFilter(e.target.value); setPage(0); }}
          >
            <option value="">All Statuses</option>
            <option value="RECEIVED">Received</option>
            <option value="INVESTIGATING">Investigating</option>
            <option value="DIAGNOSING">Diagnosing</option>
            <option value="REMEDIATING">Remediating</option>
            <option value="VERIFYING">Verifying</option>
            <option value="RESOLVED">Resolved</option>
            <option value="FAILED">Failed</option>
          </select>
        </div>
        <div style={{ width: '160px' }}>
          <label htmlFor="service-filter">Service</label>
          <select
            id="service-filter"
            value={serviceFilter}
            onChange={e => setServiceFilter(e.target.value)}
          >
            <option value="">All Services</option>
            <option value="auth-api">auth-api</option>
          </select>
        </div>
      </div>

      <div className="card">
        {loading ? (
          <LoadingState />
        ) : error ? (
          <ErrorState message={error} onRetry={refresh} />
        ) : filtered.length === 0 ? (
          <div className="empty-state">No incidents found</div>
        ) : (
          <div>
            <table className="data-table" style={{ marginBottom: '1rem' }}>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Service</th>
                  <th>Severity</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(inc => (
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
                    <td style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {inc.created_at ? new Date(inc.created_at).toLocaleString() : '-'}
                    </td>
                    <td style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {inc.updated_at ? new Date(inc.updated_at).toLocaleString() : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              <div>Showing {filtered.length} of {total} incidents</div>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button
                  className="btn"
                  disabled={page === 0}
                  onClick={() => setPage(p => Math.max(0, p - 1))}
                >
                  Previous
                </button>
                <button
                  className="btn"
                  disabled={(page + 1) * limit >= total}
                  onClick={() => setPage(p => p + 1)}
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}