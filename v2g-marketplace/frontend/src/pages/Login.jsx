import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import './Auth.css';

function Login({ onSwitchToRegister }) {
  const { login, error, clearError } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [remember, setRemember] = useState(false);
  const [loading, setLoading] = useState(false);
  const [localError, setLocalError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLocalError('');
    clearError();

    if (!email || !password) {
      setLocalError('Please fill in all fields');
      return;
    }

    setLoading(true);
    const result = await login(email, password, remember);
    setLoading(false);

    if (!result.success) {
      setLocalError(result.error);
    }
  };

  const displayError = localError || error;
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

        <form onSubmit={handleSubmit} className="auth-form">
          {displayError && (
            <div className="auth-error">{displayError}</div>
          )}

          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              disabled={loading}
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
              disabled={loading}
              autoComplete="current-password"
            />
          </div>

          <div className="form-group checkbox-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
                disabled={loading}
              />
              <span>Remember me</span>
            </label>
          </div>

          <button type="submit" className="auth-button" disabled={loading}>
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        <div className="auth-footer">
          <p>
            Don't have an account?{' '}
            <a
              href="/register"
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
