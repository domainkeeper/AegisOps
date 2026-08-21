import { useEffect, useRef, useState } from 'react';
const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';
export function useSSE() {
    const [events, setEvents] = useState([]);
    const lastId = useRef(0);
    const [connected, setConnected] = useState(false);
    useEffect(() => {
        const token = localStorage.getItem('aegisops_token');
        const headers = {};
        if (token)
            headers['Authorization'] = `Bearer ${token}`;
        const es = new EventSource(`${API_BASE}/events`, { headers });
        es.onopen = () => setConnected(true);
        es.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data);
                if (data.id > lastId.current) {
                    lastId.current = data.id;
                    setEvents(prev => [...prev, data].slice(-100));
                }
            }
            catch { }
        };
        es.onerror = () => setConnected(false);
        return () => es.close();
    }, []);
    return { events, connected };
}
