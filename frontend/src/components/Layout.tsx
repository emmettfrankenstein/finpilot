import { Link, NavLink, Outlet } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';

export function Layout() {
  const { user, logout } = useAuth();
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="app-header">
        <Link to="/customers" className="brand">
          <img src="/favicon.svg" alt="" width={24} height={24} /> FinPilot
        </Link>
        <nav aria-label="Main">
          <NavLink to="/customers">Customers</NavLink>
          {user?.role === 'ADMIN' && <NavLink to="/admin/imports">Data imports</NavLink>}
        </nav>
        <div className="user-menu">
          <span className="muted small">
            {user?.username} · {user?.role}
          </span>
          <button type="button" className="button secondary small" onClick={() => logout()}>
            Sign out
          </button>
        </div>
      </header>
      <main id="main" className="container">
        <Outlet />
      </main>
      <footer className="app-footer muted small">Synthetic assessment data only. Not investment advice.</footer>
    </>
  );
}
