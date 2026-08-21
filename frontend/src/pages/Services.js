import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useApi } from '../hooks/useApi';
import { api } from '../services/api';
import { StatusBadge } from '../components/StatusBadge';
import { LoadingState } from '../components/LoadingState';
import { ErrorState } from '../components/ErrorState';
export function Services() {
    const { data, loading, error, refresh } = useApi(() => api.services(), []);
    if (loading)
        return _jsx(LoadingState, {});
    if (error)
        return _jsx(ErrorState, { message: error, onRetry: refresh });
    if (!data || data.length === 0)
        return _jsx("div", { className: "empty-state", children: "No services reported" });
    return (_jsxs("div", { children: [_jsx("div", { className: "page-header", children: _jsxs("div", { children: [_jsx("div", { className: "page-title", children: "Services" }), _jsx("div", { className: "page-subtitle", children: "Service health and container status" })] }) }), _jsx("div", { className: "grid-4", children: data.map(svc => (_jsxs("div", { className: "card", children: [_jsxs("div", { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }, children: [_jsx("span", { style: { fontWeight: 600, fontSize: '0.9rem' }, children: svc.name }), _jsx(StatusBadge, { status: svc.health })] }), _jsxs("div", { style: { display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.8rem' }, children: [svc.image && (_jsxs("div", { children: [_jsx("span", { style: { color: 'var(--text-muted)' }, children: "Image: " }), _jsx("span", { style: { fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-secondary)' }, children: svc.image })] })), svc.container && (_jsxs("div", { children: [_jsx("span", { style: { color: 'var(--text-muted)' }, children: "Container: " }), _jsx("span", { style: { fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-secondary)' }, children: svc.container })] })), svc.started_at && (_jsxs("div", { children: [_jsx("span", { style: { color: 'var(--text-muted)' }, children: "Started: " }), _jsx("span", { style: { color: 'var(--text-secondary)' }, children: new Date(svc.started_at).toLocaleString() })] })), svc.restart_count !== null && svc.restart_count !== undefined && (_jsxs("div", { children: [_jsx("span", { style: { color: 'var(--text-muted)' }, children: "Restarts: " }), _jsx("span", { style: { color: 'var(--text-secondary)' }, children: svc.restart_count })] })), svc.last_incident && (_jsxs("div", { children: [_jsx("span", { style: { color: 'var(--text-muted)' }, children: "Last Incident: " }), _jsx("a", { href: `/incidents/${svc.last_incident}`, onClick: e => {
                                                e.preventDefault();
                                                window.history.pushState({}, '', `/incidents/${svc.last_incident}`);
                                                window.dispatchEvent(new PopStateEvent('popstate'));
                                            }, style: { fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }, children: svc.last_incident })] }))] })] }, svc.name))) })] }));
}
