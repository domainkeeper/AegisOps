import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useApi } from '../hooks/useApi';
import { api } from '../services/api';
import { LoadingState } from '../components/LoadingState';
import { ErrorState } from '../components/ErrorState';
export function Security() {
    const { data, loading, error, refresh } = useApi(() => api.authority(), []);
    if (loading)
        return _jsx(LoadingState, {});
    if (error)
        return _jsx(ErrorState, { message: error, onRetry: refresh });
    if (!data)
        return _jsx(ErrorState, { message: "Failed to load authority data" });
    // The backend returns `authority_model` but the type is `AuthorityResponse`
    // Cast to access the actual response structure
    const raw = data;
    const authority = raw.authority_model ?? [];
    const planActions = raw.plan_actions ?? [];
    const note = raw.note ?? '';
    return (_jsxs("div", { children: [_jsx("div", { className: "page-header", children: _jsxs("div", { children: [_jsx("div", { className: "page-title", children: "Security Authority Model" }), _jsx("div", { className: "page-subtitle", children: "Observational view of the authorization hierarchy" })] }) }), _jsxs("div", { className: "card", style: { marginBottom: '1.5rem' }, children: [_jsx("div", { className: "card-header", children: "Plan Actions" }), _jsx("p", { style: { fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }, children: "Top-level actions defined in the root plan that agents may be delegated to execute." }), planActions.length === 0 ? (_jsx("div", { className: "empty-state", children: "No plan actions defined" })) : (_jsx("div", { style: { display: 'flex', flexDirection: 'column', gap: '0.4rem' }, children: planActions.map((action, i) => (_jsxs("div", { style: {
                                display: 'flex',
                                alignItems: 'center',
                                gap: '0.5rem',
                                padding: '0.5rem 0.75rem',
                                background: 'var(--bg-primary)',
                                border: '1px solid var(--border)',
                                borderRadius: 'var(--radius)',
                                fontFamily: 'var(--font-mono)',
                                fontSize: '0.85rem',
                            }, children: [_jsxs("span", { style: { color: 'var(--accent)', fontWeight: 600 }, children: [i + 1, "."] }), action] }, i))) }))] }), authority.length === 0 ? (_jsx("div", { className: "card", children: _jsx("div", { className: "empty-state", children: "No delegation entries configured" }) })) : (_jsx("div", { style: { display: 'flex', flexDirection: 'column', gap: '0.75rem' }, children: authority.map((entry, i) => (_jsxs("div", { className: "card", style: {
                        borderLeft: `3px solid ${i === 0 ? 'var(--accent)' : i === 1 ? 'var(--green)' : 'var(--purple)'}`,
                    }, children: [_jsxs("div", { style: { display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }, children: [_jsx("span", { style: {
                                        width: '24px',
                                        height: '24px',
                                        borderRadius: '50%',
                                        background: 'var(--bg-primary)',
                                        border: '1px solid var(--border)',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        fontSize: '0.75rem',
                                        fontWeight: 600,
                                        color: 'var(--text-muted)',
                                    }, children: i + 1 }), _jsx("span", { style: { fontWeight: 600, fontSize: '0.95rem' }, children: entry.agent })] }), entry.steps && entry.steps.length > 0 && (_jsxs("div", { style: { marginBottom: '0.75rem' }, children: [_jsx("div", { style: {
                                        fontSize: '0.7rem',
                                        textTransform: 'uppercase',
                                        letterSpacing: '0.05em',
                                        color: 'var(--text-muted)',
                                        marginBottom: '0.3rem',
                                    }, children: "Steps" }), _jsx("div", { style: { display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }, children: entry.steps.map((step, si) => (_jsx("span", { style: {
                                            fontFamily: 'var(--font-mono)',
                                            fontSize: '0.8rem',
                                            background: 'var(--bg-primary)',
                                            border: '1px solid var(--border)',
                                            borderRadius: '3px',
                                            padding: '0.2rem 0.5rem',
                                        }, children: step }, si))) })] })), _jsxs("div", { children: [_jsx("div", { style: {
                                        fontSize: '0.7rem',
                                        textTransform: 'uppercase',
                                        letterSpacing: '0.05em',
                                        color: 'var(--text-muted)',
                                        marginBottom: '0.3rem',
                                    }, children: "Allowed Actions" }), _jsx("div", { style: { display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }, children: (entry.allowed_actions ?? []).map((action, ai) => (_jsx("span", { style: {
                                            fontFamily: 'var(--font-mono)',
                                            fontSize: '0.8rem',
                                            background: 'rgba(62,207,142,0.08)',
                                            border: '1px solid rgba(62,207,142,0.2)',
                                            borderRadius: '3px',
                                            padding: '0.2rem 0.5rem',
                                            color: 'var(--green)',
                                        }, children: action }, ai))) })] })] }, i))) })), note && (_jsxs("div", { className: "card", style: {
                    marginTop: '1.5rem',
                    borderColor: 'rgba(245,166,35,0.3)',
                    background: 'rgba(245,166,35,0.03)',
                }, children: [_jsx("div", { className: "card-header", style: { color: 'var(--yellow)' }, children: "Note" }), _jsx("p", { style: { fontSize: '0.85rem', color: 'var(--text-secondary)' }, children: note })] }))] }));
}
