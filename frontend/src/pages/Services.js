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
    if (!data)
        return _jsx("div", { className: "empty-state", children: "No services reported" });
    const services = data.services ?? [];
    return (_jsxs("div", { children: [_jsx("div", { className: "page-header", children: _jsxs("div", { children: [_jsx("div", { className: "page-title", children: "Services" }), _jsx("div", { className: "page-subtitle", children: "Service health and container status" })] }) }), services.length === 0 ? (_jsx("div", { className: "empty-state", children: "No services reported" })) : (_jsx("div", { className: "grid-4", children: services.map(svc => {
                    const healthStatus = typeof svc.health === 'string' ? svc.health : svc.health?.status || 'unknown';
                    const dockerInfo = svc.docker;
                    return (_jsxs("div", { className: "card", children: [_jsxs("div", { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }, children: [_jsx("span", { style: { fontWeight: 600, fontSize: '0.9rem' }, children: svc.name }), _jsx(StatusBadge, { status: healthStatus })] }), _jsxs("div", { style: { display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.8rem' }, children: [dockerInfo?.image && (_jsxs("div", { children: [_jsx("span", { style: { color: 'var(--text-muted)' }, children: "Image: " }), _jsx("span", { style: { fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-secondary)' }, children: dockerInfo.image })] })), dockerInfo?.name && (_jsxs("div", { children: [_jsx("span", { style: { color: 'var(--text-muted)' }, children: "Container: " }), _jsx("span", { style: { fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-secondary)' }, children: dockerInfo.name })] })), dockerInfo?.state && (_jsxs("div", { children: [_jsx("span", { style: { color: 'var(--text-muted)' }, children: "State: " }), _jsx("span", { style: { color: 'var(--text-secondary)' }, children: dockerInfo.state })] }))] })] }, svc.name));
                }) }))] }));
}
