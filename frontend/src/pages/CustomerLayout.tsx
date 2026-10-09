import { Link, NavLink, Outlet, useParams } from 'react-router-dom';

import { useCustomer } from '../api/hooks';
import { Badge } from '../components/Badge';
import { QueryBoundary } from '../components/DataState';
import { date } from '../lib/format';

export function CustomerLayout() {
  const { customerId = '' } = useParams();
  const query = useCustomer(customerId);

  return (
    <>
      <p className="breadcrumb">
        <Link to="/customers">Customers</Link> / {customerId}
      </p>
      <QueryBoundary query={query} label="Loading customer">
        {(c) => (
          <>
            <header className="customer-header panel">
              <div>
                <h1>{c.full_name}</h1>
                <p className="muted">
                  {c.customer_id} · {c.email} · {c.phone} · {c.city}, {c.state}
                </p>
                <p className="badges">
                  <Badge value={c.kyc_status} label={`KYC ${c.kyc_status}`} />
                  <Badge value="SEGMENT" label={c.segment} />
                  <span className="muted small">Customer since {date(c.onboarded_at)}</span>
                </p>
              </div>
              <div className="risk-summary" aria-label="Latest risk profile">
                {c.latest_risk_profile ? (
                  <>
                    <div className="risk-score" aria-label={`Risk score ${c.latest_risk_profile.risk_score} of 100`}>
                      {c.latest_risk_profile.risk_score}
                      <span className="small muted">/100</span>
                    </div>
                    <div>
                      <strong>{c.latest_risk_profile.risk_level}</strong>
                      <div className="muted small">
                        {c.latest_risk_profile.horizon_years}-year horizon · {c.latest_risk_profile.liquidity_need.toLowerCase()} liquidity need
                      </div>
                      <div className="muted small">Assessed {date(c.latest_risk_profile.assessed_at)}</div>
                    </div>
                  </>
                ) : (
                  <span className="muted">No risk profile on record</span>
                )}
              </div>
            </header>
            <nav className="tabs" aria-label="Customer sections">
              <NavLink end to=".">
                Overview
              </NavLink>
              <NavLink to="positions">Positions</NavLink>
              <NavLink to="transactions">Transactions</NavLink>
              <NavLink to="goals">Goals</NavLink>
            </nav>
            <Outlet context={c} />
          </>
        )}
      </QueryBoundary>
    </>
  );
}
