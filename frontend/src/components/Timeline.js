import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { StatusBadge } from './StatusBadge';
function formatTs(ts) {
    const d = new Date(ts * 1000);
    return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}
export function Timeline({ events }) {
    if (!events || !events.length)
        return _jsxs("div", { className: "empty-state", children: [_jsx("div", { className: "empty-state-icon", children: "\u25FB" }), "No timeline events"] });
    return (_jsx("ul", { className: "timeline", children: events.map((e, i) => {
            const status = e.status || 'unknown';
            const stage = e.stage || 'unknown';
            const ts = e.ts || 0;
            return (_jsxs("li", { className: `timeline-item ${status.toLowerCase()}`, children: [_jsx("span", { className: "timeline-time", children: formatTs(ts) }), _jsxs("div", { className: "timeline-content", children: [_jsxs("div", { className: "timeline-stage", children: [stage.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()), _jsx(StatusBadge, { status: status, label: "" })] }), e.detail && _jsx("div", { className: "timeline-detail", children: e.detail })] })] }, i));
        }) }));
}
