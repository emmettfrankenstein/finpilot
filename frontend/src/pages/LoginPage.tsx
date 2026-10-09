import { useState, type FormEvent } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';

import { ApiError } from '../api/client';
import { useAuth } from '../auth/AuthContext';

export function LoginPage() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? '/customers';
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (user) return <Navigate to={from} replace />;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username.trim(), password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 429
          ? 'Too many attempts. Wait a minute and try again.'
          : err instanceof ApiError
            ? err.message
            : 'Sign-in failed.',
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <form className="panel login-card" onSubmit={onSubmit} noValidate>
        <h1>
          <img src="/favicon.svg" alt="" width={28} height={28} /> FinPilot
        </h1>
        <p className="muted">Sign in to the portfolio service console.</p>
        <label htmlFor="username">Username</label>
        <input id="username" name="username" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required />
        <label htmlFor="password">Password</label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="button" disabled={submitting || !username || !password}>
          {submitting ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </main>
  );
}
