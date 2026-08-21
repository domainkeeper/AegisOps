import { useState, useEffect, useCallback } from 'react';
export function useApi(fetcher, deps = []) {
    const [state, setState] = useState({ data: null, loading: true, error: null });
    const refresh = useCallback(() => {
        setState(prev => ({ ...prev, loading: true, error: null }));
        fetcher().then(data => {
            setState({ data, loading: false, error: null });
        }).catch(err => {
            setState({ data: null, loading: false, error: err.message || 'Request failed' });
        });
    }, deps);
    useEffect(() => { refresh(); }, [refresh]);
    return { ...state, refresh };
}
