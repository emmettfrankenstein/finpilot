import { useQueryClient } from '@tanstack/react-query';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import { api, refreshSession, setAccessToken, setSessionExpiredHandler } from '../api/client';
import type { TokenResponse, User } from '../api/types';

interface AuthState {
  user: User | null;
  status: 'restoring' | 'signed-in' | 'signed-out';
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthState['status']>('restoring');

  const signOutLocally = useCallback(() => {
    setAccessToken(null);
    setUser(null);
    setStatus('signed-out');
    queryClient.clear();
  }, [queryClient]);

  useEffect(() => {
    setSessionExpiredHandler(signOutLocally);
    let cancelled = false;
    refreshSession().then((session) => {
      if (cancelled) return;
      if (session) {
        setUser(session.user);
        setStatus('signed-in');
      } else setStatus('signed-out');
    });
    return () => {
      cancelled = true;
      setSessionExpiredHandler(null);
    };
  }, [signOutLocally]);

  const login = useCallback(async (username: string, password: string) => {
    const session = await api<TokenResponse>('/auth/login', { method: 'POST', json: { username, password } });
    setAccessToken(session.access);
    setUser(session.user);
    setStatus('signed-in');
  }, []);

  const logout = useCallback(async () => {
    try {
      await api('/auth/logout', { method: 'POST' });
    } finally {
      signOutLocally();
    }
  }, [signOutLocally]);

  const value = useMemo(() => ({ user, status, login, logout }), [user, status, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components -- hook is colocated with its provider
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
