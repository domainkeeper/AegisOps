import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useMemo } from 'react';
import { useApi } from '../hooks/useApi';
import { useSSE } from '../hooks/useSSE';
import { api } from '../services/api';
import { StatusBadge } from '../components/StatusBadge';
import { LoadingState } from '../components/LoadingState';
import { ErrorState } from '../components/ErrorState';
export function Dashboard() {
    const statusReq = useApi(() => api.systemStatus(), []);
    const incidentsReq = useApi(() => api.listIncidents({ limit: 10 }), []);
    const auditReq = useApi(() => api.listAudit({ limit: 500 }), []);
    const { events: sseEvents, connected } = useSSE();
    const securitySummary = useMemo(() => {
        if (!auditReq.data?.events)
            return { authorized: 0, blocked: 0, failed: 0 };
        const events = auditReq.data.events;
        return {
            authorized: events.filter(e => e.status === 'allowed' || e.status === 'authorized' || e.status === 'success').length,
            blocked: events.filter(e => e.status === 'blocked').length,
            failed: events.filter(e => e.status === 'error' || e.status === 'failed').length,
        };
    }, [auditReq.data]);
    const activeIncidents = (incidentsReq.data?.incidents ?? []).filter(inc => inc.status !== 'resolved' && inc.status !== 'closed');
    if (statusReq.loading && incidentsReq.loading && auditReq.loading) {
        return _jsx(LoadingState, {});
    }
    return (_jsxs("div", { children: [_jsx("div", { className: "page-header", children: _jsxs("div", { children: [_jsx("div", { className: "page-title", children: "Dashboard" }), _jsx("div", { className: "page-subtitle", children: "System overview and active incidents" })] }) }), _jsxs("div", { className: "card", style: { marginBottom: '1.5rem' }, children: [_jsx("div", { className: "card-header", children: "System Status" }), statusReq.loading ? (_jsx(LoadingState, {})) : statusReq.error ? (_jsx(ErrorState, { message: statusReq.error, onRetry: statusReq.refresh })) : !statusReq.data?.components.length ? (_jsx("div", { className: "empty-state", children: "No components reported" })) : (_jsx("div", { className: "grid-4", children: statusReq.data.components.map(c => (_jsxs("div", { className: "card", style: { padding: '0.75rem 1rem' }, children: [_jsx("div", { style: { fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.25rem' }, children: c.name }), _jsx(StatusBadge, { status: c.status }), _jsx("div", { style: { fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }, children: c.detail })] }, c.name))) }))] }), _jsxs("div", { className: "grid-2", style: { marginBottom: '1.5rem' }, children: [_jsxs("div", { className: "card", children: [_jsx("div", { className: "card-header", children: "Security Summary" }), auditReq.loading ? (_jsx(LoadingState, {})) : auditReq.error ? (_jsx(ErrorState, { message: auditReq.error, onRetry: auditReq.refresh })) : (_jsxs("div", { className: "grid-3", children: [_jsxs("div", { className: "metric-card", children: [_jsx("div", { className: "metric-value", style: { color: 'var(--green)' }, children: securitySummary.authorized }), _jsx("div", { className: "metric-label", children: "Authorized" })] }), _jsxs("div", { className: "metric-card", children: [_jsx("div", { className: "metric-value", style: { color: 'var(--red)' }, children: securitySummary.blocked }), _jsx("div", { className: "metric-label", children: "Blocked" })] }), _jsxs("div", { className: "metric-card", children: [_jsx("div", { className: "metric-value", style: { color: 'var(--orange)' }, children: securitySummary.failed }), _jsx("div", { className: "metric-label", children: "Failed" })] })] }))] }), _jsxs("div", { className: "card", children: [_jsxs("div", { className: "card-header", children: ["Active Incidents (", activeIncidents.length, ")"] }), incidentsReq.loading ? (_jsx(LoadingState, {})) : incidentsReq.error ? (_jsx(ErrorState, { message: incidentsReq.error, onRetry: incidentsReq.refresh })) : activeIncidents.length === 0 ? (_jsx("div", { className: "empty-state", children: "No active incidents" })) : (_jsxs("table", { className: "data-table", children: [_jsx("thead", { children: _jsxs("tr", { children: [_jsx("th", { children: "ID" }), _jsx("th", { children: "Service" }), _jsx("th", { children: "Severity" }), _jsx("th", { children: "Status" }), _jsx("th", { children: "Created" })] }) }), _jsx("tbody", { children: activeIncidents.map(inc => (_jsxs("tr", { onClick: () => {
                                                window.history.pushState({}, '', `/incidents/${inc.id}`);
                                                window.dispatchEvent(new PopStateEvent('popstate'));
                                            }, style: { cursor: 'pointer' }, children: [_jsx("td", { style: { fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }, children: inc.id }), _jsx("td", { children: inc.service }), _jsx("td", { children: _jsx(StatusBadge, { status: inc.severity }) }), _jsx("td", { children: _jsx(StatusBadge, { status: inc.status }) }), _jsx("td", { style: { fontSize: '0.75rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }, children: new Date(inc.created_at).toLocaleString() })] }, inc.id))) })] }))] })] }), _jsxs("div", { className: "card", children: [_jsxs("div", { className: "card-header", style: { display: 'flex', alignItems: 'center', gap: '0.5rem' }, children: ["Recent Activity", _jsx("span", { style: {
                                    fontSize: '0.7rem',
                                    fontWeight: 400,
                                    color: connected ? 'var(--green)' : 'var(--text-muted)',
                                }, children: connected ? '● Live' : '○ Disconnected' })] }), sseEvents.length === 0 ? (_jsx("div", { className: "empty-state", children: "Waiting for events..." })) : (_jsx("div", { style: { maxHeight: '300px', overflowY: 'auto' }, children: sseEvents.slice(-20).reverse().map(e => (_jsxs("div", { style: {
                                display: 'flex',
                                gap: '0.75rem',
                                padding: '0.4rem 0',
                                borderBottom: '1px solid var(--border)',
                                fontSize: '0.8rem',
                                alignItems: 'center',
                            }, children: [_jsx("span", { style: {
                                        color: 'var(--text-muted)',
                                        fontFamily: 'var(--font-mono)',
                                        fontSize: '0.7rem',
                                        minWidth: '14ch',
                                    }, children: new Date(e.created_at).toLocaleTimeString() }), _jsx(StatusBadge, { status: e.status }), _jsx("span", { style: { color: 'var(--text-secondary)' }, children: e.agent }), _jsx("span", { style: { color: 'var(--text-muted)' }, children: e.action }), _jsx("span", { style: {
                                        fontFamily: 'var(--font-mono)',
                                        fontSize: '0.75rem',
                                        color: 'var(--text-muted)',
                                        marginLeft: 'auto',
                                    }, children: e.incident_id })] }, e.id))) }))] })] }));
}
