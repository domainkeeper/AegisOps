import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
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
    const fetcher = useCallback(() => api.listAudit({
        limit,
        offset: page * limit,
        status: filterStatus || undefined,
        incident_id: filterIncident || undefined,
    }), [page, filterStatus, filterIncident]);
    const { data, loading, error, refresh } = useApi(fetcher, [page, filterStatus, filterIncident]);
    const totalPages = data ? Math.ceil(data.total / limit) : 0;
    return (_jsxs("div", { children: [_jsx("div", { className: "page-header", children: _jsxs("div", { children: [_jsx("div", { className: "page-title", children: "Audit Log" }), _jsx("div", { className: "page-subtitle", children: data ? `${data.total} total events` : 'Searchable event history' })] }) }), _jsxs("div", { className: "card", style: {
                    marginBottom: '1rem',
                    display: 'flex',
                    gap: '1rem',
                    alignItems: 'end',
                    flexWrap: 'wrap',
                }, children: [_jsxs("div", { style: { minWidth: '180px', flex: 1 }, children: [_jsx("label", { htmlFor: "filter-status", children: "Status" }), _jsxs("select", { id: "filter-status", value: filterStatus, onChange: e => {
                                    setFilterStatus(e.target.value);
                                    setPage(0);
                                }, children: [_jsx("option", { value: "", children: "All Statuses" }), _jsx("option", { value: "allowed", children: "Allowed" }), _jsx("option", { value: "blocked", children: "Blocked" }), _jsx("option", { value: "error", children: "Error" }), _jsx("option", { value: "success", children: "Success" }), _jsx("option", { value: "failed", children: "Failed" }), _jsx("option", { value: "running", children: "Running" })] })] }), _jsxs("div", { style: { minWidth: '200px', flex: 1 }, children: [_jsx("label", { htmlFor: "filter-incident", children: "Incident ID" }), _jsx("input", { id: "filter-incident", placeholder: "e.g. inc_abc123", value: filterIncident, onChange: e => {
                                    setFilterIncident(e.target.value);
                                    setPage(0);
                                } })] }), _jsx("button", { className: "btn", onClick: refresh, style: { marginBottom: '0.15rem' }, children: "Refresh" })] }), loading ? (_jsx(LoadingState, {})) : error ? (_jsx(ErrorState, { message: error, onRetry: refresh })) : !data || !data.items || data.items.length === 0 ? (_jsx("div", { className: "card", children: _jsx("div", { className: "empty-state", children: "No audit events match your filters" }) })) : (_jsxs(_Fragment, { children: [_jsx("div", { className: "card", style: { padding: 0, overflow: 'auto' }, children: _jsxs("table", { className: "data-table", children: [_jsx("thead", { children: _jsxs("tr", { children: [_jsx("th", { children: "Timestamp" }), _jsx("th", { children: "Incident" }), _jsx("th", { children: "Agent" }), _jsx("th", { children: "Action" }), _jsx("th", { children: "Status" }), _jsx("th", { children: "Detail" })] }) }), _jsx("tbody", { children: data.items.map((ev, i) => (_jsxs("tr", { onClick: () => {
                                            window.history.pushState({}, '', `/incidents/${ev.incident_id}`);
                                            window.dispatchEvent(new PopStateEvent('popstate'));
                                        }, style: { cursor: 'pointer' }, children: [_jsx("td", { style: {
                                                    fontFamily: 'var(--font-mono)',
                                                    fontSize: '0.75rem',
                                                    whiteSpace: 'nowrap',
                                                }, children: ev.created_at ? new Date(ev.created_at).toLocaleString() : '-' }), _jsx("td", { style: {
                                                    fontFamily: 'var(--font-mono)',
                                                    fontSize: '0.8rem',
                                                    color: 'var(--accent)',
                                                }, children: ev.incident_id }), _jsx("td", { children: ev.agent }), _jsx("td", { style: { fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }, children: ev.action }), _jsx("td", { children: _jsx(StatusBadge, { status: ev.status }) }), _jsx("td", { style: {
                                                    fontSize: '0.8rem',
                                                    color: 'var(--text-secondary)',
                                                    maxWidth: '250px',
                                                    overflow: 'hidden',
                                                    textOverflow: 'ellipsis',
                                                }, children: ev.detail || ev.error_type || '-' })] }, i))) })] }) }), _jsxs("div", { style: {
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            marginTop: '1rem',
                        }, children: [_jsxs("span", { style: { fontSize: '0.8rem', color: 'var(--text-muted)' }, children: ["Page ", page + 1, " of ", totalPages || 1, " \u00B7 ", limit, " per page"] }), _jsxs("div", { style: { display: 'flex', gap: '0.5rem' }, children: [_jsx("button", { className: "btn", disabled: page === 0, onClick: () => setPage(p => Math.max(0, p - 1)), children: "Previous" }), _jsx("button", { className: "btn", disabled: page >= totalPages - 1, onClick: () => setPage(p => p + 1), children: "Next" })] })] })] }))] }));
}
