import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import {
  login as apiLogin,
  register as apiRegister,
  demoLogin as apiDemoLogin,
  getCurrentUser,
  getHealth,
} from '../services/api';
import {
  registerLocal,
  loginLocal,
  findLocalUserById,
  localTokenFor,
  LOCAL_TOKEN_PREFIX,
  userFromRecord,
} from '../auth/localAccounts';

const AuthContext = createContext(null);

const TOKEN_KEY = 'auth_token';
const REMEMBER_KEY = 'auth_remember';
const DEMO_TOKEN = 'demo-local';
const DEMO_USER = {
  id: 'demo-user',
  email: 'demo@v2g.local',
  role: 'ev_owner',
  created_at: '2026-01-01T00:00:00Z',
};

function isDemoOnly() {
  const value = String(import.meta.env.VITE_DEMO_ONLY || '').trim().toLowerCase();
  return ['1', 'true', 'yes', 'on'].includes(value);
}

function parseJwt(token) {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch {
    return null;
  }
}

function isJwtToken(token) {
  return typeof token === 'string' && token.split('.').length === 3 && token.includes('.');
}

function isLocalSessionToken(token) {
  return typeof token === 'string' && token.startsWith(LOCAL_TOKEN_PREFIX);
}

function isTokenExpired(token) {
  const payload = parseJwt(token);
  if (!payload || !payload.exp) return true;
  return Date.now() >= payload.exp * 1000;
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const apiUpRef = useRef(isDemoOnly() ? false : null);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REMEMBER_KEY);
    setUser(null);
  }, []);

  const shouldUseLocalAuth = useCallback(async () => {
    if (isDemoOnly()) {
      apiUpRef.current = false;
      return true;
    }
    if (apiUpRef.current === false) {
      return true;
    }
    if (apiUpRef.current === true) {
      return false;
    }
    try {
      await getHealth();
      apiUpRef.current = true;
      return false;
    } catch {
      apiUpRef.current = false;
      return true;
    }
  }, []);

  const applySession = useCallback((nextUser, token, remember = false) => {
    localStorage.setItem(TOKEN_KEY, token);
    if (remember) {
      localStorage.setItem(REMEMBER_KEY, 'true');
    } else {
      localStorage.removeItem(REMEMBER_KEY);
    }
    setUser(nextUser);
    return nextUser;
  }, []);

  const checkAuth = useCallback(async () => {
    const token = localStorage.getItem(TOKEN_KEY);

    if (!token) {
      setLoading(false);
      return;
    }

    if (token === DEMO_TOKEN) {
      setUser(DEMO_USER);
      setLoading(false);
      return;
    }

    if (isLocalSessionToken(token)) {
      const id = token.slice(LOCAL_TOKEN_PREFIX.length);
      const record = findLocalUserById(id);
      if (record) {
        setUser(userFromRecord(record));
      } else {
        logout();
      }
      setLoading(false);
      return;
    }

    if (isJwtToken(token) && isTokenExpired(token)) {
      logout();
      setLoading(false);
      return;
    }

    try {
      const userData = await getCurrentUser();
      setUser(userData);
    } catch (_error) {
      logout();
    } finally {
      setLoading(false);
    }
  }, [logout]);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  useEffect(() => {
    shouldUseLocalAuth();
  }, [shouldUseLocalAuth]);

  useEffect(() => {
    const interval = setInterval(() => {
      const token = localStorage.getItem(TOKEN_KEY);
      if (token && isJwtToken(token) && isTokenExpired(token)) {
        logout();
      }
    }, 60000);

    return () => clearInterval(interval);
  }, [logout]);

  const consumeToken = useCallback(async (token, remember = false) => {
    if (token === DEMO_TOKEN) {
      return applySession(DEMO_USER, token, remember);
    }
    if (isLocalSessionToken(token)) {
      const id = token.slice(LOCAL_TOKEN_PREFIX.length);
      const record = findLocalUserById(id);
      if (!record) {
        throw new Error('Local session not found');
      }
      return applySession(userFromRecord(record), token, remember);
    }

    localStorage.setItem(TOKEN_KEY, token);
    if (remember) {
      localStorage.setItem(REMEMBER_KEY, 'true');
    } else {
      localStorage.removeItem(REMEMBER_KEY);
    }
    const userData = await getCurrentUser();
    setUser(userData);
    return userData;
  }, [applySession]);

  const login = async (email, password, remember = false) => {
    setError(null);
    try {
      if (await shouldUseLocalAuth()) {
        const result = await loginLocal({ email, password });
        if (!result.ok) {
          setError(result.error);
          return { success: false, error: result.error };
        }
        applySession(result.user, localTokenFor(result.user.id), remember);
        return { success: true };
      }
      const response = await apiLogin({ email, password });
      await consumeToken(response.access_token, remember);
      return { success: true };
    } catch (err) {
      const message = err.message || 'Login failed';
      setError(message);
      return { success: false, error: message };
    }
  };

  const register = async (email, password, role = 'ev_owner') => {
    setError(null);
    try {
      if (await shouldUseLocalAuth()) {
        const result = await registerLocal({ email, password, role });
        if (!result.ok) {
          setError(result.error);
          return { success: false, error: result.error };
        }
        applySession(result.user, localTokenFor(result.user.id), false);
        return { success: true };
      }
      const response = await apiRegister({ email, password, role });
      await consumeToken(response.access_token, false);
      return { success: true };
    } catch (err) {
      const message = err.message || 'Registration failed';
      setError(message);
      return { success: false, error: message };
    }
  };

  const demoLogin = async () => {
    setError(null);
    try {
      if (await shouldUseLocalAuth()) {
        applySession(DEMO_USER, DEMO_TOKEN, false);
        return { success: true };
      }
      const response = await apiDemoLogin();
      await consumeToken(response.access_token, false);
      return { success: true };
    } catch (err) {
      const message = err.message || 'Demo login failed';
      setError(message);
      return { success: false, error: message };
    }
  };

  const value = {
    user,
    loading,
    error,
    isAuthenticated: !!user,
    login,
    demoLogin,
    logout,
    register,
    consumeToken,
    clearError: () => setError(null),
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export default AuthContext;
