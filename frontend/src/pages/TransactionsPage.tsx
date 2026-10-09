import { useParams, useSearchParams } from 'react-router-dom';

import { useCustomer, useInstruments, useTransactions } from '../api/hooks';
import type { TransactionFilters } from '../api/hooks';
import { Empty, QueryBoundary } from '../components/DataState';
import { Pagination } from '../components/Pagination';
import { TransactionsTable } from '../components/TransactionsTable';

const PAGE_SIZE = 25;
const TYPES = ['BUY', 'SELL', 'DIVIDEND', 'FEE'];
const STATUSES = ['SETTLED', 'PENDING', 'REVERSED'];

function listParam(value: string | null): string[] {
  return value ? value.split(',').filter(Boolean) : [];
}

export function TransactionsPage() {
  const { customerId = '' } = useParams();
  const [params, setParams] = useSearchParams();
  const customer = useCustomer(customerId);
  const instruments = useInstruments();

  // URL is the single source of truth for filters, so views are shareable and back-button safe.
  const filters: TransactionFilters = {
    date_from: params.get('date_from') ?? undefined,
    date_to: params.get('date_to') ?? undefined,
    account: params.get('account') ?? undefined,
    instrument: params.get('instrument') ?? undefined,
    type: listParam(params.get('type')),
    status: listParam(params.get('status')),
    ordering: params.get('ordering') ?? '-trade_date',
    page: Number(params.get('page') ?? '1'),
    page_size: PAGE_SIZE,
  };
  const query = useTransactions(customerId, filters);

  function update(changes: Record<string, string | undefined>) {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(changes)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    if (!('page' in changes)) next.delete('page');
    setParams(next, { replace: true });
  }

  function toggleList(name: 'type' | 'status', value: string) {
    const current = new Set(filters[name]);
    if (current.has(value)) current.delete(value);
    else current.add(value);
    update({ [name]: [...current].join(',') });
  }

  const hasFilters = ['date_from', 'date_to', 'account', 'instrument', 'type', 'status'].some((k) => params.get(k));

  return (
    <section className="panel">
      <form className="filters" onSubmit={(e) => e.preventDefault()} aria-label="Transaction filters">
        <div className="field">
          <label htmlFor="date_from">From</label>
          <input id="date_from" type="date" value={filters.date_from ?? ''} onChange={(e) => update({ date_from: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor="date_to">To</label>
          <input id="date_to" type="date" value={filters.date_to ?? ''} onChange={(e) => update({ date_to: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor="account">Account</label>
          <select id="account" value={filters.account ?? ''} onChange={(e) => update({ account: e.target.value })}>
            <option value="">All accounts</option>
            {customer.data?.accounts.map((a) => (
              <option key={a.account_id} value={a.account_id}>
                {a.account_id}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="instrument">Instrument</label>
          <select id="instrument" value={filters.instrument ?? ''} onChange={(e) => update({ instrument: e.target.value })}>
            <option value="">All instruments</option>
            {instruments.data?.map((i) => (
              <option key={i.instrument_id} value={i.instrument_id}>
                {i.symbol} · {i.instrument_name}
              </option>
            ))}
          </select>
        </div>
        <fieldset className="field chips">
          <legend>Type</legend>
          {TYPES.map((t) => (
            <label key={t} className="chip">
              <input type="checkbox" checked={filters.type!.includes(t)} onChange={() => toggleList('type', t)} /> {t}
            </label>
          ))}
        </fieldset>
        <fieldset className="field chips">
          <legend>Status</legend>
          {STATUSES.map((s) => (
            <label key={s} className="chip">
              <input type="checkbox" checked={filters.status!.includes(s)} onChange={() => toggleList('status', s)} /> {s}
            </label>
          ))}
        </fieldset>
        <div className="field">
          <label htmlFor="tx-ordering">Sort</label>
          <select id="tx-ordering" value={filters.ordering} onChange={(e) => update({ ordering: e.target.value })}>
            <option value="-trade_date">Newest first</option>
            <option value="trade_date">Oldest first</option>
            <option value="-amount">Largest amount</option>
            <option value="amount">Smallest amount</option>
          </select>
        </div>
        {hasFilters && (
          <button type="button" className="button secondary" onClick={() => setParams({}, { replace: true })}>
            Clear filters
          </button>
        )}
      </form>

      <QueryBoundary query={query} label="Loading transactions">
        {(data) =>
          data.count === 0 ? (
            <Empty title="No transactions found">{hasFilters ? 'Adjust or clear the filters.' : 'This customer has no recorded activity.'}</Empty>
          ) : (
            <>
              <TransactionsTable rows={data.results} />
              <Pagination
                page={filters.page!}
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
  );
}
