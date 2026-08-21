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
    return (_jsxs("div", { children: [_jsxs("div", { className: "page-header", children: [_jsxs("div", { children: [_jsx("div", { className: "page-title", style: { fontFamily: 'var(--font-mono)', fontSize: '1.1rem' }, children: inc.id }), _jsxs("div", { className: "page-subtitle", children: [inc.service, " \u00B7 Created ", new Date(inc.created_at).toLocaleString(), inc.resolved_at && _jsxs(_Fragment, { children: [" \u00B7 Resolved ", new Date(inc.resolved_at).toLocaleString()] })] })] }), _jsxs("div", { style: { display: 'flex', gap: '0.5rem', alignItems: 'center' }, children: [_jsx(StatusBadge, { status: inc.status }), _jsx(StatusBadge, { status: inc.severity }), inc.governed !== undefined && (_jsx(StatusBadge, { status: inc.governed ? 'governed' : 'ungoverned' }))] })] }), inc.error && (_jsx("div", { className: "error-state", style: { marginBottom: '1rem' }, children: inc.error })), _jsx("div", { className: "tabs", children: TABS.map(tab => (_jsx("div", { className: `tab ${activeTab === tab ? 'active' : ''}`, onClick: () => setActiveTab(tab), children: tab }, tab))) }), activeTab === 'Timeline' && (_jsx("div", { className: "card", children: inc.timeline && inc.timeline.length > 0 ? (_jsx(Timeline, { events: inc.timeline })) : (_jsx("div", { className: "empty-state", children: "No timeline events recorded" })) })), activeTab === 'Diagnosis' && (_jsx("div", { className: "card", children: inc.diagnosis ? (_jsxs("div", { style: { display: 'flex', flexDirection: 'column', gap: '1rem' }, children: [inc.diagnosis.diagnosis && (_jsxs("div", { children: [_jsx("div", { className: "card-header", children: "Diagnosis" }), _jsx("div", { style: { fontSize: '0.9rem', lineHeight: 1.6 }, children: inc.diagnosis.diagnosis })] })), inc.diagnosis.root_cause && (_jsxs("div", { children: [_jsx("div", { className: "card-header", children: "Root Cause" }), _jsx("div", { style: { fontSize: '0.9rem', color: 'var(--text-secondary)' }, children: inc.diagnosis.root_cause })] })), inc.diagnosis.recommended_action && (_jsxs("div", { children: [_jsx("div", { className: "card-header", children: "Recommended Action" }), _jsx("div", { style: { fontSize: '0.9rem', color: 'var(--accent)' }, children: inc.diagnosis.recommended_action })] })), _jsxs("div", { className: "grid-3", children: [inc.diagnosis.confidence !== undefined && (_jsxs("div", { className: "metric-card", children: [_jsxs("div", { className: "metric-value", children: [Math.round(inc.diagnosis.confidence * 100), "%"] }), _jsx("div", { className: "metric-label", children: "Confidence" })] })), inc.diagnosis.llm_source && (_jsxs("div", { className: "metric-card", children: [_jsx("div", { className: "metric-value", style: { fontSize: '1rem' }, children: inc.diagnosis.llm_source }), _jsx("div", { className: "metric-label", children: "LLM Source" })] })), inc.diagnosis.requires_remediation !== undefined && (_jsxs("div", { className: "metric-card", children: [_jsx("div", { className: "metric-value", children: inc.diagnosis.requires_remediation ? 'Yes' : 'No' }), _jsx("div", { className: "metric-label", children: "Remediation Required" })] }))] }), inc.diagnosis.governed_restart_attempted && (_jsxs("div", { style: { marginTop: '0.5rem' }, children: [_jsx("div", { className: "card-header", children: "Governed Restart" }), _jsxs("div", { style: { display: 'flex', gap: '0.5rem', alignItems: 'center' }, children: [_jsx(StatusBadge, { status: inc.diagnosis.governed_restart_blocked ? 'blocked' : 'allowed' }), _jsx("span", { style: { fontSize: '0.85rem', color: 'var(--text-secondary)' }, children: inc.diagnosis.governed_restart_blocked
                                                ? 'Restart was blocked by security policy'
                                                : 'Restart was authorized' })] }), inc.diagnosis.governed_restart_error && (_jsx("div", { style: { fontSize: '0.8rem', color: 'var(--red)', marginTop: '0.25rem' }, children: inc.diagnosis.governed_restart_error }))] }))] })) : (_jsx("div", { className: "empty-state", children: "No diagnosis data available" })) })), activeTab === 'Authorization' && (_jsx("div", { children: inc.authorization_events && inc.authorization_events.length > 0 ? (_jsxs("div", { children: [_jsxs("div", { className: "card", style: { marginBottom: '1rem' }, children: [_jsx("div", { className: "card-header", children: "Authorization Decision Summary" }), _jsx("p", { style: { fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem' }, children: "Each agent's requested action and the authority system's decision. This is the central security visualization showing what was blocked vs. allowed." })] }), _jsxs("div", { className: "grid-2", children: [inc.authorization_events
                                    .filter(e => e.result === 'blocked')
                                    .map((ev, i) => (_jsx(AuthorizationCard, { event: ev }, `blocked-${i}`))), inc.authorization_events
                                    .filter(e => e.result === 'allowed')
                                    .map((ev, i) => (_jsx(AuthorizationCard, { event: ev }, `allowed-${i}`))), inc.authorization_events
                                    .filter(e => e.result === 'error')
                                    .map((ev, i) => (_jsx(AuthorizationCard, { event: ev }, `error-${i}`)))] })] })) : (_jsx("div", { className: "card", children: _jsx("div", { className: "empty-state", children: "No authorization events recorded for this incident" }) })) })), activeTab === 'Service' && (_jsxs("div", { className: "card", children: [_jsx("div", { className: "card-header", children: "Service Information" }), _jsxs("div", { style: { display: 'flex', flexDirection: 'column', gap: '0.75rem' }, children: [_jsxs("div", { children: [_jsx("div", { style: { fontSize: '0.75rem', color: 'var(--text-muted)' }, children: "Service" }), _jsx("div", { style: { fontSize: '0.95rem' }, children: inc.service || 'N/A' })] }), _jsxs("div", { children: [_jsx("div", { style: { fontSize: '0.75rem', color: 'var(--text-muted)' }, children: "Status" }), _jsx(StatusBadge, { status: inc.status })] }), _jsxs("div", { children: [_jsx("div", { style: { fontSize: '0.75rem', color: 'var(--text-muted)' }, children: "Severity" }), _jsx(StatusBadge, { status: inc.severity })] }), inc.description && (_jsxs("div", { children: [_jsx("div", { style: { fontSize: '0.75rem', color: 'var(--text-muted)' }, children: "Description" }), _jsx("div", { style: { fontSize: '0.9rem', color: 'var(--text-secondary)' }, children: inc.description })] })), inc.intent_token_status && (_jsxs("div", { children: [_jsx("div", { style: { fontSize: '0.75rem', color: 'var(--text-muted)' }, children: "Intent Token" }), _jsx(StatusBadge, { status: inc.intent_token_status })] }))] })] })), activeTab === 'Audit' && (_jsx(IncidentAudit, { incidentId: incidentId }))] }));
}
function AuthorizationCard({ event }) {
    const borderColor = event.result === 'allowed'
        ? 'rgba(62,207,142,0.3)'
        : event.result === 'blocked'
            ? 'rgba(231,76,60,0.3)'
            : 'rgba(230,126,34,0.3)';
    const bgColor = event.result === 'allowed'
        ? 'rgba(62,207,142,0.05)'
        : event.result === 'blocked'
            ? 'rgba(231,76,60,0.05)'
            : 'rgba(230,126,34,0.05)';
    return (_jsxs("div", { className: "card", style: {
            borderColor,
            background: bgColor,
        }, children: [_jsxs("div", { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }, children: [_jsx("span", { style: { fontWeight: 600, fontSize: '0.9rem' }, children: event.agent }), _jsx(StatusBadge, { status: event.result })] }), _jsxs("div", { style: { marginBottom: '0.75rem' }, children: [_jsx("div", { style: { fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.15rem' }, children: "Requested Action" }), _jsx("span", { style: { fontFamily: 'var(--font-mono)', fontSize: '0.85rem', background: 'var(--bg-primary)', padding: '0.2rem 0.5rem', borderRadius: '4px' }, children: event.requested_action })] }), event.authority_actions.length > 0 && (_jsxs("div", { style: { marginBottom: '0.5rem' }, children: [_jsx("div", { style: { fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }, children: "Authority Actions" }), _jsx("div", { style: { display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }, children: event.authority_actions.map((a, i) => (_jsx("span", { style: {
                                fontFamily: 'var(--font-mono)',
                                fontSize: '0.75rem',
                                background: 'var(--bg-primary)',
                                border: '1px solid var(--border)',
                                borderRadius: '3px',
                                padding: '0.15rem 0.4rem',
                            }, children: a }, i))) })] })), _jsx("div", { style: { fontSize: '0.8rem', color: 'var(--text-secondary)', borderTop: '1px solid var(--border)', paddingTop: '0.5rem', marginTop: '0.25rem' }, children: event.reason })] }));
}
function IncidentAudit({ incidentId }) {
    const { data, loading, error, refresh } = useApi(() => api.getIncidentAudit(incidentId), [incidentId]);
    const [expanded, setExpanded] = useState(false);
    if (loading)
        return _jsx(LoadingState, {});
    if (error)
        return _jsx(ErrorState, { message: error, onRetry: refresh });
    if (!data || data.length === 0)
        return _jsx("div", { className: "empty-state", children: "No audit events for this incident" });
    const displayed = expanded ? data : data.slice(0, 20);
    return (_jsxs("div", { className: "card", children: [_jsxs("div", { className: "card-header", style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' }, children: [_jsxs("span", { children: ["Audit Events (", data.length, ")"] }), data.length > 20 && (_jsx("button", { className: "btn", onClick: () => setExpanded(!expanded), style: { fontSize: '0.75rem', padding: '0.2rem 0.6rem' }, children: expanded ? 'Collapse' : 'Show All' }))] }), _jsxs("table", { className: "data-table", children: [_jsx("thead", { children: _jsxs("tr", { children: [_jsx("th", { children: "Time" }), _jsx("th", { children: "Agent" }), _jsx("th", { children: "Action" }), _jsx("th", { children: "Status" }), _jsx("th", { children: "Detail" })] }) }), _jsx("tbody", { children: displayed.map((ev, i) => (_jsxs("tr", { children: [_jsx("td", { style: { fontFamily: 'var(--font-mono)', fontSize: '0.75rem', whiteSpace: 'nowrap' }, children: new Date(ev.created_at).toLocaleString() }), _jsx("td", { children: ev.agent }), _jsx("td", { style: { fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }, children: ev.action }), _jsx("td", { children: _jsx(StatusBadge, { status: ev.status }) }), _jsx("td", { style: { fontSize: '0.8rem', color: 'var(--text-secondary)', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis' }, children: ev.detail || ev.error_type || '-' })] }, i))) })] })] }));
}
