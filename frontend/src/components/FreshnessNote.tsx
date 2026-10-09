import type { Portfolio } from '../api/types';
import { date } from '../lib/format';

export function FreshnessNote({ asOf }: { asOf: Portfolio['as_of'] }) {
  return (
    <p className="freshness muted small">
      Holdings as of <strong>{date(asOf.snapshot_date)}</strong> · prices as of <strong>{date(asOf.price_date)}</strong>
      {asOf.unpriced_positions > 0 && (
        <span className="negative"> · {asOf.unpriced_positions} position(s) have no price and are excluded from totals</span>
      )}
    </p>
  );
}
