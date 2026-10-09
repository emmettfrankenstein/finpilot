import type { ReactNode } from 'react';

export function StatCard({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: ReactNode; tone?: string }) {
  return (
    <div className="stat-card">
      <dt className="stat-label">{label}</dt>
      <dd className={`stat-value ${tone ?? ''}`}>{value}</dd>
      {hint && <dd className="stat-hint muted">{hint}</dd>}
    </div>
  );
}
