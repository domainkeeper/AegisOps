import { jsx as _jsx } from "react/jsx-runtime";
import { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../services/api';
const AuthContext = createContext(null);
export function AuthProvider({ children }) {
    const [state, setState] = useState({
        token: localStorage.getItem('aegisops_token'),
        username: '',
        isAuthenticated: false,
        loading: true,
    });
    useEffect(() => {
        api.session().then(resp => {
            setState(prev => ({
                ...prev,
                isAuthenticated: resp.authenticated,
                username: resp.username || '',
                loading: false,
            }));
        }).catch(() => {
            setState(prev => ({ ...prev, loading: false }));
        });
    }, []);
    const login = async (username, password) => {
        const resp = await api.login(username, password);
        localStorage.setItem('aegisops_token', resp.token);
        setState({ token: resp.token, username, isAuthenticated: true, loading: false });
    };
    const logout = () => {
        localStorage.removeItem('aegisops_token');
        setState({ token: null, username: '', isAuthenticated: false, loading: false });
        api.logout().catch(() => { });
    };
    return (_jsx(AuthContext.Provider, { value: { ...state, login, logout }, children: children }));
}
export function useAuth() {
    const ctx = useContext(AuthContext);
    if (!ctx)
        throw new Error('useAuth must be used within an AuthProvider');
    return ctx;
}
