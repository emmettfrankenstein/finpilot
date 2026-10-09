import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import type { Role } from '../api/types';
import { Loading } from '../components/DataState';
import { useAuth } from './AuthContext';

export function RequireAuth({ children, role }: { children: ReactNode; role?: Role }) {
  const { user, status } = useAuth();
  const location = useLocation();
  if (status === 'restoring') return <Loading label="Restoring your session" />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  if (role && user.role !== role) {
    return (
      <section className="panel" role="alert">
        <h1>Not permitted</h1>
        <p>This page requires the {role} role. Ask an administrator for access.</p>
      </section>
    );
  }
  return <>{children}</>;
}
