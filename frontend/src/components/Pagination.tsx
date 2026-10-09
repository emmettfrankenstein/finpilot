interface Props {
  page: number;
  pageSize: number;
  count: number;
  onPageChange: (page: number) => void;
  isFetching?: boolean;
}

export function Pagination({ page, pageSize, count, onPageChange, isFetching }: Props) {
  const pages = Math.max(1, Math.ceil(count / pageSize));
  const from = count === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, count);
  return (
    <nav className="pagination" aria-label="Pagination">
      <span className="muted" aria-live="polite">
        {from}–{to} of {count.toLocaleString('en-IN')}
        {isFetching ? ' · updating…' : ''}
      </span>
      <div className="pagination-buttons">
        <button type="button" className="button secondary" onClick={() => onPageChange(page - 1)} disabled={page <= 1}>
          Previous
        </button>
        <span>
          Page {page} of {pages}
        </span>
        <button type="button" className="button secondary" onClick={() => onPageChange(page + 1)} disabled={page >= pages}>
          Next
        </button>
      </div>
    </nav>
  );
}
