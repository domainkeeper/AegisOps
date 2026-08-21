import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { ApiError } from '../services/api';
export function Login() {
    const { login } = useAuth();
    const [username, setUsername] = useState('admin');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError('');
        try {
            await login(username, password);
        }
        catch (err) {
            setError(err instanceof ApiError ? err.message : 'Login failed');
            setLoading(false);
        }
    };
    return (_jsx("div", { className: "login-page", children: _jsxs("div", { className: "login-card", children: [_jsxs("div", { style: { textAlign: 'center', marginBottom: '1rem' }, children: [_jsx("div", { style: { fontSize: '1.5rem', fontWeight: 700, letterSpacing: '-0.02em' }, children: "AegisOps" }), _jsx("div", { style: { fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.15rem' }, children: "Operations Console" })] }), _jsxs("form", { onSubmit: handleSubmit, children: [error && _jsx("div", { className: "error-state", style: { marginBottom: '1rem' }, children: error }), _jsxs("div", { style: { marginBottom: '0.75rem' }, children: [_jsx("label", { htmlFor: "username", children: "Username" }), _jsx("input", { id: "username", value: username, onChange: e => setUsername(e.target.value), autoFocus: true })] }), _jsxs("div", { style: { marginBottom: '1.25rem' }, children: [_jsx("label", { htmlFor: "password", children: "Password" }), _jsx("input", { id: "password", type: "password", value: password, onChange: e => setPassword(e.target.value) })] }), _jsx("button", { className: "btn btn-primary", type: "submit", disabled: loading, style: { width: '100%', justifyContent: 'center' }, children: loading ? 'Signing in...' : 'Sign In' })] })] }) }));
}
