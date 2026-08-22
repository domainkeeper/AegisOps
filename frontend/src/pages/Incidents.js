import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
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
    const fetcher = useCallback(() => api.listIncidents({ limit, offset: page * limit, status: statusFilter || undefined }), [page, statusFilter]);
    const { data, loading, error, refresh } = useApi(fetcher, [page, statusFilter]);
    const incidents = data?.items ?? [];
    const total = data?.total ?? 0;
    // Filter by service or search query client-side if needed or use API data
    const filtered = incidents.filter(inc => {
        if (serviceFilter && inc.service !== serviceFilter)
            return false;
        if (searchQuery) {
            const q = searchQuery.toLowerCase();
            return inc.id.toLowerCase().includes(q) || (inc.description && inc.description.toLowerCase().includes(q));
        }
        return true;
    });
    return (_jsxs("div", { children: [_jsx("div", { className: "page-header", children: _jsxs("div", { children: [_jsx("div", { className: "page-title", children: "Incidents" }), _jsx("div", { className: "page-subtitle", children: "Autonomous incident response records and status" })] }) }), _jsxs("div", { className: "card", style: { marginBottom: '1.5rem', display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'center' }, children: [_jsxs("div", { style: { flex: 1, minWidth: '200px' }, children: [_jsx("label", { htmlFor: "search", children: "Search" }), _jsx("input", { id: "search", placeholder: "Search by ID or description...", value: searchQuery, onChange: e => setSearchQuery(e.target.value) })] }), _jsxs("div", { style: { width: '160px' }, children: [_jsx("label", { htmlFor: "status-filter", children: "Status" }), _jsxs("select", { id: "status-filter", value: statusFilter, onChange: e => { setStatusFilter(e.target.value); setPage(0); }, children: [_jsx("option", { value: "", children: "All Statuses" }), _jsx("option", { value: "RECEIVED", children: "Received" }), _jsx("option", { value: "INVESTIGATING", children: "Investigating" }), _jsx("option", { value: "DIAGNOSING", children: "Diagnosing" }), _jsx("option", { value: "REMEDIATING", children: "Remediating" }), _jsx("option", { value: "VERIFYING", children: "Verifying" }), _jsx("option", { value: "RESOLVED", children: "Resolved" }), _jsx("option", { value: "FAILED", children: "Failed" })] })] }), _jsxs("div", { style: { width: '160px' }, children: [_jsx("label", { htmlFor: "service-filter", children: "Service" }), _jsxs("select", { id: "service-filter", value: serviceFilter, onChange: e => setServiceFilter(e.target.value), children: [_jsx("option", { value: "", children: "All Services" }), _jsx("option", { value: "auth-api", children: "auth-api" })] })] })] }), _jsx("div", { className: "card", children: loading ? (_jsx(LoadingState, {})) : error ? (_jsx(ErrorState, { message: error, onRetry: refresh })) : filtered.length === 0 ? (_jsx("div", { className: "empty-state", children: "No incidents found" })) : (_jsxs("div", { children: [_jsxs("table", { className: "data-table", style: { marginBottom: '1rem' }, children: [_jsx("thead", { children: _jsxs("tr", { children: [_jsx("th", { children: "ID" }), _jsx("th", { children: "Service" }), _jsx("th", { children: "Severity" }), _jsx("th", { children: "Status" }), _jsx("th", { children: "Created" }), _jsx("th", { children: "Updated" })] }) }), _jsx("tbody", { children: filtered.map(inc => (_jsxs("tr", { onClick: () => {
                                            window.history.pushState({}, '', `/incidents/${inc.id}`);
                                            window.dispatchEvent(new PopStateEvent('popstate'));
                                        }, style: { cursor: 'pointer' }, children: [_jsx("td", { style: { fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }, children: inc.id }), _jsx("td", { children: inc.service }), _jsx("td", { children: _jsx(StatusBadge, { status: inc.severity }) }), _jsx("td", { children: _jsx(StatusBadge, { status: inc.status }) }), _jsx("td", { style: { fontSize: '0.75rem', color: 'var(--text-muted)' }, children: inc.created_at ? new Date(inc.created_at).toLocaleString() : '-' }), _jsx("td", { style: { fontSize: '0.75rem', color: 'var(--text-muted)' }, children: inc.updated_at ? new Date(inc.updated_at).toLocaleString() : '-' })] }, inc.id))) })] }), _jsxs("div", { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.85rem', color: 'var(--text-secondary)' }, children: [_jsxs("div", { children: ["Showing ", filtered.length, " of ", total, " incidents"] }), _jsxs("div", { style: { display: 'flex', gap: '0.5rem' }, children: [_jsx("button", { className: "btn", disabled: page === 0, onClick: () => setPage(p => Math.max(0, p - 1)), children: "Previous" }), _jsx("button", { className: "btn", disabled: (page + 1) * limit >= total, onClick: () => setPage(p => p + 1), children: "Next" })] })] })] })) })] }));
}
