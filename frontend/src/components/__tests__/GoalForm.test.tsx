import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { ApiError } from '../../api/client';
import type { Goal } from '../../api/types';
import { validateGoal } from '../../lib/goalValidation';
import { GoalForm } from '../GoalForm';

const goal: Goal = {
  goal_id: 'G00001',
  customer_id: 'C0001',
  goal_type: 'RETIREMENT',
  goal_name: 'Retire early',
  target_amount: '1000000.00',
  current_funded_amount: '250000.00',
  funded_pct: '25.00',
  target_date: '2040-01-01',
  priority: 'HIGH',
  flags: [],
  updated_at: '2026-10-01T00:00:00Z',
};

describe('validateGoal', () => {
  const base = { goal_type: 'TRAVEL', goal_name: 'Trip', target_amount: '1000', current_funded_amount: '0', target_date: '2030-01-01', priority: 'LOW' } as const;

  it('accepts a valid goal', () => {
    expect(validateGoal({ ...base }, '2026-10-09')).toEqual({});
  });

  it('rejects funded above target and past dates', () => {
    const errors = validateGoal({ ...base, current_funded_amount: '2000', target_date: '2020-01-01' }, '2026-10-09');
    expect(errors.current_funded_amount).toMatch(/cannot exceed/);
    expect(errors.target_date).toMatch(/today or later/);
  });

  it('allows keeping an existing past target date when editing', () => {
    const old = { ...goal, target_date: '2020-01-01' };
    expect(validateGoal({ ...base, target_date: '2020-01-01' }, '2026-10-09', old).target_date).toBeUndefined();
  });
});

describe('<GoalForm />', () => {
  it('shows inline errors and does not submit an empty form', async () => {
    const onSubmit = vi.fn();
    render(<GoalForm onSubmit={onSubmit} onCancel={() => {}} />);
    await userEvent.click(screen.getByRole('button', { name: 'Create goal' }));
    expect(screen.getByText('Enter a goal name.')).toBeInTheDocument();
    expect(screen.getByLabelText('Goal name')).toHaveAttribute('aria-invalid', 'true');
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('sends only changed fields when editing', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<GoalForm goal={goal} onSubmit={onSubmit} onCancel={() => {}} />);
    const funded = screen.getByLabelText('Funded so far (₹)');
    await userEvent.clear(funded);
    await userEvent.type(funded, '300000');
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(onSubmit).toHaveBeenCalledWith({ current_funded_amount: '300000' });
  });

  it('maps server validation errors onto fields', async () => {
    const onSubmit = vi
      .fn()
      .mockRejectedValue(new ApiError(400, 'validation_error', 'invalid', { goal_name: ['Name already used.'] }));
    render(<GoalForm goal={goal} onSubmit={onSubmit} onCancel={() => {}} />);
    await userEvent.type(screen.getByLabelText('Goal name'), '!');
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(await screen.findByText('Name already used.')).toBeInTheDocument();
  });
});
