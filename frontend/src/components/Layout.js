import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useAuth } from '../contexts/AuthContext';
const NAV_ITEMS = [
    { path: '/', label: 'Dashboard', icon: '◉' },
    { path: '/incidents', label: 'Incidents', icon: '⚠' },
    { path: '/security', label: 'Security', icon: '🔐' },
    { path: '/audit', label: 'Audit Log', icon: '📋' },
    { path: '/services', label: 'Services', icon: '📊' },
    { path: '/system', label: 'System', icon: '⚙' },
];
export function Layout({ children, currentPath }) {
    const { isAuthenticated, username, logout } = useAuth();
    return (_jsxs("div", { className: "app-layout", children: [_jsxs("aside", { className: "app-sidebar", children: [_jsxs("div", { style: { padding: '1rem 1rem 1.5rem', borderBottom: '1px solid var(--border)', marginBottom: '0.5rem' }, children: [_jsx("div", { style: { fontSize: '1.1rem', fontWeight: 700, letterSpacing: '-0.02em' }, children: "AegisOps" }), _jsx("div", { style: { fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: '0.15rem' }, children: "Operations Console" })] }), _jsx("div", { className: "nav-section", children: "Navigation" }), NAV_ITEMS.map(item => (_jsxs("a", { href: item.path, className: `nav-item ${currentPath === item.path ? 'active' : ''}`, onClick: e => { e.preventDefault(); window.history.pushState({}, '', item.path); window.dispatchEvent(new PopStateEvent('popstate')); }, children: [_jsx("span", { style: { fontSize: '0.9rem' }, children: item.icon }), item.label] }, item.path))), _jsx("div", { style: { flex: 1 } }), isAuthenticated && (_jsxs("div", { style: { padding: '0.75rem 1rem', borderTop: '1px solid var(--border)' }, children: [_jsx("div", { style: { fontSize: '0.75rem', color: 'var(--text-muted)' }, children: username }), _jsx("button", { className: "btn", onClick: logout, style: { fontSize: '0.75rem', padding: '0.25rem 0.75rem', marginTop: '0.25rem' }, children: "Logout" })] }))] }), _jsx("main", { className: "app-main", children: children })] }));
}
