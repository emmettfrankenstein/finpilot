"""Core domain schema.

Natural identifiers from the source system (C0001, A00001, ...) are used as primary keys:
they are stable, short, already unique in clean data and are what users search for.
Every business rule that can be expressed declaratively is enforced by PostgreSQL with
CHECK / UNIQUE / FOREIGN KEY constraints, so bad data cannot enter through any path.
"""

from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.db.models import F, Q


class KycStatus(models.TextChoices):
    VERIFIED = "VERIFIED"
    PENDING = "PENDING"
    REVIEW = "REVIEW"


class Segment(models.TextChoices):
    MASS = "Mass"
    AFFLUENT = "Affluent"
    HNI = "HNI"


class AccountType(models.TextChoices):
    BROKERAGE = "BROKERAGE"
    MUTUAL_FUND = "MUTUAL_FUND"
    RETIREMENT = "RETIREMENT"


class AccountStatus(models.TextChoices):
    ACTIVE = "ACTIVE"
    DORMANT = "DORMANT"
    CLOSED = "CLOSED"


class AssetClass(models.TextChoices):
    EQUITY = "EQUITY"
    ETF = "ETF"
    MUTUAL_FUND = "MUTUAL_FUND"
    BOND = "BOND"
    REIT = "REIT"
    GSEC = "GSEC"


class Exchange(models.TextChoices):
    NSE = "NSE"
    BSE = "BSE"
    OTC = "OTC"


class Level(models.TextChoices):
    """Shared LOW/MEDIUM/HIGH scale (risk band, liquidity need, goal priority)."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RiskLevel(models.TextChoices):
    CONSERVATIVE = "Conservative"
    MODERATE = "Moderate"
    GROWTH = "Growth"
    AGGRESSIVE = "Aggressive"


class TransactionType(models.TextChoices):
    BUY = "BUY"
    SELL = "SELL"
    DIVIDEND = "DIVIDEND"
    FEE = "FEE"


class TransactionStatus(models.TextChoices):
    SETTLED = "SETTLED"
    PENDING = "PENDING"
    REVERSED = "REVERSED"


class GoalType(models.TextChoices):
    RETIREMENT = "RETIREMENT"
    EDUCATION = "EDUCATION"
    EMERGENCY_FUND = "EMERGENCY_FUND"
    HOME_PURCHASE = "HOME_PURCHASE"
    TRAVEL = "TRAVEL"
    WEALTH_CREATION = "WEALTH_CREATION"


def _in(field: str, choices) -> Q:
    return Q(**{f"{field}__in": choices.values})


class Customer(models.Model):
    customer_id = models.CharField(primary_key=True, max_length=10)
    full_name = models.CharField(max_length=120)
    email = models.EmailField(max_length=254, unique=True)
    phone = models.CharField(max_length=16)
    city = models.CharField(max_length=80)
    state = models.CharField(max_length=3)
    date_of_birth = models.DateField()
    onboarded_at = models.DateField()
    kyc_status = models.CharField(max_length=10, choices=KycStatus.choices)
    segment = models.CharField(max_length=10, choices=Segment.choices)

    class Meta:
        db_table = "customer"
        ordering = ["customer_id"]
        indexes = [
            # Trigram indexes make the case-insensitive "contains" search index-assisted.
            GinIndex(name="customer_name_trgm", fields=["full_name"], opclasses=["gin_trgm_ops"]),
            GinIndex(name="customer_email_trgm", fields=["email"], opclasses=["gin_trgm_ops"]),
            models.Index(fields=["city"], name="customer_city_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=_in("kyc_status", KycStatus), name="customer_kyc_valid"
            ),
            models.CheckConstraint(
                condition=_in("segment", Segment), name="customer_segment_valid"
            ),
            models.CheckConstraint(
                condition=Q(date_of_birth__lt=F("onboarded_at")), name="customer_dob_before_onboard"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.customer_id} {self.full_name}"


class RiskProfile(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="risk_profiles")
    risk_score = models.PositiveSmallIntegerField()
    risk_level = models.CharField(max_length=12, choices=RiskLevel.choices)
    assessed_at = models.DateField()
    horizon_years = models.PositiveSmallIntegerField()
    liquidity_need = models.CharField(max_length=6, choices=Level.choices)

    class Meta:
        db_table = "risk_profile"
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "assessed_at"], name="risk_profile_one_per_day"
            ),
            models.CheckConstraint(
                condition=Q(risk_score__gte=0, risk_score__lte=100), name="risk_score_range"
            ),
            models.CheckConstraint(condition=_in("risk_level", RiskLevel), name="risk_level_valid"),
            models.CheckConstraint(
                condition=_in("liquidity_need", Level), name="risk_liquidity_valid"
            ),
            models.CheckConstraint(condition=Q(horizon_years__lte=60), name="risk_horizon_range"),
        ]
        # "Latest profile per customer" is answered from the unique index above
        # (customer_id, assessed_at), which Postgres can scan backwards.


class Account(models.Model):
    account_id = models.CharField(primary_key=True, max_length=10)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="accounts")
    account_type = models.CharField(max_length=12, choices=AccountType.choices)
    provider = models.CharField(max_length=80)
    opened_at = models.DateField()
    status = models.CharField(max_length=8, choices=AccountStatus.choices)
    base_currency = models.CharField(max_length=3)

    class Meta:
        db_table = "account"
        ordering = ["account_id"]
        indexes = [models.Index(fields=["customer"], name="account_customer_idx")]
        constraints = [
            models.CheckConstraint(
                condition=_in("account_type", AccountType), name="account_type_valid"
            ),
            models.CheckConstraint(
                condition=_in("status", AccountStatus), name="account_status_valid"
            ),
            models.CheckConstraint(
                condition=Q(base_currency__regex=r"^[A-Z]{3}$"), name="account_currency_iso"
            ),
        ]


class Instrument(models.Model):
    instrument_id = models.CharField(primary_key=True, max_length=10)
    symbol = models.CharField(max_length=20, unique=True)
    instrument_name = models.CharField(max_length=120)
    asset_class = models.CharField(max_length=12, choices=AssetClass.choices)
    sector = models.CharField(max_length=60, null=True, blank=True)  # noqa: DJ001 - NULL = n/a
    exchange = models.CharField(max_length=3, choices=Exchange.choices)
    currency = models.CharField(max_length=3)
    risk_band = models.CharField(max_length=6, choices=Level.choices)

    class Meta:
        db_table = "instrument"
        ordering = ["instrument_id"]
        constraints = [
            models.CheckConstraint(
                condition=_in("asset_class", AssetClass), name="instrument_class_valid"
            ),
            models.CheckConstraint(
                condition=_in("exchange", Exchange), name="instrument_exchange_valid"
            ),
            models.CheckConstraint(condition=_in("risk_band", Level), name="instrument_risk_valid"),
            models.CheckConstraint(
                condition=Q(currency__regex=r"^[A-Z]{3}$"), name="instrument_currency_iso"
            ),
        ]


class InstrumentPrice(models.Model):
    """End-of-day price history. The supplied file carries one price per instrument, but keeping
    prices separate from the security master lets daily price loads append without updates."""

    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name="prices")
    price_date = models.DateField()
    close_price = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        db_table = "instrument_price"
        constraints = [
            models.UniqueConstraint(fields=["instrument", "price_date"], name="price_one_per_day"),
            models.CheckConstraint(condition=Q(close_price__gt=0), name="price_positive"),
        ]


class HoldingSnapshot(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="holdings")
    instrument = models.ForeignKey(Instrument, on_delete=models.PROTECT, related_name="holdings")
    snapshot_date = models.DateField()
    quantity = models.DecimalField(max_digits=20, decimal_places=6)
    avg_cost = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        db_table = "holding_snapshot"
        constraints = [
            # One position per account/instrument/day: the duplicate rows in the source file
            # cannot double-count market value.
            models.UniqueConstraint(
                fields=["account", "snapshot_date", "instrument"], name="holding_unique_position"
            ),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="holding_quantity_positive"),
            models.CheckConstraint(condition=Q(avg_cost__gte=0), name="holding_avg_cost_nonneg"),
        ]
        indexes = [models.Index(fields=["instrument"], name="holding_instrument_idx")]


class Transaction(models.Model):
    transaction_id = models.CharField(primary_key=True, max_length=12)
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="transactions")
    instrument = models.ForeignKey(
        Instrument, on_delete=models.PROTECT, related_name="transactions"
    )
    transaction_type = models.CharField(max_length=8, choices=TransactionType.choices)
    trade_date = models.DateField()
    quantity = models.DecimalField(max_digits=20, decimal_places=6)
    price = models.DecimalField(max_digits=18, decimal_places=4)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    status = models.CharField(max_length=8, choices=TransactionStatus.choices)
    import_batch = models.ForeignKey(
        "ingestion.ImportBatch", on_delete=models.SET_NULL, null=True, related_name="transactions"
    )

    class Meta:
        db_table = "txn"
        ordering = ["-trade_date", "-transaction_id"]
        indexes = [
            # Serves the listing: WHERE account_id IN (...) [AND date range] ORDER BY trade_date.
            models.Index(
                fields=["account", "-trade_date", "-transaction_id"], name="txn_account_date_idx"
            ),
            models.Index(fields=["instrument"], name="txn_instrument_idx"),
            # Monthly flow reporting scans by date across all accounts.
            models.Index(fields=["trade_date"], name="txn_trade_date_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=_in("transaction_type", TransactionType), name="txn_type_valid"
            ),
            models.CheckConstraint(
                condition=_in("status", TransactionStatus), name="txn_status_valid"
            ),
            models.CheckConstraint(condition=Q(amount__gte=0), name="txn_amount_nonneg"),
            models.CheckConstraint(
                condition=(
                    Q(transaction_type__in=["BUY", "SELL"], quantity__gt=0, price__gt=0)
                    | Q(transaction_type__in=["DIVIDEND", "FEE"], quantity=0, price=0)
                ),
                name="txn_shape_matches_type",
            ),
        ]


class Goal(models.Model):
    goal_id = models.CharField(primary_key=True, max_length=10)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="goals")
    goal_type = models.CharField(max_length=16, choices=GoalType.choices)
    goal_name = models.CharField(max_length=120)
    target_amount = models.DecimalField(max_digits=18, decimal_places=2)
    current_funded_amount = models.DecimalField(max_digits=18, decimal_places=2)
    target_date = models.DateField()
    priority = models.CharField(max_length=6, choices=Level.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "goal"
        ordering = ["target_date", "goal_id"]
        indexes = [models.Index(fields=["customer", "target_date"], name="goal_customer_idx")]
        constraints = [
            models.CheckConstraint(condition=_in("goal_type", GoalType), name="goal_type_valid"),
            models.CheckConstraint(condition=_in("priority", Level), name="goal_priority_valid"),
            models.CheckConstraint(condition=Q(target_amount__gt=0), name="goal_target_positive"),
            models.CheckConstraint(
                condition=Q(current_funded_amount__gte=0), name="goal_funded_nonneg"
            ),
        ]


class PositionValuation(models.Model):
    """Read-only model over the `v_position_valuation` SQL view (latest snapshot x latest price)."""

    holding_id = models.BigIntegerField(primary_key=True)
    account = models.ForeignKey(Account, on_delete=models.DO_NOTHING, related_name="+")
    customer = models.ForeignKey(Customer, on_delete=models.DO_NOTHING, related_name="+")
    instrument = models.ForeignKey(Instrument, on_delete=models.DO_NOTHING, related_name="+")
    account_type = models.CharField(max_length=12)
    symbol = models.CharField(max_length=20)
    instrument_name = models.CharField(max_length=120)
    asset_class = models.CharField(max_length=12)
    snapshot_date = models.DateField()
    quantity = models.DecimalField(max_digits=20, decimal_places=6)
    avg_cost = models.DecimalField(max_digits=18, decimal_places=4)
    cost_basis = models.DecimalField(max_digits=24, decimal_places=2)
    last_price = models.DecimalField(max_digits=18, decimal_places=4, null=True)
    price_date = models.DateField(null=True)
    market_value = models.DecimalField(max_digits=24, decimal_places=2, null=True)
    unrealised_pnl = models.DecimalField(max_digits=24, decimal_places=2, null=True)

    class Meta:
        managed = False
        db_table = "v_position_valuation"
