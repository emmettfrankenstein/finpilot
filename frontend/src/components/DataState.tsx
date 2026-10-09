import type { ReactNode } from 'react';

import { ApiError } from '../api/client';

export function Loading({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="state" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <span>{label}…</span>
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const apiError = error instanceof ApiError ? error : null;
  const message =
    apiError?.status === 404
      ? 'We could not find that record.'
      : (apiError?.message ?? 'Something went wrong while loading this data.');
  return (
    <div className="state state-error" role="alert">
      <p>{message}</p>
      {apiError?.requestId && <p className="muted small">Reference: {apiError.requestId}</p>}
      {onRetry && apiError?.status !== 404 && (
        <button type="button" className="button secondary" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="state state-empty">
      <p className="state-title">{title}</p>
      {children && <div className="muted">{children}</div>}
    </div>
  );
}

interface QueryLike<T> {
  data: T | undefined;
  error: unknown;
  isPending: boolean;
  refetch: () => unknown;
}

/** Renders loading/error states for a query and hands successful data to children. */
export function QueryBoundary<T>({
  query,
  label,
  children,
}: {
  query: QueryLike<T>;
  label?: string;
  children: (data: T) => ReactNode;
}) {
  if (query.isPending) return <Loading label={label} />;
  if (query.error || query.data === undefined) return <ErrorState error={query.error} onRetry={() => query.refetch()} />;
  return <>{children(query.data)}</>;
}
