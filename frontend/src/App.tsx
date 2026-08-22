import { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { Layout } from './components/Layout';
import { LoadingState } from './components/LoadingState';
import { Dashboard } from './pages/Dashboard';
import { Incidents } from './pages/Incidents';
import { IncidentDetail } from './pages/IncidentDetail';
import { Security } from './pages/Security';
import { Audit } from './pages/Audit';
import { Services } from './pages/Services';
import { SystemConfig } from './pages/SystemConfig';
import { Login } from './pages/Login';

function getPath() {
  return window.location.pathname === '/' ? '/' : window.location.pathname;
}

function Router() {
  const [path, setPath] = useState(getPath());
  const { isAuthenticated, loading } = useAuth();

  useEffect(() => {
    const handler = () => setPath(getPath());
    window.addEventListener('popstate', handler);
    return () => window.removeEventListener('popstate', handler);
  }, []);

  if (loading) return <LoadingState message="Initializing..." />;

  if (!isAuthenticated) return <Login />;

  const renderPage = () => {
    if (path === '/') return <Dashboard />;
    if (path.startsWith('/incidents/')) {
      const id = path.split('/')[2];
      return <IncidentDetail incidentId={id} />;
    }
    if (path === '/incidents') return <Incidents />;
    if (path === '/security') return <Security />;
    if (path === '/audit') return <Audit />;
    if (path === '/services') return <Services />;
    if (path === '/system') return <SystemConfig />;
    return <Dashboard />;
  };

  return <Layout currentPath={path}>{renderPage()}</Layout>;
}

export default function App() {
  return (
    <AuthProvider>
      <Router />
    </AuthProvider>
  );
}