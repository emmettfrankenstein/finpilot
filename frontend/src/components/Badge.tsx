const TONES: Record<string, string> = {
  VERIFIED: 'success',
  ACTIVE: 'success',
  SETTLED: 'success',
  COMPLETED: 'success',
  INSERTED: 'success',
  PENDING: 'warning',
  REVIEW: 'warning',
  DORMANT: 'warning',
  DUPLICATE: 'neutral',
  REVERSED: 'danger',
  CLOSED: 'neutral',
  FAILED: 'danger',
  REJECTED: 'danger',
  OVERDUE: 'danger',
  OVERFUNDED: 'warning',
  HIGH: 'danger',
  MEDIUM: 'warning',
  LOW: 'neutral',
};

export function Badge({ value, label }: { value: string; label?: string }) {
  return <span className={`badge badge-${TONES[value] ?? 'neutral'}`}>{label ?? value.replace(/_/g, ' ')}</span>;
}
