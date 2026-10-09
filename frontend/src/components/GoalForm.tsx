import { useState, type FormEvent } from 'react';

import { ApiError } from '../api/client';
import { GOAL_TYPES, PRIORITIES, type Goal, type GoalInput } from '../api/types';
import { humanize } from '../lib/format';
import { validateGoal, type GoalErrors } from '../lib/goalValidation';

type Errors = GoalErrors;

const EMPTY: GoalInput = {
  goal_type: 'RETIREMENT',
  goal_name: '',
  target_amount: '',
  current_funded_amount: '0',
  target_date: '',
  priority: 'MEDIUM',
};

interface Props {
  goal?: Goal;
  onSubmit: (values: Partial<GoalInput>) => Promise<unknown>;
  onCancel: () => void;
}

export function GoalForm({ goal, onSubmit, onCancel }: Props) {
  const [values, setValues] = useState<GoalInput>(
    goal
      ? {
          goal_type: goal.goal_type,
          goal_name: goal.goal_name,
          target_amount: goal.target_amount,
          current_funded_amount: goal.current_funded_amount,
          target_date: goal.target_date,
          priority: goal.priority,
        }
      : EMPTY,
  );
  const [errors, setErrors] = useState<Errors>({});
  const [saving, setSaving] = useState(false);
  const idPrefix = goal ? `goal-${goal.goal_id}` : 'goal-new';

  function set<K extends keyof GoalInput>(key: K, value: GoalInput[K]) {
    setValues((v) => ({ ...v, [key]: value }));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const today = new Date().toISOString().slice(0, 10);
    const clientErrors = validateGoal(values, today, goal);
    setErrors(clientErrors);
    if (Object.keys(clientErrors).length) return;
    // PATCH sends only changed fields.
    const payload: Partial<GoalInput> = goal
      ? Object.fromEntries(Object.entries(values).filter(([k, v]) => goal[k as keyof GoalInput] !== v))
      : values;
    if (goal && Object.keys(payload).length === 0) return onCancel();
    setSaving(true);
    try {
      await onSubmit(payload);
    } catch (err) {
      if (err instanceof ApiError && err.details) {
        const fieldErrors: Errors = {};
        for (const key of Object.keys(err.details)) fieldErrors[key as keyof Errors] = err.fieldError(key);
        setErrors(Object.keys(fieldErrors).length ? fieldErrors : { form: err.message });
      } else setErrors({ form: err instanceof Error ? err.message : 'Could not save the goal.' });
    } finally {
      setSaving(false);
    }
  }

  function field(key: keyof GoalInput, label: string, input: React.ReactNode) {
    const errorId = `${idPrefix}-${key}-error`;
    return (
      <div className={`field ${errors[key] ? 'has-error' : ''}`}>
        <label htmlFor={`${idPrefix}-${key}`}>{label}</label>
        {input}
        {errors[key] && (
          <span id={errorId} className="field-error">
            {errors[key]}
          </span>
        )}
      </div>
    );
  }

  const aria = (key: keyof GoalInput) => ({
    id: `${idPrefix}-${key}`,
    'aria-invalid': Boolean(errors[key]),
    'aria-describedby': errors[key] ? `${idPrefix}-${key}-error` : undefined,
  });

  return (
    <form className="goal-form" onSubmit={submit} noValidate aria-label={goal ? `Edit ${goal.goal_name}` : 'New goal'}>
      {errors.form && (
        <p className="form-error" role="alert">
          {errors.form}
        </p>
      )}
      <div className="form-grid">
        {field('goal_name', 'Goal name', <input {...aria('goal_name')} value={values.goal_name} maxLength={120} onChange={(e) => set('goal_name', e.target.value)} />)}
        {field(
          'goal_type',
          'Goal type',
          <select {...aria('goal_type')} value={values.goal_type} onChange={(e) => set('goal_type', e.target.value as GoalInput['goal_type'])}>
            {GOAL_TYPES.map((t) => (
              <option key={t} value={t}>
                {humanize(t)}
              </option>
            ))}
          </select>,
        )}
        {field(
          'target_amount',
          'Target amount (₹)',
          <input {...aria('target_amount')} type="number" inputMode="decimal" min="1" step="0.01" value={values.target_amount} onChange={(e) => set('target_amount', e.target.value)} />,
        )}
        {field(
          'current_funded_amount',
          'Funded so far (₹)',
          <input
            {...aria('current_funded_amount')}
            type="number"
            inputMode="decimal"
            min="0"
            step="0.01"
            value={values.current_funded_amount}
            onChange={(e) => set('current_funded_amount', e.target.value)}
          />,
        )}
        {field('target_date', 'Target date', <input {...aria('target_date')} type="date" value={values.target_date} onChange={(e) => set('target_date', e.target.value)} />)}
        {field(
          'priority',
          'Priority',
          <select {...aria('priority')} value={values.priority} onChange={(e) => set('priority', e.target.value as GoalInput['priority'])}>
            {PRIORITIES.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>,
        )}
      </div>
      <div className="form-actions">
        <button type="submit" className="button" disabled={saving}>
          {saving ? 'Saving…' : goal ? 'Save changes' : 'Create goal'}
        </button>
        <button type="button" className="button secondary" onClick={onCancel} disabled={saving}>
          Cancel
        </button>
      </div>
    </form>
  );
}
