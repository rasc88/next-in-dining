import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import { useWaitlistService } from '../services';
import type { HostUser, LoginCredentials } from '../services/types';

const STORAGE_KEY = 'waitlist.session';

interface StoredSession {
  token: string;
  host: HostUser;
}

interface AuthContextValue {
  host: HostUser | null;
  loading: boolean;
  error: string | null;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function readStoredSession(): StoredSession | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as StoredSession) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const service = useWaitlistService();
  const [session, setSession] = useState<StoredSession | null>(() => readStoredSession());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const login = useCallback(
    async (credentials: LoginCredentials) => {
      setLoading(true);
      setError(null);
      try {
        const result = await service.login(credentials);
        const next: StoredSession = { token: result.token, host: result.host };
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next));
        setSession(next);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Could not sign in.');
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [service],
  );

  const logout = useCallback(async () => {
    await service.logout();
    sessionStorage.removeItem(STORAGE_KEY);
    setSession(null);
  }, [service]);

  const value = useMemo<AuthContextValue>(
    () => ({ host: session?.host ?? null, loading, error, login, logout }),
    [session, loading, error, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an <AuthProvider>.');
  return ctx;
}
