import { useAuth } from '../contexts/AuthContext';

const NAV_ITEMS = [
  { path: '/', label: 'Dashboard', icon: '◉' },
  { path: '/incidents', label: 'Incidents', icon: '⚠' },
  { path: '/security', label: 'Security', icon: '🔐' },
  { path: '/audit', label: 'Audit Log', icon: '📋' },
  { path: '/services', label: 'Services', icon: '📊' },
  { path: '/system', label: 'System', icon: '⚙' },
];

export function Layout({ children, currentPath }: { children: React.ReactNode; currentPath: string }) {
  const { isAuthenticated, username, logout } = useAuth();

  return (
    <div className="app-layout">
      <aside className="app-sidebar">
        <div style={{ padding: '1rem 1rem 1.5rem', borderBottom: '1px solid var(--border)', marginBottom: '0.5rem' }}>
          <div style={{ fontSize: '1.1rem', fontWeight: 700, letterSpacing: '-0.02em' }}>AegisOps</div>
          <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>Operations Console</div>
        </div>
        <div className="nav-section">Navigation</div>
        {NAV_ITEMS.map(item => (
          <a
            key={item.path}
            href={item.path}
            className={`nav-item ${currentPath === item.path ? 'active' : ''}`}
            onClick={e => { e.preventDefault(); window.history.pushState({}, '', item.path); window.dispatchEvent(new PopStateEvent('popstate')); }}
          >
            <span style={{ fontSize: '0.9rem' }}>{item.icon}</span>
            {item.label}
          </a>
        ))}
        <div style={{ flex: 1 }} />
        {isAuthenticated && (
          <div style={{ padding: '0.75rem 1rem', borderTop: '1px solid var(--border)' }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{username}</div>
            <button className="btn" onClick={logout} style={{ fontSize: '0.75rem', padding: '0.25rem 0.75rem', marginTop: '0.25rem' }}>Logout</button>
          </div>
        )}
      </aside>
      <main className="app-main">{children}</main>
    </div>
  );
}