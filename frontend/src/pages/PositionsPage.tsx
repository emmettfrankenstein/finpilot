import { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';

import { usePortfolio } from '../api/hooks';
import type { Position } from '../api/types';
import { Empty, QueryBoundary } from '../components/DataState';
import { FreshnessNote } from '../components/FreshnessNote';
import { humanize, money, percent, quantity, signClass } from '../lib/format';

type SortKey = 'symbol' | 'market_value' | 'unrealised_pnl' | 'weight_pct';

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: 'symbol', label: 'Instrument' },
  { key: 'market_value', label: 'Market value' },
  { key: 'unrealised_pnl', label: 'Unrealised P/L' },
  { key: 'weight_pct', label: 'Weight' },
];

function sortPositions(rows: Position[], key: SortKey, desc: boolean) {
  const sorted = [...rows].sort((a, b) =>
    key === 'symbol' ? a.symbol.localeCompare(b.symbol) : Number(a[key] ?? 0) - Number(b[key] ?? 0),
  );
  return desc ? sorted.reverse() : sorted;
}

export function PositionsPage() {
  const { customerId = '' } = useParams();
  const query = usePortfolio(customerId);
  const [account, setAccount] = useState('');
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: 'market_value', desc: true });

  const rows = useMemo(() => {
    const positions = query.data?.positions ?? [];
    return sortPositions(account ? positions.filter((p) => p.account_id === account) : positions, sort.key, sort.desc);
  }, [query.data, account, sort]);

  function toggle(key: SortKey) {
    setSort((s) => ({ key, desc: s.key === key ? !s.desc : key !== 'symbol' }));
  }

  function header(key: SortKey, label: string, numeric: boolean) {
    const active = sort.key === key;
    return (
      <th scope="col" className={numeric ? 'num' : ''} aria-sort={active ? (sort.desc ? 'descending' : 'ascending') : 'none'}>
        <button type="button" className="sort-button" onClick={() => toggle(key)}>
          {label}
          <span aria-hidden="true">{active ? (sort.desc ? ' ▼' : ' ▲') : ''}</span>
        </button>
      </th>
    );
  }

  return (
    <QueryBoundary query={query} label="Loading positions">
      {(p) => (
        <section className="panel">
          <div className="panel-head">
            <FreshnessNote asOf={p.as_of} />
            <div className="field inline">
              <label htmlFor="pos-account">Account</label>
              <select id="pos-account" value={account} onChange={(e) => setAccount(e.target.value)}>
                <option value="">All accounts</option>
                {p.accounts.map((a) => (
                  <option key={a.account_id} value={a.account_id}>
                    {a.account_id} · {humanize(a.account_type)}
                  </option>
                ))}
              </select>
            </div>
          </div>
          {rows.length === 0 ? (
            <Empty title="No positions in the latest snapshot" />
          ) : (
            <div className="table-wrap">
              <table className="table">
                <caption className="visually-hidden">Positions, sorted by {COLUMNS.find((c) => c.key === sort.key)?.label}</caption>
                <thead>
                  <tr>
                    {header('symbol', 'Instrument', false)}
                    <th scope="col">Account</th>
                    <th scope="col" className="num">Quantity</th>
                    <th scope="col" className="num">Avg cost</th>
                    <th scope="col" className="num">Latest price</th>
                    {header('market_value', 'Market value', true)}
                    {header('unrealised_pnl', 'Unrealised P/L', true)}
                    {header('weight_pct', 'Weight', true)}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={`${r.account_id}-${r.instrument_id}`}>
                      <td>
                        <strong>{r.symbol}</strong>
                        <div className="muted small">
                          {r.instrument_name} · {humanize(r.asset_class)}
                        </div>
                      </td>
                      <td>{r.account_id}</td>
                      <td className="num">{quantity(r.quantity)}</td>
                      <td className="num">{money(r.avg_cost)}</td>
                      <td className="num">{money(r.last_price)}</td>
                      <td className="num">{money(r.market_value)}</td>
                      <td className={`num ${signClass(r.unrealised_pnl)}`}>
                        {money(r.unrealised_pnl)}
                        <div className="small">{percent(r.unrealised_pnl_pct, true)}</div>
                      </td>
                      <td className="num">{percent(r.weight_pct)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </QueryBoundary>
  );
}
