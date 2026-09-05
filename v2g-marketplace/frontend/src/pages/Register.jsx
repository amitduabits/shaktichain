import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import './Auth.css';

const BASE = (import.meta.env.BASE_URL || '/').replace(/\/$/, '');
const USE_HASH = BASE !== '';
const LOGIN_HREF = USE_HASH ? '#/login' : '/login';

function Register({ onSwitchToLogin }) {
  const { register, error, clearError } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [localError, setLocalError] = useState('');

  const validateForm = () => {
    if (!email || !password) {
      setLocalError('Please fill in all fields');
      return false;
    }

    if (!email.includes('@')) {
      setLocalError('Please enter a valid email address');
      return false;
    }

    if (password.length < 6) {
      setLocalError('Password must be at least 6 characters');
      return false;
    }

    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLocalError('');
    clearError();

    if (!validateForm()) {
      return;
    }

    setLoading(true);
    const result = await register(email, password);
    setLoading(false);

    if (!result.success) {
      setLocalError(result.error);
    }
  };

  const displayError = localError || error;
  const handleSwitchToLogin = (event) => {
    event.preventDefault();
    if (onSwitchToLogin) {
      onSwitchToLogin();
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h2 className="auth-title">Register</h2>
        <p className="auth-subtitle">Join the V2G Marketplace</p>

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
              placeholder="At least 6 characters"
              disabled={loading}
              autoComplete="new-password"
            />
          </div>

          <button type="submit" className="auth-button" disabled={loading}>
            {loading ? 'Registering...' : 'Register'}
          </button>
        </form>

        <div className="auth-footer">
          <p>
            Already have an account?{' '}
            <a
              href={LOGIN_HREF}
              className="auth-link"
              onClick={handleSwitchToLogin}
            >
              Login
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}

export default Register;
