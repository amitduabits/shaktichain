import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { setDocumentTitle } from '../auth/roles';
import './Auth.css';

const BASE = (import.meta.env.BASE_URL || '/').replace(/\/$/, '');
const USE_HASH = BASE !== '';
const REGISTER_HREF = USE_HASH ? '#/register' : '/register';

function Login({ onSwitchToRegister }) {
  const { login, demoLogin, error, clearError } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [remember, setRemember] = useState(false);
  const [loginLoading, setLoginLoading] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);
  const [localError, setLocalError] = useState('');

  useEffect(() => {
    setDocumentTitle('Login');
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLocalError('');
    clearError();

    if (!email || !password) {
      setLocalError('Please fill in all fields');
      return;
    }

    setLoginLoading(true);
    const result = await login(email, password, remember);
    setLoginLoading(false);

    if (!result.success) {
      setLocalError(result.error);
    }
  };

  const handleDemoLogin = async () => {
    setLocalError('');
    clearError();
    setDemoLoading(true);
    const result = await demoLogin();
    setDemoLoading(false);
    if (!result.success) {
      setLocalError(result.error);
    }
  };

  const displayError = localError || error;
  const isBusy = loginLoading || demoLoading;
  const handleSwitchToRegister = (event) => {
    event.preventDefault();
    if (onSwitchToRegister) {
      onSwitchToRegister();
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h2 className="auth-title">Login</h2>
        <p className="auth-subtitle">Welcome back to V2G Marketplace</p>
        <p className="auth-hint">New here? Register and pick your organisation type.</p>

        <form onSubmit={handleSubmit} className="auth-form">
          {displayError && (
            <div className="auth-error" data-testid="auth-error">{displayError}</div>
          )}

          <div className="form-group">
            <label htmlFor="email">Email (user id)</label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              disabled={isBusy}
              autoComplete="email"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              disabled={isBusy}
              autoComplete="current-password"
            />
          </div>

          <div className="form-group checkbox-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
                disabled={isBusy}
              />
              <span>Remember me</span>
            </label>
          </div>

          <button type="submit" className="auth-button" disabled={isBusy}>
            {loginLoading ? 'Logging in...' : 'Login'}
          </button>
          <button
            type="button"
            className="auth-button auth-button-secondary"
            onClick={handleDemoLogin}
            disabled={isBusy}
          >
            {demoLoading ? 'Entering Demo...' : 'Enter Demo'}
          </button>
        </form>

        <div className="auth-footer">
          <p>
            Don't have an account?{' '}
            <a
              href={REGISTER_HREF}
              className="auth-link"
              onClick={handleSwitchToRegister}
            >
              Register
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}

export default Login;
