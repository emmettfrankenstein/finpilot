import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { Pagination } from '../Pagination';

it('describes the visible range and disables bounds', async () => {
  const onPageChange = vi.fn();
  render(<Pagination page={1} pageSize={25} count={60} onPageChange={onPageChange} />);
  expect(screen.getByText(/1–25 of 60/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();
  await userEvent.click(screen.getByRole('button', { name: 'Next' }));
  expect(onPageChange).toHaveBeenCalledWith(2);
});
