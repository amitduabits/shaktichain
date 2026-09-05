import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import {
  VIEW_ROLE_KEY,
  isDemoOnlyFlag,
  normalizeRole,
} from '../auth/roles';
import { useAuth } from './AuthContext';

const RoleViewContext = createContext(null);

function readStoredViewRole() {
  if (!isDemoOnlyFlag() || typeof sessionStorage === 'undefined') {
    return null;
  }
  try {
    const value = sessionStorage.getItem(VIEW_ROLE_KEY);
    return value ? normalizeRole(value) : null;
  } catch {
    return null;
  }
}

export function RoleViewProvider({ children }) {
  const { user, loading, isAuthenticated } = useAuth();
  const demoOnly = isDemoOnlyFlag();
  const [viewRole, setViewRoleState] = useState(readStoredViewRole);

  const storedRole = normalizeRole(user?.role);
  const effectiveRole = demoOnly && viewRole ? normalizeRole(viewRole) : storedRole;

  const setViewRole = useCallback((role) => {
    if (!demoOnly) {
      return;
    }
    const next = normalizeRole(role);
    setViewRoleState(next);
    try {
      sessionStorage.setItem(VIEW_ROLE_KEY, next);
    } catch {
      // ignore
    }
  }, [demoOnly]);

  const clearViewRole = useCallback(() => {
    setViewRoleState(null);
    try {
      sessionStorage.removeItem(VIEW_ROLE_KEY);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      clearViewRole();
    }
  }, [clearViewRole, isAuthenticated, loading]);

  const value = useMemo(
    () => ({
      storedRole,
      viewRole: demoOnly ? viewRole : null,
      effectiveRole,
      setViewRole,
      clearViewRole,
      demoOnly,
    }),
    [clearViewRole, demoOnly, effectiveRole, setViewRole, storedRole, viewRole]
  );

  return <RoleViewContext.Provider value={value}>{children}</RoleViewContext.Provider>;
}

export function useRoleView() {
  const context = useContext(RoleViewContext);
  if (!context) {
    throw new Error('useRoleView must be used within a RoleViewProvider');
  }
  return context;
}

export default RoleViewContext;
