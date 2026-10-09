import { useRef, useState, type FormEvent } from 'react';

import { ApiError } from '../api/client';
import { useImportBatches, useImportRows, useUploadImport } from '../api/hooks';
import type { ImportBatch, ImportResult } from '../api/types';
import { Badge } from '../components/Badge';
import { Empty, QueryBoundary } from '../components/DataState';
import { Pagination } from '../components/Pagination';
import { StatCard } from '../components/StatCard';

const DATASETS = ['transactions', 'customers', 'accounts', 'instruments', 'risk_profiles', 'holdings_snapshot', 'goals'];

export function ImportPage() {
  const [dataset, setDataset] = useState('transactions');
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [selectedBatch, setSelectedBatch] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const upload = useUploadImport();
  const batches = useImportBatches();

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setResult(null);
    try {
      const res = await upload.mutateAsync({ dataset, file });
      setResult(res);
      setSelectedBatch(res.id);
      setFile(null);
      if (inputRef.current) inputRef.current.value = '';
    } catch {
      // Rendered from upload.error below.
    }
  }

  const uploadError = upload.error instanceof ApiError ? upload.error : null;

  return (
    <div className="stack">
      <h1>Data imports</h1>
      <section className="panel" aria-labelledby="upload-heading">
        <h2 id="upload-heading">Upload CSV</h2>
        <p className="muted small">
          Every row is validated and staged. Valid rows are merged in a single database transaction; rejected rows are kept with
          their reasons. Rows already loaded with identical values are skipped, and the same file cannot be applied twice.
        </p>
        <form className="filters" onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="dataset">Dataset</label>
            <select id="dataset" value={dataset} onChange={(e) => setDataset(e.target.value)}>
              {DATASETS.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </div>
          <div className="field grow">
            <label htmlFor="file">CSV file</label>
            <input
              ref={inputRef}
              id="file"
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => {
                upload.reset();
                setFile(e.target.files?.[0] ?? null);
              }}
              aria-describedby="file-hint"
            />
            <span id="file-hint" className="muted small">
              {file ? `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)` : 'UTF-8 CSV with a header row, up to 5 MB.'}
            </span>
          </div>
          <button type="submit" className="button" disabled={!file || upload.isPending}>
            {upload.isPending ? 'Validating and importing…' : 'Import file'}
          </button>
        </form>
        {upload.isPending && (
          <div className="progress indeterminate" role="progressbar" aria-label="Import in progress">
            <div className="progress-bar" />
          </div>
        )}
        {upload.error && (
          <div className="form-error" role="alert">
            <strong>{uploadError?.status === 409 ? 'Already imported. ' : 'Import failed. '}</strong>
            {uploadError?.fieldError('file') ?? uploadError?.message ?? 'Unexpected error.'}
          </div>
        )}
        {result && <ImportSummary batch={result} />}
      </section>

      <section className="panel" aria-labelledby="history-heading">
        <h2 id="history-heading">Recent imports</h2>
        <QueryBoundary query={batches} label="Loading import history">
          {(data) =>
            data.results.length === 0 ? (
              <Empty title="No imports yet" />
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th scope="col">Batch</th>
                      <th scope="col">Dataset</th>
                      <th scope="col">File</th>
                      <th scope="col">Status</th>
                      <th scope="col" className="num">Rows</th>
                      <th scope="col" className="num">Inserted</th>
                      <th scope="col" className="num">Duplicates</th>
                      <th scope="col" className="num">Rejected</th>
                      <th scope="col">
                        <span className="visually-hidden">Actions</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.results.map((b) => (
                      <tr key={b.id} aria-selected={selectedBatch === b.id}>
                        <td>#{b.id}</td>
                        <td>{b.dataset}</td>
                        <td>
                          {b.file_name}
                          <div className="muted small">
                            {b.source} · {b.created_by ?? 'system'} · {new Date(b.created_at).toLocaleString('en-IN')}
                          </div>
                        </td>
                        <td>
                          <Badge value={b.status} />
                        </td>
                        <td className="num">{b.total_rows}</td>
                        <td className="num">{b.inserted_rows}</td>
                        <td className="num">{b.duplicate_rows}</td>
                        <td className="num">{b.rejected_rows}</td>
                        <td>
                          <button type="button" className="button secondary small" onClick={() => setSelectedBatch(b.id)}>
                            View rows
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          }
        </QueryBoundary>
      </section>

      {selectedBatch !== null && <BatchRows batchId={selectedBatch} />}
    </div>
  );
}

function ImportSummary({ batch }: { batch: ImportBatch }) {
  return (
    <div className="import-summary" aria-live="polite">
      <h3>
        Batch #{batch.id}: {batch.file_name}
      </h3>
      <dl className="stat-grid">
        <StatCard label="Rows read" value={batch.total_rows} />
        <StatCard label="Imported" value={batch.inserted_rows} tone="positive" />
        <StatCard label="Duplicates skipped" value={batch.duplicate_rows} />
        <StatCard label="Rejected" value={batch.rejected_rows} tone={batch.rejected_rows ? 'negative' : ''} />
        <StatCard label="Imported with warnings" value={batch.warning_rows} />
      </dl>
    </div>
  );
}

function BatchRows({ batchId }: { batchId: number }) {
  const [outcome, setOutcome] = useState('REJECTED');
  const [page, setPage] = useState(1);
  const rows = useImportRows(batchId, outcome, page);
  return (
    <section className="panel" aria-labelledby="rows-heading">
      <div className="panel-head">
        <h2 id="rows-heading">Batch #{batchId} rows</h2>
        <div className="field inline">
          <label htmlFor="outcome">Outcome</label>
          <select
            id="outcome"
            value={outcome}
            onChange={(e) => {
              setOutcome(e.target.value);
              setPage(1);
            }}
          >
            <option value="REJECTED">Rejected</option>
            <option value="DUPLICATE">Duplicates</option>
            <option value="INSERTED">Inserted</option>
          </select>
        </div>
      </div>
      <QueryBoundary query={rows} label="Loading rows">
        {(data) =>
          data.count === 0 ? (
            <Empty title={`No ${outcome.toLowerCase()} rows in this batch`} />
          ) : (
            <>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th scope="col" className="num">Row</th>
                      <th scope="col">Key</th>
                      <th scope="col">Outcome</th>
                      <th scope="col">Reasons</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.results.map((r) => (
                      <tr key={r.row_number}>
                        <td className="num">{r.row_number}</td>
                        <td>{r.record_key || <span className="muted">—</span>}</td>
                        <td>
                          <Badge value={r.outcome} />
                        </td>
                        <td>
                          <ul className="reasons">
                            {r.errors.map((e) => (
                              <li key={e} className="negative">
                                {e}
                              </li>
                            ))}
                            {r.warnings.map((w) => (
                              <li key={w} className="muted">
                                {w}
                              </li>
                            ))}
                          </ul>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination page={page} pageSize={25} count={data.count} onPageChange={setPage} isFetching={rows.isFetching} />
            </>
          )
        }
      </QueryBoundary>
    </section>
  );
}
