import { jsx as _jsx } from "react/jsx-runtime";
import { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { Layout } from './components/Layout';
import { LoadingState } from './components/LoadingState';
import { Dashboard } from './pages/Dashboard';
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
    if (loading)
        return _jsx(LoadingState, { message: "Initializing..." });
    if (!isAuthenticated)
        return _jsx(Login, {});
    const renderPage = () => {
        if (path === '/')
            return _jsx(Dashboard, {});
        if (path.startsWith('/incidents/')) {
            const id = path.split('/')[2];
            return _jsx(IncidentDetail, { incidentId: id });
        }
        if (path === '/incidents')
            return _jsx(Dashboard, {});
        if (path === '/security')
            return _jsx(Security, {});
        if (path === '/audit')
            return _jsx(Audit, {});
        if (path === '/services')
            return _jsx(Services, {});
        if (path === '/system')
            return _jsx(SystemConfig, {});
        return _jsx(Dashboard, {});
    };
    return _jsx(Layout, { currentPath: path, children: renderPage() });
}
export default function App() {
    return (_jsx(AuthProvider, { children: _jsx(Router, {}) }));
}
