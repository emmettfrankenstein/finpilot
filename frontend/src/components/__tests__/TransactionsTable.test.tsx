import { render, screen } from '@testing-library/react';

import type { Transaction } from '../../api/types';
import { TransactionsTable } from '../TransactionsTable';

const row = (id: string, status: Transaction['status']): Transaction => ({
  transaction_id: id,
  account_id: 'A00001',
  instrument_id: 'I0001',
  symbol: 'EQ001',
  instrument_name: 'Equity One',
  transaction_type: 'BUY',
  trade_date: '2026-09-01',
  quantity: '10.000000',
  price: '100.0000',
  amount: '1000.00',
  status,
});

it('visually distinguishes reversed and pending rows with text and styling', () => {
  render(<TransactionsTable rows={[row('T1', 'REVERSED'), row('T2', 'PENDING'), row('T3', 'SETTLED')]} />);
  const reversed = screen.getByText('T1').closest('tr')!;
  const pending = screen.getByText('T2').closest('tr')!;
  expect(reversed).toHaveClass('tx-reversed');
  expect(pending).toHaveClass('tx-pending');
  expect(screen.getByText('REVERSED')).toBeInTheDocument();
});
