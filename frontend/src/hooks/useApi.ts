import { useState, useEffect, useCallback } from 'react';

interface UseApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

export function useApi<T>(fetcher: () => Promise<T>, deps: any[] = []) {
  const [state, setState] = useState<UseApiState<T>>({ data: null, loading: true, error: null });

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