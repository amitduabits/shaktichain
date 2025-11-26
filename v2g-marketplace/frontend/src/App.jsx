import { useState, useEffect } from 'react';
import Dashboard from './components/Dashboard';
import { getHealth } from './services/api';
import './App.css';

const APP_VERSION = '1.0.0';

function App() {
  const [apiStatus, setApiStatus] = useState('checking');

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

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <h1>V2G Energy Marketplace</h1>
          <div className="header-status">
            <span className={`status-indicator ${apiStatus}`}></span>
            <span className="status-text">
              {apiStatus === 'checking' && 'Connecting...'}
              {apiStatus === 'connected' && 'API Connected'}
              {apiStatus === 'disconnected' && 'API Offline'}
            </span>
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

export default App;
