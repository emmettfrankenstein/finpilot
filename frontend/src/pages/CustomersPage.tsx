import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { useCustomers } from '../api/hooks';
import { Badge } from '../components/Badge';
import { Empty, QueryBoundary } from '../components/DataState';
import { Pagination } from '../components/Pagination';
import { money } from '../lib/format';

const PAGE_SIZE = 25;

export function CustomersPage() {
  const [params, setParams] = useSearchParams();
  const search = params.get('search') ?? '';
  const kyc = params.get('kyc_status') ?? '';
  const segment = params.get('segment') ?? '';
  const ordering = params.get('ordering') ?? 'customer_id';
  const page = Number(params.get('page') ?? '1');
  const [draft, setDraft] = useState(search);

  // Debounce typing into the URL (which drives the query).
  useEffect(() => {
    const handle = setTimeout(() => {
      if (draft !== search) update({ search: draft });
    }, 300);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft]);

  function update(changes: Record<string, string>) {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(changes)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    if (!('page' in changes)) next.delete('page');
    setParams(next, { replace: true });
  }

  const query = useCustomers({ search, kyc_status: kyc, segment, ordering, page });

  return (
    <>
      <h1>Customers</h1>
      <form className="filters" role="search" onSubmit={(e) => e.preventDefault()}>
        <div className="field grow">
          <label htmlFor="customer-search">Search</label>
          <input
            id="customer-search"
            type="search"
            placeholder="Customer ID, name, email or city"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="kyc">KYC status</label>
          <select id="kyc" value={kyc} onChange={(e) => update({ kyc_status: e.target.value })}>
            <option value="">All</option>
            <option>VERIFIED</option>
            <option>PENDING</option>
            <option>REVIEW</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="segment">Segment</label>
          <select id="segment" value={segment} onChange={(e) => update({ segment: e.target.value })}>
            <option value="">All</option>
            <option>Mass</option>
            <option>Affluent</option>
            <option>HNI</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="ordering">Sort by</label>
          <select id="ordering" value={ordering} onChange={(e) => update({ ordering: e.target.value })}>
            <option value="customer_id">Customer ID</option>
            <option value="name">Name</option>
            <option value="city">City</option>
            <option value="-aum">Portfolio value (high to low)</option>
            <option value="aum">Portfolio value (low to high)</option>
          </select>
        </div>
      </form>

      <section className="panel">
        <QueryBoundary query={query} label="Loading customers">
          {(data) =>
            data.count === 0 ? (
              <Empty title="No customers match these filters">Try a shorter search term or clear the filters.</Empty>
            ) : (
              <>
                <div className="table-wrap">
                  <table className="table">
                    <caption className="visually-hidden">Customers</caption>
                    <thead>
                      <tr>
                        <th scope="col">Customer</th>
                        <th scope="col">City</th>
                        <th scope="col">Segment</th>
                        <th scope="col">KYC</th>
                        <th scope="col">Risk</th>
                        <th scope="col" className="num">Accounts</th>
                        <th scope="col" className="num">Portfolio value</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.results.map((c) => (
                        <tr key={c.customer_id}>
                          <td>
                            <Link to={`/customers/${c.customer_id}`} className="strong">
                              {c.full_name}
                            </Link>
                            <div className="muted small">
                              {c.customer_id} · {c.email}
                            </div>
                          </td>
                          <td>
                            {c.city}, {c.state}
                          </td>
                          <td>{c.segment}</td>
                          <td>
                            <Badge value={c.kyc_status} />
                          </td>
                          <td>{c.risk_level ?? <span className="muted">Not assessed</span>}</td>
                          <td className="num">{c.account_count}</td>
                          <td className="num">{money(c.total_market_value)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  page={page}
                  pageSize={PAGE_SIZE}
                  count={data.count}
                  isFetching={query.isFetching}
                  onPageChange={(p) => update({ page: String(p) })}
                />
              </>
            )
          }
        </QueryBoundary>
      </section>
    </>
  );
}
