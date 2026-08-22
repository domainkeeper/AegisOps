import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { useApi } from '../hooks/useApi';
import { api } from '../services/api';
import { StatusBadge } from '../components/StatusBadge';
import { Timeline } from '../components/Timeline';
import { LoadingState } from '../components/LoadingState';
import { ErrorState } from '../components/ErrorState';
const TABS = ['Timeline', 'Diagnosis', 'Authorization', 'Service', 'Audit'];
export function IncidentDetail({ incidentId }) {
    const { data, loading, error, refresh } = useApi(() => api.getIncident(incidentId), [incidentId]);
    const [activeTab, setActiveTab] = useState('Authorization');
    if (loading)
        return _jsx(LoadingState, {});
    if (error)
        return _jsx(ErrorState, { message: error, onRetry: refresh });
    if (!data)
        return _jsx(ErrorState, { message: "Incident not found" });
    const inc = data;
    return (_jsxs("div", { children: [_jsxs("div", { className: "page-header", children: [_jsxs("div", { children: [_jsx("div", { className: "page-title", style: { fontFamily: 'var(--font-mono)', fontSize: '1.1rem' }, children: inc.id }), _jsxs("div", { className: "page-subtitle", children: [inc.service, " \u00B7 Created ", inc.created_at ? new Date(inc.created_at).toLocaleString() : '-', inc.resolved_at && _jsxs(_Fragment, { children: [" \u00B7 Resolved ", new Date(inc.resolved_at).toLocaleString()] })] })] }), _jsxs("div", { style: { display: 'flex', gap: '0.5rem', alignItems: 'center' }, children: [_jsx(StatusBadge, { status: inc.status }), _jsx(StatusBadge, { status: inc.severity }), inc.governed !== undefined && (_jsx(StatusBadge, { status: inc.governed ? 'governed' : 'ungoverned' }))] })] }), inc.error && (_jsx("div", { className: "error-state", style: { marginBottom: '1rem' }, children: inc.error })), _jsx("div", { className: "tabs", children: TABS.map(tab => (_jsx("div", { className: `tab ${activeTab === tab ? 'active' : ''}`, onClick: () => setActiveTab(tab), children: tab }, tab))) }), activeTab === 'Timeline' && (_jsx("div", { className: "card", children: inc.timeline && inc.timeline.length > 0 ? (_jsx(Timeline, { events: inc.timeline })) : (_jsx("div", { className: "empty-state", children: "No timeline events recorded" })) })), activeTab === 'Diagnosis' && (_jsx("div", { className: "card", children: inc.diagnosis ? (_jsxs("div", { style: { display: 'flex', flexDirection: 'column', gap: '1rem' }, children: [_jsxs("div", { children: [_jsx("div", { className: "card-header", children: "Diagnosis" }), _jsx("div", { style: { fontSize: '0.9rem', lineHeight: 1.6 }, children: inc.diagnosis })] }), inc.recommended_action && (_jsxs("div", { children: [_jsx("div", { className: "card-header", children: "Recommended Action" }), _jsx("div", { style: { fontSize: '0.9rem', color: 'var(--accent)' }, children: inc.recommended_action })] })), inc.resolution && (_jsxs("div", { children: [_jsx("div", { className: "card-header", children: "Resolution" }), _jsx("div", { style: { fontSize: '0.9rem', color: 'var(--text-secondary)' }, children: inc.resolution })] })), _jsxs("div", { className: "grid-3", children: [inc.intent_token_status && (_jsxs("div", { className: "metric-card", children: [_jsx("div", { className: "metric-value", children: inc.intent_token_status }), _jsx("div", { className: "metric-label", children: "Intent Token" })] })), inc.governed !== undefined && (_jsxs("div", { className: "metric-card", children: [_jsx("div", { className: "metric-value", children: inc.governed ? 'Yes' : 'No' }), _jsx("div", { className: "metric-label", children: "Governed" })] }))] })] })) : (_jsx("div", { className: "empty-state", children: "No diagnosis data available" })) })), activeTab === 'Authorization' && (_jsx(AuthorizationEvents, { incidentId: incidentId })), activeTab === 'Service' && (_jsxs("div", { className: "card", children: [_jsx("div", { className: "card-header", children: "Service Information" }), _jsxs("div", { style: { display: 'flex', flexDirection: 'column', gap: '0.75rem' }, children: [_jsxs("div", { children: [_jsx("div", { style: { fontSize: '0.75rem', color: 'var(--text-muted)' }, children: "Service" }), _jsx("div", { style: { fontSize: '0.95rem' }, children: inc.service || 'N/A' })] }), _jsxs("div", { children: [_jsx("div", { style: { fontSize: '0.75rem', color: 'var(--text-muted)' }, children: "Status" }), _jsx(StatusBadge, { status: inc.status })] }), _jsxs("div", { children: [_jsx("div", { style: { fontSize: '0.75rem', color: 'var(--text-muted)' }, children: "Severity" }), _jsx(StatusBadge, { status: inc.severity })] }), inc.description && (_jsxs("div", { children: [_jsx("div", { style: { fontSize: '0.75rem', color: 'var(--text-muted)' }, children: "Description" }), _jsx("div", { style: { fontSize: '0.9rem', color: 'var(--text-secondary)' }, children: inc.description })] })), inc.intent_token_status && (_jsxs("div", { children: [_jsx("div", { style: { fontSize: '0.75rem', color: 'var(--text-muted)' }, children: "Intent Token" }), _jsx(StatusBadge, { status: inc.intent_token_status })] })), inc.governed !== undefined && (_jsxs("div", { children: [_jsx("div", { style: { fontSize: '0.75rem', color: 'var(--text-muted)' }, children: "Governed" }), _jsx(StatusBadge, { status: inc.governed ? 'governed' : 'ungoverned' })] }))] })] })), activeTab === 'Audit' && (_jsx(IncidentAudit, { incidentId: incidentId }))] }));
}
function AuthorizationEvents({ incidentId }) {
    const { data, loading, error, refresh } = useApi(() => api.getIncidentAudit(incidentId), [incidentId]);
    if (loading)
        return _jsx(LoadingState, {});
    if (error)
        return _jsx(ErrorState, { message: error, onRetry: refresh });
    if (!data || !data.audit_events || data.audit_events.length === 0) {
        return _jsx("div", { className: "card", children: _jsx("div", { className: "empty-state", children: "No authorization events recorded for this incident" }) });
    }
    const events = data.audit_events;
    const blocked = events.filter(e => e.status === 'blocked');
    const allowed = events.filter(e => e.status === 'allowed' || e.status === 'success');
    const errors = events.filter(e => e.status === 'error' || e.status === 'failed');
    return (_jsxs("div", { children: [_jsxs("div", { className: "card", style: { marginBottom: '1rem' }, children: [_jsx("div", { className: "card-header", children: "Authorization Decision Summary" }), _jsx("p", { style: { fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem' }, children: "Each agent's requested action and the authority system's decision. This is the central security visualization showing what was blocked vs. allowed." })] }), _jsxs("div", { className: "grid-2", children: [blocked.map((ev, i) => (_jsx(AuditEventCard, { event: ev }, `blocked-${i}`))), allowed.map((ev, i) => (_jsx(AuditEventCard, { event: ev }, `allowed-${i}`))), errors.map((ev, i) => (_jsx(AuditEventCard, { event: ev }, `error-${i}`)))] })] }));
}
function AuditEventCard({ event }) {
    const borderColor = event.status === 'allowed' || event.status === 'success'
        ? 'rgba(62,207,142,0.3)'
        : event.status === 'blocked'
            ? 'rgba(231,76,60,0.3)'
            : 'rgba(230,126,34,0.3)';
    const bgColor = event.status === 'allowed' || event.status === 'success'
        ? 'rgba(62,207,142,0.05)'
        : event.status === 'blocked'
            ? 'rgba(231,76,60,0.05)'
            : 'rgba(230,126,34,0.05)';
    return (_jsxs("div", { className: "card", style: {
            borderColor,
            background: bgColor,
        }, children: [_jsxs("div", { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }, children: [_jsx("span", { style: { fontWeight: 600, fontSize: '0.9rem' }, children: event.agent }), _jsx(StatusBadge, { status: event.status })] }), _jsxs("div", { style: { marginBottom: '0.75rem' }, children: [_jsx("div", { style: { fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.15rem' }, children: "Requested Action" }), _jsx("span", { style: { fontFamily: 'var(--font-mono)', fontSize: '0.85rem', background: 'var(--bg-primary)', padding: '0.2rem 0.5rem', borderRadius: '4px' }, children: event.action })] }), _jsx("div", { style: { fontSize: '0.8rem', color: 'var(--text-secondary)', borderTop: '1px solid var(--border)', paddingTop: '0.5rem', marginTop: '0.25rem' }, children: event.detail || event.error_type || '-' })] }));
}
function IncidentAudit({ incidentId }) {
    const { data, loading, error, refresh } = useApi(() => api.getIncidentAudit(incidentId), [incidentId]);
    const [expanded, setExpanded] = useState(false);
    if (loading)
        return _jsx(LoadingState, {});
    if (error)
        return _jsx(ErrorState, { message: error, onRetry: refresh });
    if (!data || !data.audit_events || data.audit_events.length === 0)
        return _jsx("div", { className: "empty-state", children: "No audit events for this incident" });
    const events = data.audit_events;
    const displayed = expanded ? events : events.slice(0, 20);
    return (_jsxs("div", { className: "card", children: [_jsxs("div", { className: "card-header", style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' }, children: [_jsxs("span", { children: ["Audit Events (", events.length, ")"] }), events.length > 20 && (_jsx("button", { className: "btn", onClick: () => setExpanded(!expanded), style: { fontSize: '0.75rem', padding: '0.2rem 0.6rem' }, children: expanded ? 'Collapse' : 'Show All' }))] }), _jsxs("table", { className: "data-table", children: [_jsx("thead", { children: _jsxs("tr", { children: [_jsx("th", { children: "Time" }), _jsx("th", { children: "Agent" }), _jsx("th", { children: "Action" }), _jsx("th", { children: "Status" }), _jsx("th", { children: "Detail" })] }) }), _jsx("tbody", { children: displayed.map((ev, i) => (_jsxs("tr", { children: [_jsx("td", { style: { fontFamily: 'var(--font-mono)', fontSize: '0.75rem', whiteSpace: 'nowrap' }, children: ev.created_at ? new Date(ev.created_at).toLocaleString() : '-' }), _jsx("td", { children: ev.agent }), _jsx("td", { style: { fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }, children: ev.action }), _jsx("td", { children: _jsx(StatusBadge, { status: ev.status }) }), _jsx("td", { style: { fontSize: '0.8rem', color: 'var(--text-secondary)', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis' }, children: ev.detail || ev.error_type || '-' })] }, i))) })] }), events.length > 20 && (_jsx("div", { style: { marginTop: '0.5rem', textAlign: 'center' }, children: _jsx("button", { className: "btn", onClick: () => setExpanded(!expanded), style: { fontSize: '0.75rem', padding: '0.2rem 0.6rem' }, children: expanded ? 'Collapse' : 'Show All' }) }))] }));
}
