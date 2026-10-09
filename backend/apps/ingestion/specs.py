"""Per-dataset validation and persistence rules.

A spec knows how to turn one raw CSV row into a cleaned record (or reasons for rejecting it),
how to identify the record (its natural key), how to look up records that already exist,
and how to write a batch of cleaned records. The generic pipeline in `services.py` handles
staging, duplicate detection and the transactional merge for every dataset the same way.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.db import connection

from apps.portfolio.models import (
    Account,
    AccountStatus,
    AccountType,
    AssetClass,
    Customer,
    Exchange,
    Goal,
    GoalType,
    HoldingSnapshot,
    Instrument,
    InstrumentPrice,
    KycStatus,
    Level,
    RiskLevel,
    RiskProfile,
    Segment,
    Transaction,
    TransactionStatus,
    TransactionType,
)

from . import parsing as p
from .models import Dataset, ImportBatch

CUSTOMER_ID = re.compile(r"^C\d{4,8}$")
ACCOUNT_ID = re.compile(r"^A\d{5,8}$")
INSTRUMENT_ID = re.compile(r"^I\d{4,8}$")
TRANSACTION_ID = re.compile(r"^T\d{7,10}$")
GOAL_ID = re.compile(r"^G\d{5,8}$")
PHONE = re.compile(r"^\+91[6-9]\d{9}$")
STATE = re.compile(r"^[A-Z]{2,3}$")
CURRENCY = re.compile(r"^[A-Z]{3}$")

AMOUNT_TOLERANCE = Decimal("0.01")

# Score bands implied by the supplied risk profiles.
RISK_BANDS = [
    (0, 34, "Conservative"),
    (35, 54, "Moderate"),
    (55, 74, "Growth"),
    (75, 100, "Aggressive"),
]


@dataclass
class Context:
    """Reference data a row is validated against, loaded once per batch."""

    today: date
    customers: set[str] = field(default_factory=set)
    accounts: dict[str, Account] = field(default_factory=dict)
    instruments: set[str] = field(default_factory=set)


class DatasetSpec:
    dataset: Dataset
    columns: list[str]
    model = None
    compare_fields: list[str]

    def load_context(self, ctx: Context) -> None:  # pragma: no cover - overridden as needed
        pass

    def key(self, cleaned: dict) -> str:
        return str(cleaned[self.model._meta.pk.attname])

    def raw_key(self, raw: dict) -> str:
        return (raw.get(self.columns[0]) or "").strip()[:64]

    def validate(self, raw: dict, ctx: Context) -> tuple[dict | None, p.RowErrors, list[str]]:
        raise NotImplementedError

    def comparable(self, record: dict) -> tuple:
        """Value tuple used to decide whether two versions of a record are identical."""
        return tuple(_norm(record[name]) for name in self.compare_fields)

    def fetch_existing(self, keys: list[str]) -> dict[str, tuple]:
        pk = self.model._meta.pk.attname
        rows = self.model.objects.filter(**{f"{pk}__in": keys}).values(pk, *self.compare_fields)
        return {str(row[pk]): self.comparable(row) for row in rows}

    def persist(self, records: list[dict], batch: ImportBatch) -> None:
        self.model.objects.bulk_create([self.model(**record) for record in records])

    def after_persist(self) -> None:
        pass


def _norm(value):
    """Normalise values so DB rows compare equal to freshly parsed CSV values (425.50 == 425.5)."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value.normalize()
    return str(value)


class CustomerSpec(DatasetSpec):
    dataset = Dataset.CUSTOMERS
    model = Customer
    columns = [
        "customer_id",
        "full_name",
        "email",
        "phone",
        "city",
        "state",
        "date_of_birth",
        "onboarded_at",
        "kyc_status",
        "segment",
    ]
    compare_fields = columns

    def validate(self, raw, ctx):
        e = p.RowErrors()
        r = {
            "customer_id": p.text(raw, "customer_id", e, max_length=10, pattern=CUSTOMER_ID),
            "full_name": p.text(raw, "full_name", e, max_length=120),
            "email": p.text(raw, "email", e, max_length=254, pattern=p.EMAIL_RE),
            "phone": p.text(raw, "phone", e, max_length=16, pattern=PHONE),
            "city": p.text(raw, "city", e, max_length=80),
            "state": p.text(raw, "state", e, max_length=3, pattern=STATE),
            "date_of_birth": p.iso_date(raw, "date_of_birth", e),
            "onboarded_at": p.iso_date(raw, "onboarded_at", e),
            "kyc_status": p.enum(raw, "kyc_status", e, KycStatus),
            "segment": p.enum(raw, "segment", e, Segment),
        }
        if r["email"]:
            r["email"] = r["email"].lower()
        if r["date_of_birth"] and r["onboarded_at"]:
            if r["date_of_birth"] >= r["onboarded_at"]:
                e.add("date_of_birth", "must be before onboarded_at")
            if r["onboarded_at"] > ctx.today:
                e.add("onboarded_at", "is in the future")
        return (None if e else r), e, []


class InstrumentSpec(DatasetSpec):
    """instruments.csv carries the security master *and* the latest price; the price is
    stored as a row in instrument_price so later price files can append history."""

    dataset = Dataset.INSTRUMENTS
    model = Instrument
    columns = [
        "instrument_id",
        "symbol",
        "instrument_name",
        "asset_class",
        "sector",
        "exchange",
        "currency",
        "last_price",
        "price_as_of",
        "risk_band",
    ]
    compare_fields = [
        "symbol",
        "instrument_name",
        "asset_class",
        "sector",
        "exchange",
        "currency",
        "risk_band",
    ]

    def validate(self, raw, ctx):
        e = p.RowErrors()
        r = {
            "instrument_id": p.text(raw, "instrument_id", e, max_length=10, pattern=INSTRUMENT_ID),
            "symbol": p.text(raw, "symbol", e, max_length=20),
            "instrument_name": p.text(raw, "instrument_name", e, max_length=120),
            "asset_class": p.enum(raw, "asset_class", e, AssetClass),
            "sector": p.text(raw, "sector", e, max_length=60, required=False),
            "exchange": p.enum(raw, "exchange", e, Exchange),
            "currency": p.text(raw, "currency", e, max_length=3, pattern=CURRENCY),
            "risk_band": p.enum(raw, "risk_band", e, Level),
            "last_price": p.decimal(raw, "last_price", e, places=4, gt=Decimal(0)),
            "price_as_of": p.iso_date(raw, "price_as_of", e),
        }
        if r["price_as_of"] and r["price_as_of"] > ctx.today:
            e.add("price_as_of", "is in the future")
        return (None if e else r), e, []

    def persist(self, records, batch):
        Instrument.objects.bulk_create(
            [
                Instrument(**{k: v for k, v in r.items() if k not in ("last_price", "price_as_of")})
                for r in records
            ]
        )
        InstrumentPrice.objects.bulk_create(
            [
                InstrumentPrice(
                    instrument_id=r["instrument_id"],
                    price_date=r["price_as_of"],
                    close_price=r["last_price"],
                )
                for r in records
            ]
        )


class AccountSpec(DatasetSpec):
    dataset = Dataset.ACCOUNTS
    model = Account
    columns = [
        "account_id",
        "customer_id",
        "account_type",
        "provider",
        "opened_at",
        "status",
        "base_currency",
    ]
    compare_fields = columns

    def load_context(self, ctx):
        ctx.customers = set(Customer.objects.values_list("customer_id", flat=True))

    def validate(self, raw, ctx):
        e = p.RowErrors()
        r = {
            "account_id": p.text(raw, "account_id", e, max_length=10, pattern=ACCOUNT_ID),
            "customer_id": p.text(raw, "customer_id", e, max_length=10),
            "account_type": p.enum(raw, "account_type", e, AccountType),
            "provider": p.text(raw, "provider", e, max_length=80),
            "opened_at": p.iso_date(raw, "opened_at", e),
            "status": p.enum(raw, "status", e, AccountStatus),
            "base_currency": p.text(raw, "base_currency", e, max_length=3, pattern=CURRENCY),
        }
        if r["customer_id"] and r["customer_id"] not in ctx.customers:
            e.add("customer_id", f"'{r['customer_id']}' does not exist")
        if r["opened_at"] and r["opened_at"] > ctx.today:
            e.add("opened_at", "is in the future")
        return (None if e else r), e, []


class RiskProfileSpec(DatasetSpec):
    dataset = Dataset.RISK_PROFILES
    model = RiskProfile
    columns = [
        "customer_id",
        "risk_score",
        "risk_level",
        "assessed_at",
        "horizon_years",
        "liquidity_need",
    ]
    compare_fields = ["risk_score", "risk_level", "horizon_years", "liquidity_need"]

    def load_context(self, ctx):
        ctx.customers = set(Customer.objects.values_list("customer_id", flat=True))

    def key(self, cleaned):
        return f"{cleaned['customer_id']}|{cleaned['assessed_at']}"

    def validate(self, raw, ctx):
        e = p.RowErrors()
        warnings: list[str] = []
        r = {
            "customer_id": p.text(raw, "customer_id", e, max_length=10),
            "risk_score": p.integer(raw, "risk_score", e, min_value=0, max_value=100),
            "risk_level": p.enum(raw, "risk_level", e, RiskLevel),
            "assessed_at": p.iso_date(raw, "assessed_at", e),
            "horizon_years": p.integer(raw, "horizon_years", e, min_value=0, max_value=60),
            "liquidity_need": p.enum(raw, "liquidity_need", e, Level),
        }
        if r["customer_id"] and r["customer_id"] not in ctx.customers:
            e.add("customer_id", f"'{r['customer_id']}' does not exist")
        if r["assessed_at"] and r["assessed_at"] > ctx.today:
            e.add("assessed_at", "is in the future")
        if r["risk_score"] is not None and r["risk_level"]:
            expected = next(lvl for lo, hi, lvl in RISK_BANDS if lo <= r["risk_score"] <= hi)
            if expected != r["risk_level"]:
                warnings.append(
                    f"risk_level {r['risk_level']} does not match score band {expected}"
                )
        return (None if e else r), e, warnings

    def fetch_existing(self, keys):
        customer_ids = {k.split("|")[0] for k in keys}
        rows = RiskProfile.objects.filter(customer_id__in=customer_ids).values(
            "customer_id", "assessed_at", *self.compare_fields
        )
        return {f"{row['customer_id']}|{row['assessed_at']}": self.comparable(row) for row in rows}


class HoldingSpec(DatasetSpec):
    dataset = Dataset.HOLDINGS
    model = HoldingSnapshot
    columns = ["account_id", "instrument_id", "quantity", "avg_cost", "snapshot_date"]
    compare_fields = ["quantity", "avg_cost"]

    def load_context(self, ctx):
        ctx.accounts = {a.account_id: a for a in Account.objects.only("account_id", "status")}
        ctx.instruments = set(Instrument.objects.values_list("instrument_id", flat=True))

    def key(self, cleaned):
        return f"{cleaned['account_id']}|{cleaned['instrument_id']}|{cleaned['snapshot_date']}"

    def raw_key(self, raw):
        return "|".join(
            (raw.get(c) or "").strip() for c in ("account_id", "instrument_id", "snapshot_date")
        )[:64]

    def validate(self, raw, ctx):
        e = p.RowErrors()
        warnings: list[str] = []
        r = {
            "account_id": p.text(raw, "account_id", e, max_length=10),
            "instrument_id": p.text(raw, "instrument_id", e, max_length=10),
            "quantity": p.decimal(raw, "quantity", e, places=6, gt=Decimal(0), max_digits=20),
            "avg_cost": p.decimal(raw, "avg_cost", e, places=4, min_value=Decimal(0)),
            "snapshot_date": p.iso_date(raw, "snapshot_date", e),
        }
        account = ctx.accounts.get(r["account_id"]) if r["account_id"] else None
        if r["account_id"] and account is None:
            e.add("account_id", f"'{r['account_id']}' does not exist")
        if r["instrument_id"] and r["instrument_id"] not in ctx.instruments:
            e.add("instrument_id", f"'{r['instrument_id']}' does not exist")
        if r["snapshot_date"] and r["snapshot_date"] > ctx.today:
            e.add("snapshot_date", "is in the future")
        if account is not None and account.status == AccountStatus.CLOSED:
            warnings.append("position held in a CLOSED account")
        return (None if e else r), e, warnings

    def fetch_existing(self, keys):
        accounts = {k.split("|")[0] for k in keys}
        dates = {k.split("|")[2] for k in keys}
        rows = HoldingSnapshot.objects.filter(
            account_id__in=accounts, snapshot_date__in=dates
        ).values("account_id", "instrument_id", "snapshot_date", *self.compare_fields)
        return {
            f"{row['account_id']}|{row['instrument_id']}|{row['snapshot_date']}": self.comparable(
                row
            )
            for row in rows
        }


class TransactionSpec(DatasetSpec):
    dataset = Dataset.TRANSACTIONS
    model = Transaction
    columns = [
        "transaction_id",
        "account_id",
        "instrument_id",
        "transaction_type",
        "trade_date",
        "quantity",
        "price",
        "amount",
        "status",
    ]
    compare_fields = columns[1:]

    def load_context(self, ctx):
        ctx.accounts = {
            a.account_id: a for a in Account.objects.only("account_id", "opened_at", "status")
        }
        ctx.instruments = set(Instrument.objects.values_list("instrument_id", flat=True))

    def validate(self, raw, ctx):
        e = p.RowErrors()
        warnings: list[str] = []
        r = {
            "transaction_id": p.text(
                raw, "transaction_id", e, max_length=12, pattern=TRANSACTION_ID
            ),
            "account_id": p.text(raw, "account_id", e, max_length=10),
            "instrument_id": p.text(raw, "instrument_id", e, max_length=10),
            "transaction_type": p.enum(raw, "transaction_type", e, TransactionType),
            "trade_date": p.iso_date(raw, "trade_date", e),
            "quantity": p.decimal(
                raw, "quantity", e, places=6, min_value=Decimal(0), max_digits=20
            ),
            "price": p.decimal(raw, "price", e, places=4, min_value=Decimal(0)),
            # Amount is always a positive magnitude; direction comes from transaction_type.
            "amount": p.decimal(raw, "amount", e, places=2, min_value=Decimal(0)),
            "status": p.enum(raw, "status", e, TransactionStatus),
        }
        account = ctx.accounts.get(r["account_id"]) if r["account_id"] else None
        if r["account_id"] and account is None:
            e.add("account_id", f"'{r['account_id']}' does not exist")
        if r["instrument_id"] and r["instrument_id"] not in ctx.instruments:
            e.add("instrument_id", f"'{r['instrument_id']}' does not exist")
        if r["trade_date"] and r["trade_date"] > ctx.today:
            e.add("trade_date", f"{r['trade_date']} is in the future")

        kind, qty, price, amount = r["transaction_type"], r["quantity"], r["price"], r["amount"]
        if kind in ("BUY", "SELL") and qty is not None and price is not None:
            if qty == 0 or price == 0:
                e.add("quantity", f"{kind} requires quantity > 0 and price > 0")
            elif amount is not None and abs(qty * price - amount) > AMOUNT_TOLERANCE:
                e.add("amount", f"{amount} does not equal quantity x price ({(qty * price):.2f})")
        if kind in ("DIVIDEND", "FEE") and qty is not None and price is not None:
            if qty != 0 or price != 0:
                e.add("quantity", f"{kind} is a cash event; quantity and price must be 0")
            if amount is not None and amount == 0:
                e.add("amount", f"{kind} amount must be > 0")

        if account is not None and r["trade_date"] and r["trade_date"] < account.opened_at:
            warnings.append(f"trade_date precedes account opening ({account.opened_at})")
        return (None if e else r), e, warnings

    def persist(self, records, batch):
        Transaction.objects.bulk_create([Transaction(import_batch=batch, **r) for r in records])


class GoalSpec(DatasetSpec):
    dataset = Dataset.GOALS
    model = Goal
    columns = [
        "goal_id",
        "customer_id",
        "goal_type",
        "goal_name",
        "target_amount",
        "current_funded_amount",
        "target_date",
        "priority",
    ]
    compare_fields = columns[1:]

    def load_context(self, ctx):
        ctx.customers = set(Customer.objects.values_list("customer_id", flat=True))

    def validate(self, raw, ctx):
        e = p.RowErrors()
        warnings: list[str] = []
        r = {
            "goal_id": p.text(raw, "goal_id", e, max_length=10, pattern=GOAL_ID),
            "customer_id": p.text(raw, "customer_id", e, max_length=10),
            "goal_type": p.enum(raw, "goal_type", e, GoalType),
            "goal_name": p.text(raw, "goal_name", e, max_length=120),
            "target_amount": p.decimal(raw, "target_amount", e, places=2, gt=Decimal(0)),
            "current_funded_amount": p.decimal(
                raw, "current_funded_amount", e, places=2, min_value=Decimal(0)
            ),
            "target_date": p.iso_date(raw, "target_date", e),
            "priority": p.enum(raw, "priority", e, Level),
        }
        if r["customer_id"] and r["customer_id"] not in ctx.customers:
            e.add("customer_id", f"'{r['customer_id']}' does not exist")
        # Inconsistent-but-plausible goals are loaded and flagged, not rejected: they are real
        # customer intent that the service team should see and correct.
        if r["target_amount"] and r["current_funded_amount"] is not None:
            if r["current_funded_amount"] > r["target_amount"]:
                warnings.append("current_funded_amount exceeds target_amount")
        if r["target_date"] and r["target_date"] < ctx.today:
            warnings.append("target_date is in the past")
        return (None if e else r), e, warnings

    def after_persist(self):
        # Keep the sequence for newly created goals ahead of imported ids.
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT setval('goal_number_seq', "
                "GREATEST(COALESCE(MAX(SUBSTRING(goal_id FROM 2)::int), 0), 1)) "
                "FROM goal WHERE goal_id ~ '^G[0-9]+$'"
            )


SPECS: dict[str, DatasetSpec] = {
    spec.dataset.value: spec
    for spec in (
        CustomerSpec(),
        InstrumentSpec(),
        AccountSpec(),
        RiskProfileSpec(),
        HoldingSpec(),
        TransactionSpec(),
        GoalSpec(),
    )
}

# Dependency order for seeding from a directory of CSV files.
SEED_ORDER = [
    Dataset.CUSTOMERS,
    Dataset.INSTRUMENTS,
    Dataset.ACCOUNTS,
    Dataset.RISK_PROFILES,
    Dataset.HOLDINGS,
    Dataset.TRANSACTIONS,
    Dataset.GOALS,
]
