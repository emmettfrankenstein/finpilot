"""Business path: CSV validation, staging, duplicate policy and transactional merge."""

from decimal import Decimal

import pytest

from apps.ingestion.models import BatchStatus, ImportBatch, RowOutcome, StagedRow
from apps.ingestion.services import DuplicateFileError, InvalidFileError, run_import
from apps.portfolio.models import HoldingSnapshot, Transaction

from .conftest import DATA_DIR, TODAY

HEADER = "transaction_id,account_id,instrument_id,transaction_type,trade_date,quantity,price,amount,status\n"


def _import(body: str, name="t.csv"):
    return run_import("transactions", (HEADER + body).encode(), file_name=name, today=TODAY)


def _rejections(batch):
    return {r.record_key: r.errors for r in batch.rows.filter(outcome=RowOutcome.REJECTED)}


@pytest.mark.django_db
class TestTransactionValidation:
    def test_rejects_each_supplied_anomaly_with_reason(self, small_dataset):
        batch = _import(
            "T0000101,A00001,I9999,BUY,2026-09-15,10,100,1000,SETTLED\n"
            "T0000102,A00001,I0001,FEE,2026-08-22,0,0,-75,SETTLED\n"
            "T0000103,A00001,I0001,BUY,2027-01-05,2,210,420,PENDING\n"
        )
        errors = _rejections(batch)
        assert errors["T0000101"] == ["instrument_id: 'I9999' does not exist"]
        assert errors["T0000102"] == ["amount: -75 must be >= 0"]
        assert errors["T0000103"] == ["trade_date: 2027-01-05 is in the future"]
        assert batch.inserted_rows == 0 and batch.rejected_rows == 3
        assert not Transaction.objects.filter(transaction_id__in=errors).exists()

    def test_reports_every_problem_on_a_row(self, small_dataset):
        batch = _import("T0000104,AXXXX,I0001,SWAP,2026-02-30,x,1,1,DONE\n")
        (errors,) = _rejections(batch).values()
        assert len(errors) == 5

    def test_amount_must_match_quantity_times_price(self, small_dataset):
        batch = _import("T0000105,A00001,I0001,BUY,2026-09-01,2,100,250,SETTLED\n")
        assert "does not equal quantity x price" in _rejections(batch)["T0000105"][0]

    def test_cash_events_must_have_zero_quantity(self, small_dataset):
        batch = _import("T0000106,A00001,I0001,DIVIDEND,2026-09-01,1,10,10,SETTLED\n")
        assert "cash event" in _rejections(batch)["T0000106"][0]

    def test_warns_but_loads_trade_before_account_opening(self, small_dataset):
        batch = _import("T0000107,A00001,I0001,BUY,2025-01-15,1,100,100,SETTLED\n")
        row = batch.rows.get()
        assert row.outcome == RowOutcome.INSERTED
        assert "precedes account opening" in row.warnings[0]


@pytest.mark.django_db
class TestDuplicatePolicy:
    def test_identical_duplicate_in_file_is_skipped(self, small_dataset):
        line = "T0000201,A00001,I0001,BUY,2026-09-01,1,100,100,SETTLED\n"
        batch = _import(line + line)
        assert (batch.inserted_rows, batch.duplicate_rows, batch.rejected_rows) == (1, 1, 0)

    def test_conflicting_duplicate_in_file_is_rejected(self, small_dataset):
        batch = _import(
            "T0000202,A00001,I0001,BUY,2026-09-01,1,100,100,SETTLED\n"
            "T0000202,A00001,I0001,BUY,2026-09-01,2,100,200,SETTLED\n"
        )
        assert (batch.inserted_rows, batch.rejected_rows) == (1, 1)
        assert Transaction.objects.get(pk="T0000202").quantity == 1

    def test_reimporting_existing_rows_is_idempotent(self, small_dataset):
        before = Transaction.objects.count()
        batch = _import("T0000001,A00001,I0001,BUY,2026-03-03,10,100.00,1000.00,SETTLED\n")
        assert batch.duplicate_rows == 1
        assert Transaction.objects.count() == before

    def test_existing_row_with_different_values_is_not_overwritten(self, small_dataset):
        batch = _import("T0000001,A00001,I0001,BUY,2026-03-03,11,100,1100,SETTLED\n")
        assert "not overwritten" in _rejections(batch)["T0000001"][0]
        assert Transaction.objects.get(pk="T0000001").quantity == Decimal("10")

    def test_same_file_twice_is_refused(self, small_dataset):
        body = "T0000301,A00001,I0001,BUY,2026-09-01,1,100,100,SETTLED\n"
        first = _import(body)
        with pytest.raises(DuplicateFileError) as exc:
            _import(body)
        assert exc.value.batch == first

    def test_duplicate_holdings_do_not_double_count(self, small_dataset):
        assert HoldingSnapshot.objects.filter(account_id="A00002").count() == 1
        batch = ImportBatch.objects.get(dataset="holdings_snapshot")
        assert batch.duplicate_rows == 1


@pytest.mark.django_db
class TestFileLevelFailures:
    def test_missing_columns(self, small_dataset):
        with pytest.raises(InvalidFileError, match="Missing required column"):
            run_import("transactions", b"transaction_id,account_id\nT1,A1\n", file_name="x.csv")
        assert not ImportBatch.objects.filter(file_name="x.csv").exists()

    def test_not_utf8(self, small_dataset):
        with pytest.raises(InvalidFileError, match="UTF-8"):
            run_import("transactions", b"\xff\xfe\x00bad", file_name="x.csv")

    def test_staged_rows_record_every_input_row(self, small_dataset):
        batch = _import(
            "T0000401,A00001,I0001,BUY,2026-09-01,1,100,100,SETTLED\n"
            "T0000402,A00001,I9999,BUY,2026-09-01,1,100,100,SETTLED\n"
        )
        assert batch.status == BatchStatus.COMPLETED
        assert StagedRow.objects.filter(batch=batch).count() == 2


@pytest.mark.django_db
def test_full_supplied_dataset_seed():
    """Loads the real supplied CSVs and checks every deliberate anomaly is handled."""
    from apps.ingestion.specs import SEED_ORDER

    results = {}
    for dataset in SEED_ORDER:
        content = (DATA_DIR / f"{dataset.value}.csv").read_bytes()
        results[dataset.value] = run_import(dataset.value, content, file_name="seed", today=TODAY)

    tx = results["transactions"]
    assert (tx.total_rows, tx.inserted_rows, tx.duplicate_rows, tx.rejected_rows) == (
        4554,
        4550,
        1,
        3,
    )
    holdings = results["holdings_snapshot"]
    assert (holdings.inserted_rows, holdings.duplicate_rows) == (982, 3)
    assert all(b.rejected_rows == 0 for name, b in results.items() if name != "transactions")
