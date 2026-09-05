import { useCallback, useEffect, useState } from 'react';
import Dashboard from './components/Dashboard';
import Login from './pages/Login';
import Register from './pages/Register';
import { AuthProvider, useAuth } from './context/AuthContext';
import { DemoLedgerProvider } from './context/DemoLedgerContext';
import { Web3Provider } from './providers/Web3Provider';
import { ConnectWallet, TransactionStatus } from './components/web3';
import { getHealth } from './services/api';
import './App.css';

const APP_VERSION = '1.0.0';
const AUTH_ROUTES = new Set(['/login', '/register']);
const BASE = (import.meta.env.BASE_URL || '/').replace(/\/$/, '');
const USE_HASH = BASE !== '';
const DEMO_ONLY = ['1', 'true', 'yes', 'on'].includes(
  String(import.meta.env.VITE_DEMO_ONLY || '').trim().toLowerCase()
);

function normalizePath(pathname) {
  if (pathname === '/dashboard') {
    return '/dashboard';
  }
  if (pathname === '/register') {
    return '/register';
  }
  if (pathname === '/login') {
    return '/login';
  }
  return '/login';
}

function AppContent() {
  const { user, loading, isAuthenticated, logout } = useAuth();
  const [apiStatus, setApiStatus] = useState('checking');
  const [currentPath, setCurrentPath] = useState(() => {
    if (USE_HASH) {
      return normalizePath(window.location.hash.replace(/^#/, '') || '/login');
    }
    return normalizePath(window.location.pathname);
  });

  const navigate = useCallback((path, replace = false) => {
    if (USE_HASH) {
      const next = `#${path}`;
      if (replace) {
        window.history.replaceState({}, '', next);
      } else if (window.location.hash !== next) {
        window.location.hash = path;
      }
      setCurrentPath(normalizePath(path));
      return;
    }
    if (window.location.pathname !== path) {
      if (replace) {
        window.history.replaceState({}, '', path);
      } else {
        window.history.pushState({}, '', path);
      }
    }
    setCurrentPath(path);
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

    if (AUTH_ROUTES.has(currentPath)) {
      navigate('/dashboard', true);
    }
  }, [currentPath, isAuthenticated, loading, navigate]);

  const handleLogout = useCallback(() => {
    logout();
    navigate('/login', true);
  }, [logout, navigate]);

  if (loading) {
    return (
      <div className="app">
        <div className="loading-screen">
          <div className="loading-spinner"></div>
          <p>Loading...</p>
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

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <h1>V2G Energy Marketplace</h1>
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
      </header>

      <main className="app-main">
        <Dashboard />
      </main>

      <footer className="app-footer">
        <div className="footer-content">
          <span className="footer-brand">ShaktiChain V2G Marketplace</span>
          <span className="footer-version">v{APP_VERSION}</span>
        </div>
      </footer>

      {/* Transaction notifications */}
      <TransactionStatus />
    </div>
  );
}

function App() {
  return (
    <Web3Provider defaultMode="simulation" theme="dark">
      <AuthProvider>
        <DemoLedgerProvider>
          <AppContent />
        </DemoLedgerProvider>
      </AuthProvider>
    </Web3Provider>
  );
}

export default App;
