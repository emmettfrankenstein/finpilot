import type { Goal, GoalInput } from '../api/types';

export type GoalErrors = Partial<Record<keyof GoalInput | 'form', string>>;

export function validateGoal(values: GoalInput, today: string, existing?: Goal): GoalErrors {
  const errors: GoalErrors = {};
  const target = Number(values.target_amount);
  const funded = Number(values.current_funded_amount);
  if (!values.goal_name.trim()) errors.goal_name = 'Enter a goal name.';
  if (!values.target_amount || !Number.isFinite(target) || target <= 0) errors.target_amount = 'Target must be a positive amount.';
  if (values.current_funded_amount === '' || !Number.isFinite(funded) || funded < 0)
    errors.current_funded_amount = 'Funded amount must be zero or more.';
  else if (!errors.target_amount && funded > target) errors.current_funded_amount = 'Funded amount cannot exceed the target.';
  if (!values.target_date) errors.target_date = 'Choose a target date.';
  else if (values.target_date < today && values.target_date !== existing?.target_date)
    errors.target_date = 'Target date must be today or later.';
  return errors;
}
