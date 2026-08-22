import { useState, useCallback } from 'react';
import { useApi } from '../hooks/useApi';
import { api } from '../services/api';
import { StatusBadge } from '../components/StatusBadge';
import { LoadingState } from '../components/LoadingState';
import { ErrorState } from '../components/ErrorState';

export function Audit() {
  const [page, setPage] = useState(0);
  const [filterStatus, setFilterStatus] = useState('');
  const [filterIncident, setFilterIncident] = useState('');
  const limit = 50;

  const fetcher = useCallback(
    () =>
      api.listAudit({
        limit,
        offset: page * limit,
        status: filterStatus || undefined,
        incident_id: filterIncident || undefined,
      }),
    [page, filterStatus, filterIncident],
  );

  const { data, loading, error, refresh } = useApi(fetcher, [page, filterStatus, filterIncident]);

  const totalPages = data ? Math.ceil(data.total / limit) : 0;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Audit Log</div>
          <div className="page-subtitle">
            {data ? `${data.total} total events` : 'Searchable event history'}
          </div>
        </div>
      </div>

      <div
        className="card"
        style={{
          marginBottom: '1rem',
          display: 'flex',
          gap: '1rem',
          alignItems: 'end',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ minWidth: '180px', flex: 1 }}>
          <label htmlFor="filter-status">Status</label>
          <select
            id="filter-status"
            value={filterStatus}
            onChange={e => {
              setFilterStatus(e.target.value);
              setPage(0);
            }}
          >
            <option value="">All Statuses</option>
            <option value="allowed">Allowed</option>
            <option value="blocked">Blocked</option>
            <option value="error">Error</option>
            <option value="success">Success</option>
            <option value="failed">Failed</option>
            <option value="running">Running</option>
          </select>
        </div>
        <div style={{ minWidth: '200px', flex: 1 }}>
          <label htmlFor="filter-incident">Incident ID</label>
          <input
            id="filter-incident"
            placeholder="e.g. inc_abc123"
            value={filterIncident}
            onChange={e => {
              setFilterIncident(e.target.value);
              setPage(0);
            }}
          />
        </div>
        <button className="btn" onClick={refresh} style={{ marginBottom: '0.15rem' }}>
          Refresh
        </button>
      </div>

      {loading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error} onRetry={refresh} />
      ) : !data || !data.items || data.items.length === 0 ? (
        <div className="card">
          <div className="empty-state">No audit events match your filters</div>
        </div>
      ) : (
        <>
          <div className="card" style={{ padding: 0, overflow: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Incident</th>
                  <th>Agent</th>
                  <th>Action</th>
                  <th>Status</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((ev, i) => (
                  <tr
                    key={i}
                    onClick={() => {
                      window.history.pushState({}, '', `/incidents/${ev.incident_id}`);
                      window.dispatchEvent(new PopStateEvent('popstate'));
                    }}
                    style={{ cursor: 'pointer' }}
                  >
                    <td
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.75rem',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {ev.created_at ? new Date(ev.created_at).toLocaleString() : '-'}
                    </td>
                    <td
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.8rem',
                        color: 'var(--accent)',
                      }}
                    >
                      {ev.incident_id}
                    </td>
                    <td>{ev.agent}</td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
                      {ev.action}
                    </td>
                    <td>
                      <StatusBadge status={ev.status} />
                    </td>
                    <td
                      style={{
                        fontSize: '0.8rem',
                        color: 'var(--text-secondary)',
                        maxWidth: '250px',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {ev.detail || ev.error_type || '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginTop: '1rem',
            }}
          >
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Page {page + 1} of {totalPages || 1} &middot; {limit} per page
            </span>
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
                disabled={page >= totalPages - 1}
                onClick={() => setPage(p => p + 1)}
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}