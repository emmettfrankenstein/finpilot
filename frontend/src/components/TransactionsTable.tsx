import { memo } from 'react';

import type { Transaction } from '../api/types';
import { date, money, quantity } from '../lib/format';
import { Badge } from './Badge';

/** Memoised so paging/filter changes elsewhere on the page do not re-render unchanged rows. */
export const TransactionsTable = memo(function TransactionsTable({ rows }: { rows: Transaction[] }) {
  return (
    <div className="table-wrap">
      <table className="table">
        <caption className="visually-hidden">Transactions</caption>
        <thead>
          <tr>
            <th scope="col">Date</th>
            <th scope="col">Transaction</th>
            <th scope="col">Instrument</th>
            <th scope="col">Account</th>
            <th scope="col" className="num">Quantity</th>
            <th scope="col" className="num">Price</th>
            <th scope="col" className="num">Amount</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((t) => (
            <tr key={t.transaction_id} className={`tx-${t.status.toLowerCase()}`}>
              <td>{date(t.trade_date)}</td>
              <td>
                <strong>{t.transaction_type}</strong>
                <div className="muted small">{t.transaction_id}</div>
              </td>
              <td>
                {t.symbol}
                <div className="muted small">{t.instrument_name}</div>
              </td>
              <td>{t.account_id}</td>
              <td className="num">{Number(t.quantity) ? quantity(t.quantity) : '—'}</td>
              <td className="num">{Number(t.price) ? money(t.price) : '—'}</td>
              <td className="num amount">{money(t.amount)}</td>
              <td>
                <Badge value={t.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
});
