import { useState } from 'react';
import { useParams } from 'react-router-dom';

import { useGoals, useSaveGoal } from '../api/hooks';
import { Badge } from '../components/Badge';
import { Empty, QueryBoundary } from '../components/DataState';
import { GoalForm } from '../components/GoalForm';
import { GoalProgress } from '../components/GoalProgress';
import { humanize } from '../lib/format';

export function GoalsPage() {
  const { customerId = '' } = useParams();
  const goals = useGoals(customerId);
  const save = useSaveGoal(customerId);
  const [editing, setEditing] = useState<string | 'new' | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function submit(goalId: string | undefined, data: object) {
    const saved = await save.mutateAsync({ goalId, data });
    setEditing(null);
    setNotice(goalId ? `Saved changes to “${saved.goal_name}”.` : `Created goal “${saved.goal_name}”.`);
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Financial goals</h2>
        {editing !== 'new' && (
          <button
            type="button"
            className="button"
            onClick={() => {
              setNotice(null);
              setEditing('new');
            }}
          >
            Add goal
          </button>
        )}
      </div>
      <p className="visually-hidden" role="status">
        {notice}
      </p>
      {notice && <p className="notice">{notice}</p>}
      {editing === 'new' && (
        <div className="goal-card editing">
          <h3>New goal</h3>
          <GoalForm onSubmit={(data) => submit(undefined, data)} onCancel={() => setEditing(null)} />
        </div>
      )}
      <QueryBoundary query={goals} label="Loading goals">
        {(list) =>
          list.length === 0 ? (
            <Empty title="No goals yet">Add the customer’s first goal to start tracking progress.</Empty>
          ) : (
            <ul className="goal-list">
              {list.map((g) => (
                <li key={g.goal_id} className={`goal-card ${g.flags.length ? 'flagged' : ''}`}>
                  {editing === g.goal_id ? (
                    <GoalForm goal={g} onSubmit={(data) => submit(g.goal_id, data)} onCancel={() => setEditing(null)} />
                  ) : (
                    <>
                      <div className="goal-summary-head">
                        <div>
                          <h3>{g.goal_name}</h3>
                          <span className="muted small">
                            {g.goal_id} · {humanize(g.goal_type)}
                          </span>
                        </div>
                        <div className="badges">
                          {g.flags.map((f) => (
                            <Badge key={f} value={f} />
                          ))}
                          <Badge value={g.priority} label={`${g.priority} priority`} />
                          <button
                            type="button"
                            className="button secondary small"
                            onClick={() => {
                              setNotice(null);
                              setEditing(g.goal_id);
                            }}
                            aria-label={`Edit ${g.goal_name}`}
                          >
                            Edit
                          </button>
                        </div>
                      </div>
                      <GoalProgress goal={g} />
                      {g.flags.includes('OVERDUE') && <p className="small negative">Target date has passed before the goal was fully funded.</p>}
                      {g.flags.includes('OVERFUNDED') && <p className="small warning-text">Funded amount exceeds the target. Review the goal.</p>}
                    </>
                  )}
                </li>
              ))}
            </ul>
          )
        }
      </QueryBoundary>
    </section>
  );
}
