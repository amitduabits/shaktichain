import { useState, useEffect } from 'react';
import Dashboard from './components/Dashboard';
import Login from './pages/Login';
import Register from './pages/Register';
import { AuthProvider, useAuth } from './context/AuthContext';
import { getHealth } from './services/api';
import './App.css';

const APP_VERSION = '1.0.0';

function AppContent() {
  const { user, loading, isAuthenticated, logout } = useAuth();
  const [apiStatus, setApiStatus] = useState('checking');
  const [authView, setAuthView] = useState('login');

  useEffect(() => {
    const checkHealth = async () => {
      try {
        await getHealth();
        setApiStatus('connected');
      } catch (err) {
        setApiStatus('disconnected');
      }
    };

    checkHealth();
  }, []);

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
    if (authView === 'login') {
      return <Login onSwitchToRegister={() => setAuthView('register')} />;
    }
    return <Register onSwitchToLogin={() => setAuthView('login')} />;
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
              </span>
            </div>
            <div className="user-menu">
              <span className="user-email">{user?.email}</span>
              <button className="logout-button" onClick={logout}>
                Sign Out
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
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
