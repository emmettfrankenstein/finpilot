import { Navigate, Route, Routes } from 'react-router-dom';

import { RequireAuth } from './auth/RequireAuth';
import { Layout } from './components/Layout';
import { CustomerLayout } from './pages/CustomerLayout';
import { CustomersPage } from './pages/CustomersPage';
import { GoalsPage } from './pages/GoalsPage';
import { ImportPage } from './pages/ImportPage';
import { LoginPage } from './pages/LoginPage';
import { OverviewPage } from './pages/OverviewPage';
import { PositionsPage } from './pages/PositionsPage';
import { TransactionsPage } from './pages/TransactionsPage';

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to="/customers" replace />} />
        <Route path="customers" element={<CustomersPage />} />
        <Route path="customers/:customerId" element={<CustomerLayout />}>
          <Route index element={<OverviewPage />} />
          <Route path="positions" element={<PositionsPage />} />
          <Route path="transactions" element={<TransactionsPage />} />
          <Route path="goals" element={<GoalsPage />} />
        </Route>
        <Route
          path="admin/imports"
          element={
            <RequireAuth role="ADMIN">
              <ImportPage />
            </RequireAuth>
          }
        />
        <Route path="*" element={<p className="panel">Page not found.</p>} />
      </Route>
    </Routes>
  );
}
