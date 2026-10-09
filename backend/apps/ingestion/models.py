"""Import audit trail and staging area.

Every CSV load (seed or admin upload) creates an ImportBatch. Each source row is written to
StagedRow with its raw values, the validation outcome and row-level reasons, *before* valid
rows are merged into the final tables. Rejected rows therefore stay queryable (quarantine)
instead of disappearing into a log file.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q


class Dataset(models.TextChoices):
    CUSTOMERS = "customers"
    RISK_PROFILES = "risk_profiles"
    ACCOUNTS = "accounts"
    INSTRUMENTS = "instruments"
    HOLDINGS = "holdings_snapshot"
    TRANSACTIONS = "transactions"
    GOALS = "goals"


class BatchStatus(models.TextChoices):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RowOutcome(models.TextChoices):
    INSERTED = "INSERTED"
    DUPLICATE = "DUPLICATE"  # identical to a row already loaded: skipped, idempotent
    REJECTED = "REJECTED"  # quarantined with reasons; never merged


class ImportBatch(models.Model):
    dataset = models.CharField(max_length=20, choices=Dataset.choices)
    source = models.CharField(max_length=10, default="api")  # "api" upload or "seed" command
    file_name = models.CharField(max_length=255)
    file_sha256 = models.CharField(max_length=64)
    status = models.CharField(
        max_length=10, choices=BatchStatus.choices, default=BatchStatus.PROCESSING
    )
    total_rows = models.PositiveIntegerField(default=0)
    inserted_rows = models.PositiveIntegerField(default=0)
    duplicate_rows = models.PositiveIntegerField(default=0)
    rejected_rows = models.PositiveIntegerField(default=0)
    warning_rows = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "import_batch"
        ordering = ["-created_at"]
        constraints = [
            # The same file can only be successfully applied once per dataset.
            models.UniqueConstraint(
                fields=["dataset", "file_sha256"],
                condition=Q(status="COMPLETED"),
                name="import_batch_file_once",
            ),
            models.CheckConstraint(
                condition=Q(status__in=BatchStatus.values), name="import_batch_status_valid"
            ),
        ]


class StagedRow(models.Model):
    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name="rows")
    row_number = models.PositiveIntegerField(help_text="1-based data row number (header excluded)")
    record_key = models.CharField(max_length=64, blank=True, default="")
    raw = models.JSONField()
    outcome = models.CharField(max_length=10, choices=RowOutcome.choices)
    errors = models.JSONField(default=list, blank=True)
    warnings = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "import_staged_row"
        ordering = ["batch_id", "row_number"]
        constraints = [
            models.UniqueConstraint(fields=["batch", "row_number"], name="staged_row_unique"),
            models.CheckConstraint(
                condition=Q(outcome__in=RowOutcome.values), name="staged_row_outcome_valid"
            ),
        ]
        indexes = [
            models.Index(
                fields=["batch", "outcome"],
                name="staged_row_exceptions_idx",
                condition=~Q(outcome="INSERTED"),
            )
        ]
