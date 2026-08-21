import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
export function StatusBadge({ status, label, dot }) {
    const cls = status.toLowerCase().replace(/\s+/g, '_');
    return (_jsxs("span", { className: `status-badge ${cls}`, children: [dot && _jsx("span", { className: `status-dot ${cls}` }), label || status] }));
}
