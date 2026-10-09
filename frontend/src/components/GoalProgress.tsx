import type { Goal } from '../api/types';
import { date, money, percent } from '../lib/format';

export function GoalProgress({ goal }: { goal: Goal }) {
  const pct = Math.min(100, Number(goal.funded_pct));
  return (
    <div className="goal-progress">
      <div
        className="progress"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(pct)}
        aria-label={`${goal.goal_name} funded`}
      >
        <div className={`progress-bar ${goal.flags.includes('OVERDUE') ? 'danger' : ''}`} style={{ width: `${pct}%` }} />
      </div>
      <div className="small muted">
        {money(goal.current_funded_amount)} of {money(goal.target_amount)} · <strong>{percent(goal.funded_pct)}</strong> funded · target{' '}
        {date(goal.target_date)}
      </div>
    </div>
  );
}
