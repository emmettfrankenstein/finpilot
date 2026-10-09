"""Generic CSV import pipeline: parse -> validate -> stage -> merge (one DB transaction).

Duplicate policy (explicit, never a silent overwrite):
* The same file (by SHA-256) can be applied once per dataset; a re-upload is refused with 409.
* A row whose key already exists with *identical* values is a DUPLICATE: skipped, so
  overlapping files are idempotent.
* A row whose key already exists with *different* values is REJECTED as a conflict. Changing
  an existing record needs an explicit correction workflow, not a re-import.
* Within one file the first occurrence of a key wins; later identical copies are DUPLICATE,
  later conflicting copies are REJECTED.
"""

import csv
import hashlib
import io
import logging
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import BatchStatus, ImportBatch, RowOutcome, StagedRow
from .specs import SPECS, Context, DatasetSpec

logger = logging.getLogger("finpilot.import")


class ImportFailure(Exception):
    """Base class for whole-file failures (distinct from row-level rejections)."""


class InvalidFileError(ImportFailure):
    pass


class DuplicateFileError(ImportFailure):
    def __init__(self, batch: ImportBatch):
        super().__init__(f"This file was already imported as batch {batch.pk}.")
        self.batch = batch


@dataclass
class _Row:
    number: int
    raw: dict
    key: str
    cleaned: dict | None
    errors: list[str]
    warnings: list[str]
    outcome: str = RowOutcome.REJECTED


def _decode(content: bytes) -> tuple[csv.DictReader, list[dict]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InvalidFileError("File is not valid UTF-8 text.") from exc
    reader = csv.DictReader(io.StringIO(text, newline=""))
    return reader, list(reader)


def run_import(
    dataset: str,
    content: bytes,
    *,
    file_name: str,
    user=None,
    source: str = "api",
    today=None,
) -> ImportBatch:
    spec: DatasetSpec = SPECS[dataset]
    digest = hashlib.sha256(content).hexdigest()

    previous = ImportBatch.objects.filter(
        dataset=dataset, file_sha256=digest, status=BatchStatus.COMPLETED
    ).first()
    if previous:
        raise DuplicateFileError(previous)

    reader, raw_rows = _decode(content)
    header = [h.strip() for h in (reader.fieldnames or [])]
    missing = [c for c in spec.columns if c not in header]
    if missing:
        raise InvalidFileError(f"Missing required column(s): {', '.join(missing)}")
    if not raw_rows:
        raise InvalidFileError("File contains a header but no data rows.")

    # The batch row is committed on its own so the audit trail survives a failed merge.
    batch = ImportBatch.objects.create(
        dataset=dataset,
        source=source,
        file_name=file_name[:255],
        file_sha256=digest,
        created_by=user if getattr(user, "is_authenticated", False) else None,
        total_rows=len(raw_rows),
    )
    log_ctx = {"batch_id": batch.pk, "dataset": dataset, "source": source}
    logger.info("import_started", extra={**log_ctx, "rows": len(raw_rows)})

    try:
        rows = _validate(spec, raw_rows, today or timezone.localdate())
        with transaction.atomic():
            # Lock out concurrent loads of the same dataset so duplicate checks stay valid.
            ImportBatch.objects.select_for_update().filter(pk=batch.pk).get()
            _classify_against_database(spec, rows)
            valid = [r.cleaned for r in rows if r.outcome == RowOutcome.INSERTED]
            StagedRow.objects.bulk_create(
                [
                    StagedRow(
                        batch=batch,
                        row_number=r.number,
                        record_key=r.key[:64],
                        raw=r.raw,
                        outcome=r.outcome,
                        errors=r.errors,
                        warnings=r.warnings,
                    )
                    for r in rows
                ],
                batch_size=1000,
            )
            spec.persist(valid, batch)
            spec.after_persist()
            batch.inserted_rows = len(valid)
            batch.duplicate_rows = sum(r.outcome == RowOutcome.DUPLICATE for r in rows)
            batch.rejected_rows = sum(r.outcome == RowOutcome.REJECTED for r in rows)
            batch.warning_rows = sum(bool(r.warnings) for r in rows)
            batch.status = BatchStatus.COMPLETED
            batch.finished_at = timezone.now()
            batch.save()
    except IntegrityError as exc:
        # A constraint caught something validation missed: nothing was merged.
        logger.exception("import_failed", extra=log_ctx)
        _fail(
            batch, f"Database rejected the batch; no rows were imported ({exc.__class__.__name__})."
        )
        raise InvalidFileError(batch.error_message) from exc
    except Exception:
        logger.exception("import_failed", extra=log_ctx)
        _fail(batch, "Unexpected error; no rows were imported.")
        raise

    logger.info(
        "import_completed",
        extra={
            **log_ctx,
            "inserted": batch.inserted_rows,
            "duplicates": batch.duplicate_rows,
            "rejected": batch.rejected_rows,
            "warnings": batch.warning_rows,
        },
    )
    return batch


def _fail(batch: ImportBatch, message: str) -> None:
    ImportBatch.objects.filter(pk=batch.pk).update(
        status=BatchStatus.FAILED, error_message=message, finished_at=timezone.now()
    )
    batch.refresh_from_db()


def _validate(spec: DatasetSpec, raw_rows: list[dict], today) -> list[_Row]:
    ctx = Context(today=today)
    spec.load_context(ctx)
    first_seen: dict[str, tuple] = {}
    rows: list[_Row] = []
    for number, raw in enumerate(raw_rows, start=1):
        too_many_columns = None in raw
        raw = {k.strip(): (v if v is not None else "") for k, v in raw.items() if k is not None}
        if too_many_columns:
            rows.append(_Row(number, raw, spec.raw_key(raw), None, ["row: too many columns"], []))
            continue
        cleaned, errors, warnings = spec.validate(raw, ctx)
        key = spec.key(cleaned) if cleaned else spec.raw_key(raw)
        row = _Row(number, raw, key, cleaned, list(errors), warnings)
        if cleaned is not None:
            signature = spec.comparable(cleaned)
            if key in first_seen:
                if first_seen[key] == signature:
                    row.outcome = RowOutcome.DUPLICATE
                    row.warnings = [*warnings, f"exact duplicate of an earlier row for key {key}"]
                else:
                    row.errors = [f"key {key} appears earlier in the file with different values"]
            else:
                first_seen[key] = signature
                row.outcome = RowOutcome.INSERTED
        rows.append(row)
    return rows


def _classify_against_database(spec: DatasetSpec, rows: list[_Row]) -> None:
    candidates = [r for r in rows if r.outcome == RowOutcome.INSERTED]
    existing = spec.fetch_existing([r.key for r in candidates]) if candidates else {}
    for row in candidates:
        if row.key not in existing:
            continue
        if existing[row.key] == spec.comparable(row.cleaned):
            row.outcome = RowOutcome.DUPLICATE
            row.warnings = [*row.warnings, "already loaded with identical values; skipped"]
        else:
            row.outcome = RowOutcome.REJECTED
            row.errors = [f"key {row.key} already exists with different values; not overwritten"]
