import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { api } from '../services/api';

interface AuthState {
  token: string | null;
  username: string;
  isAuthenticated: boolean;
  loading: boolean;
}

interface AuthContextType extends AuthState {
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
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

  const login = async (username: string, password: string) => {
    const resp = await api.login(username, password);
    localStorage.setItem('aegisops_token', resp.token);
    setState({ token: resp.token, username, isAuthenticated: true, loading: false });
  };

  const logout = () => {
    localStorage.removeItem('aegisops_token');
    setState({ token: null, username: '', isAuthenticated: false, loading: false });
    api.logout().catch(() => {});
  };

  return (
    <AuthContext.Provider value={{ ...state, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}