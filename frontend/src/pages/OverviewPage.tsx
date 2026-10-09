import { Link, useParams } from 'react-router-dom';

import { useGoals, usePortfolio } from '../api/hooks';
import { AllocationChart } from '../components/AllocationChart';
import { Badge } from '../components/Badge';
import { Empty, QueryBoundary } from '../components/DataState';
import { FreshnessNote } from '../components/FreshnessNote';
import { GoalProgress } from '../components/GoalProgress';
import { StatCard } from '../components/StatCard';
import { humanize, money, percent, signClass } from '../lib/format';

export function OverviewPage() {
  const { customerId = '' } = useParams();
  const portfolio = usePortfolio(customerId);
  const goals = useGoals(customerId);

  return (
    <div className="stack">
      <QueryBoundary query={portfolio} label="Loading portfolio">
        {(p) => (
          <>
            <FreshnessNote asOf={p.as_of} />
            <dl className="stat-grid">
              <StatCard label="Total portfolio value" value={money(p.totals.market_value)} />
              <StatCard label="Cost basis" value={money(p.totals.cost_basis)} />
              <StatCard
                label="Unrealised gain/loss"
                value={money(p.totals.unrealised_pnl)}
                hint={percent(p.totals.unrealised_pnl_pct, true)}
                tone={signClass(p.totals.unrealised_pnl)}
              />
              <StatCard label="Positions" value={p.totals.position_count} hint={`${p.accounts.length} account(s)`} />
            </dl>

            <div className="two-col">
              <section className="panel" aria-labelledby="accounts-heading">
                <h2 id="accounts-heading">Accounts</h2>
                {p.accounts.length === 0 ? (
                  <Empty title="No investment accounts" />
                ) : (
                  <ul className="account-list">
                    {p.accounts.map((a) => (
                      <li key={a.account_id} className="account-card">
                        <div className="account-card-head">
                          <strong>{humanize(a.account_type)}</strong>
                          <Badge value={a.status} />
                        </div>
                        <div className="muted small">
                          {a.account_id} · {a.provider}
                        </div>
                        <div className="account-card-value">{money(a.market_value)}</div>
                        <div className={`small ${signClass(a.unrealised_pnl)}`}>
                          {money(a.unrealised_pnl)} ({percent(a.unrealised_pnl_pct, true)}) · {a.position_count} positions
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
              <section className="panel" aria-labelledby="allocation-heading">
                <h2 id="allocation-heading">Asset allocation</h2>
                {p.allocation.length === 0 ? <Empty title="No holdings in the latest snapshot" /> : <AllocationChart data={p.allocation} />}
              </section>
            </div>
          </>
        )}
      </QueryBoundary>

      <section className="panel" aria-labelledby="goals-heading">
        <div className="panel-head">
          <h2 id="goals-heading">Goals</h2>
          <Link to="goals">Manage goals</Link>
        </div>
        <QueryBoundary query={goals} label="Loading goals">
          {(list) =>
            list.length === 0 ? (
              <Empty title="No financial goals recorded" />
            ) : (
              <ul className="goal-summary">
                {list.map((g) => (
                  <li key={g.goal_id}>
                    <div className="goal-summary-head">
                      <span>
                        <strong>{g.goal_name}</strong> <span className="muted small">{humanize(g.goal_type)}</span>
                      </span>
                      <span>
                        {g.flags.map((f) => (
                          <Badge key={f} value={f} />
                        ))}{' '}
                        <Badge value={g.priority} label={`${g.priority} priority`} />
                      </span>
                    </div>
                    <GoalProgress goal={g} />
                  </li>
                ))}
              </ul>
            )
          }
        </QueryBoundary>
      </section>
    </div>
  );
}
