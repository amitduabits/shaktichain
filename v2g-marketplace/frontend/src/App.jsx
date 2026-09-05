import { useCallback, useEffect, useState } from 'react';
import Login from './pages/Login';
import Register from './pages/Register';
import { RoleHome } from './pages/RoleHome';
import { RoleAssets } from './pages/RoleAssets';
import { RoleReports } from './pages/RoleReports';
import { MarketPage } from './pages/MarketPage';
import { SettlementPage } from './pages/SettlementPage';
import { AdminPage } from './pages/AdminPage';
import { SettingsPage } from './pages/SettingsPage';
import { ForbiddenPage, NotFoundPage } from './pages/ErrorPages';
import { AuthProvider, useAuth } from './context/AuthContext';
import { DemoLedgerProvider } from './context/DemoLedgerContext';
import { RoleViewProvider, useRoleView } from './context/RoleViewContext';
import { Web3Provider } from './providers/Web3Provider';
import { ConnectWallet, TransactionStatus } from './components/web3';
import { getHealth } from './services/api';
import {
  ALL_ROLES,
  canAccess,
  isDemoOnlyFlag,
  knownAppPath,
  navItems,
  roleLabel,
  screenTitle,
  setDocumentTitle,
} from './auth/roles';
import './styles/tokens.css';
import './App.css';

const APP_VERSION = '1.0.0';
const AUTH_ROUTES = new Set(['/login', '/register']);
const BASE = (import.meta.env.BASE_URL || '/').replace(/\/$/, '');
const USE_HASH = BASE !== '';
const DEMO_ONLY = isDemoOnlyFlag();

function normalizePath(pathname) {
  const raw = pathname || '/login';
  if (raw === '/dashboard') {
    return '/home';
  }
  if (raw === '/' || raw === '') {
    return '/login';
  }
  return raw;
}

function AppContent() {
  const { user, loading, isAuthenticated, logout } = useAuth();
  const { effectiveRole, setViewRole, demoOnly } = useRoleView();
  const [apiStatus, setApiStatus] = useState('checking');
  const [currentPath, setCurrentPath] = useState(() => {
    if (USE_HASH) {
      return normalizePath(window.location.hash.replace(/^#/, '') || '/login');
    }
    return normalizePath(window.location.pathname);
  });

  const navigate = useCallback((path, replace = false) => {
    const nextPath = normalizePath(path);
    if (USE_HASH) {
      const next = `#${nextPath}`;
      if (replace) {
        window.history.replaceState({}, '', next);
      } else if (window.location.hash !== next) {
        window.location.hash = nextPath;
      }
      setCurrentPath(nextPath);
      return;
    }
    if (window.location.pathname !== nextPath) {
      if (replace) {
        window.history.replaceState({}, '', nextPath);
      } else {
        window.history.pushState({}, '', nextPath);
      }
    }
    setCurrentPath(nextPath);
  }, []);

  useEffect(() => {
    if (DEMO_ONLY) {
      setApiStatus('demo');
      return;
    }
    const checkHealth = async () => {
      try {
        await getHealth();
        setApiStatus('connected');
      } catch (_error) {
        setApiStatus('disconnected');
      }
    };
    checkHealth();
  }, []);

  useEffect(() => {
    const onPopState = () => {
      if (USE_HASH) {
        setCurrentPath(normalizePath(window.location.hash.replace(/^#/, '') || '/login'));
        return;
      }
      setCurrentPath(normalizePath(window.location.pathname));
    };
    window.addEventListener('popstate', onPopState);
    window.addEventListener('hashchange', onPopState);
    return () => {
      window.removeEventListener('popstate', onPopState);
      window.removeEventListener('hashchange', onPopState);
    };
  }, []);

  useEffect(() => {
    if (loading) {
      return;
    }
    if (!isAuthenticated) {
      if (!AUTH_ROUTES.has(currentPath)) {
        navigate('/login', true);
      }
      return;
    }
    if (AUTH_ROUTES.has(currentPath) || currentPath === '/login') {
      navigate('/home', true);
      return;
    }
    const raw = USE_HASH
      ? window.location.hash.replace(/^#/, '')
      : window.location.pathname;
    if (raw === '/dashboard') {
      navigate('/home', true);
    }
  }, [currentPath, isAuthenticated, loading, navigate]);

  useEffect(() => {
    if (!isAuthenticated) {
      setDocumentTitle(currentPath === '/register' ? 'Register' : 'Login');
      return;
    }
    setDocumentTitle(screenTitle(currentPath, effectiveRole));
  }, [currentPath, effectiveRole, isAuthenticated]);

  const handleLogout = useCallback(() => {
    logout();
    navigate('/login', true);
  }, [logout, navigate]);

  if (loading) {
    return (
      <div className="app">
        <div className="loading-screen">
          <div className="loading-spinner"></div>
          <p>Loading…</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    if (currentPath === '/register') {
      return <Register onSwitchToLogin={() => navigate('/login')} />;
    }
    return <Login onSwitchToRegister={() => navigate('/register')} />;
  }

  const topNav = navItems(effectiveRole, false);
  const bottomNav = navItems(effectiveRole, true);
  const guarded = knownAppPath(currentPath);
  const allowed = canAccess(currentPath, effectiveRole);
  const requiredLabel = currentPath === '/admin' ? 'Admin' : currentPath === '/market' || currentPath === '/settlement'
    ? 'trader'
    : roleLabel(effectiveRole);

  let body = null;
  if (!guarded) {
    body = <NotFoundPage onHome={() => navigate('/home')} />;
  } else if (currentPath === '/403' || (guarded && !allowed && !AUTH_ROUTES.has(currentPath) && currentPath !== '/home')) {
    body = <ForbiddenPage requiredLabel={requiredLabel} onHome={() => navigate('/home')} />;
  } else if (currentPath === '/404') {
    body = <NotFoundPage onHome={() => navigate('/home')} />;
  } else if (currentPath === '/home') {
    body = <RoleHome role={effectiveRole} onNavigate={navigate} />;
  } else if (currentPath === '/assets') {
    body = <RoleAssets role={effectiveRole} />;
  } else if (currentPath === '/reports') {
    body = <RoleReports role={effectiveRole} onNavigate={navigate} />;
  } else if (currentPath === '/market') {
    body = <MarketPage role={effectiveRole} />;
  } else if (currentPath === '/settlement') {
    body = <SettlementPage />;
  } else if (currentPath === '/admin') {
    body = <AdminPage />;
  } else if (currentPath === '/settings') {
    body = <SettingsPage onNavigate={navigate} onLogout={handleLogout} />;
  } else {
    body = <NotFoundPage onHome={() => navigate('/home')} />;
  }

  return (
    <div className="app">
      <a className="skip-link" href="#main">Skip to main</a>
      <header className="app-header">
        <div className="header-content">
          <div className="brand-block">
            <h1>Shakti-Chain</h1>
            <p className="role-subtitle">{roleLabel(effectiveRole)}</p>
          </div>
          <nav className="top-nav" aria-label="Primary">
            {topNav.map((item) => (
              <button
                key={item.path}
                type="button"
                className={`nav-link ${currentPath === item.path ? 'active' : ''}`}
                onClick={() => navigate(item.path)}
              >
                {item.label}
              </button>
            ))}
          </nav>
          <div className="header-right">
            <div className="header-status">
              <span className={`status-indicator ${apiStatus}`}></span>
              <span className="status-text">
                {apiStatus === 'checking' && 'Connecting...'}
                {apiStatus === 'connected' && 'API Connected'}
                {apiStatus === 'disconnected' && 'API Offline'}
                {apiStatus === 'demo' && 'Simulation demo'}
              </span>
            </div>
            {demoOnly && (
              <label className="role-switcher-label">
                View as
                <select
                  data-testid="role-switcher"
                  value={effectiveRole}
                  onChange={(event) => setViewRole(event.target.value)}
                >
                  {ALL_ROLES.map((id) => (
                    <option key={id} value={id}>{roleLabel(id)}</option>
                  ))}
                </select>
              </label>
            )}
            {!DEMO_ONLY && (
              <div className="web3-wallet">
                <ConnectWallet compact />
              </div>
            )}
            <div className="user-menu">
              <span className="user-email">{user?.email}</span>
              <button className="logout-button" onClick={handleLogout}>
                Logout
              </button>
            </div>
          </div>
        </div>
        <p data-testid="sim-disclaimer" className="sim-strip sim-disclaimer">
          Simulation. Not connected to a live DISCOM.
        </p>
      </header>

      <main id="main" className="app-main">
        {body}
      </main>

      <nav className="bottom-nav" aria-label="Mobile">
        {bottomNav.map((item) => (
          <button
            key={item.path}
            type="button"
            className={`nav-link ${currentPath === item.path ? 'active' : ''}`}
            onClick={() => navigate(item.path)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      <footer className="app-footer">
        <div className="footer-content">
          <span className="footer-brand">Shakti-Chain V2G Marketplace</span>
          <span className="footer-version">v{APP_VERSION}</span>
        </div>
      </footer>

      <TransactionStatus />
    </div>
  );
}

function App() {
  return (
    <Web3Provider defaultMode="simulation" theme="dark">
      <AuthProvider>
        <RoleViewProvider>
          <DemoLedgerProvider>
            <AppContent />
          </DemoLedgerProvider>
        </RoleViewProvider>
      </AuthProvider>
    </Web3Provider>
  );
}

export default App;
