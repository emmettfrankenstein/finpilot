from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from .models import (
    Account,
    Customer,
    Goal,
    Instrument,
    RiskProfile,
    Transaction,
    TransactionStatus,
    TransactionType,
)

MONEY = {"max_digits": 18, "decimal_places": 2}


class RiskProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskProfile
        fields = ["risk_score", "risk_level", "assessed_at", "horizon_years", "liquidity_need"]


class CustomerListSerializer(serializers.ModelSerializer):
    risk_level = serializers.CharField(read_only=True, allow_null=True)
    account_count = serializers.IntegerField(read_only=True)
    total_market_value = serializers.DecimalField(read_only=True, allow_null=True, **MONEY)

    class Meta:
        model = Customer
        fields = [
            "customer_id",
            "full_name",
            "email",
            "city",
            "state",
            "kyc_status",
            "segment",
            "risk_level",
            "account_count",
            "total_market_value",
        ]


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ["account_id", "account_type", "provider", "opened_at", "status", "base_currency"]


class CustomerDetailSerializer(serializers.ModelSerializer):
    latest_risk_profile = serializers.SerializerMethodField()
    accounts = AccountSerializer(many=True, read_only=True)

    class Meta:
        model = Customer
        fields = [
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
            "latest_risk_profile",
            "accounts",
        ]

    def get_latest_risk_profile(self, obj) -> RiskProfileSerializer(allow_null=True):  # type: ignore[valid-type]
        profiles = getattr(obj, "latest_profiles", None)
        profile = profiles[0] if profiles else None
        return RiskProfileSerializer(profile).data if profile else None


class InstrumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Instrument
        fields = [
            "instrument_id",
            "symbol",
            "instrument_name",
            "asset_class",
            "sector",
            "exchange",
            "risk_band",
        ]


# ---- Portfolio (response-only shapes, documented for OpenAPI) ---------------------------------


class PositionSerializer(serializers.Serializer):
    account_id = serializers.CharField()
    instrument_id = serializers.CharField()
    symbol = serializers.CharField()
    instrument_name = serializers.CharField()
    asset_class = serializers.CharField()
    quantity = serializers.DecimalField(max_digits=20, decimal_places=6)
    avg_cost = serializers.DecimalField(max_digits=18, decimal_places=4)
    last_price = serializers.DecimalField(max_digits=18, decimal_places=4, allow_null=True)
    cost_basis = serializers.DecimalField(**MONEY)
    market_value = serializers.DecimalField(allow_null=True, **MONEY)
    unrealised_pnl = serializers.DecimalField(allow_null=True, **MONEY)
    unrealised_pnl_pct = serializers.DecimalField(max_digits=9, decimal_places=2, allow_null=True)
    weight_pct = serializers.DecimalField(max_digits=7, decimal_places=2, allow_null=True)
    snapshot_date = serializers.DateField()
    price_date = serializers.DateField(allow_null=True)


class TotalsSerializer(serializers.Serializer):
    market_value = serializers.DecimalField(**MONEY)
    cost_basis = serializers.DecimalField(**MONEY)
    unrealised_pnl = serializers.DecimalField(**MONEY)
    unrealised_pnl_pct = serializers.DecimalField(max_digits=9, decimal_places=2, allow_null=True)
    position_count = serializers.IntegerField()


class AccountTotalsSerializer(TotalsSerializer):
    account_id = serializers.CharField()
    account_type = serializers.CharField()
    provider = serializers.CharField()
    status = serializers.CharField()
    snapshot_date = serializers.DateField(allow_null=True)


class AllocationSerializer(serializers.Serializer):
    asset_class = serializers.CharField()
    market_value = serializers.DecimalField(**MONEY)
    weight_pct = serializers.DecimalField(max_digits=7, decimal_places=2)
    position_count = serializers.IntegerField()


class DataFreshnessSerializer(serializers.Serializer):
    snapshot_date = serializers.DateField(allow_null=True)
    price_date = serializers.DateField(allow_null=True)
    unpriced_positions = serializers.IntegerField()


class PortfolioSerializer(serializers.Serializer):
    customer_id = serializers.CharField()
    currency = serializers.CharField()
    as_of = DataFreshnessSerializer()
    totals = TotalsSerializer()
    accounts = AccountTotalsSerializer(many=True)
    allocation = AllocationSerializer(many=True)
    positions = PositionSerializer(many=True)


# ---- Transactions ---------------------------------------------------------------------------


class TransactionSerializer(serializers.ModelSerializer):
    symbol = serializers.CharField(source="instrument.symbol", read_only=True)
    instrument_name = serializers.CharField(source="instrument.instrument_name", read_only=True)

    class Meta:
        model = Transaction
        fields = [
            "transaction_id",
            "account_id",
            "instrument_id",
            "symbol",
            "instrument_name",
            "transaction_type",
            "trade_date",
            "quantity",
            "price",
            "amount",
            "status",
        ]


class TransactionFilterSerializer(serializers.Serializer):
    """Validates query parameters so bad filters return 400 instead of being ignored."""

    ORDERING = ["trade_date", "-trade_date", "amount", "-amount"]

    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    account = serializers.CharField(required=False, max_length=10)
    instrument = serializers.CharField(required=False, max_length=10)
    type = serializers.MultipleChoiceField(choices=TransactionType.choices, required=False)
    status = serializers.MultipleChoiceField(choices=TransactionStatus.choices, required=False)
    ordering = serializers.ChoiceField(choices=ORDERING, required=False, default="-trade_date")

    def validate(self, attrs):
        if (
            attrs.get("date_from")
            and attrs.get("date_to")
            and attrs["date_from"] > attrs["date_to"]
        ):
            raise serializers.ValidationError({"date_to": ["must be on or after date_from"]})
        return attrs


# ---- Goals ----------------------------------------------------------------------------------


def goal_flags(goal: Goal, today=None) -> list[str]:
    today = today or timezone.localdate()
    flags = []
    if goal.current_funded_amount > goal.target_amount:
        flags.append("OVERFUNDED")
    if goal.target_date < today and goal.current_funded_amount < goal.target_amount:
        flags.append("OVERDUE")
    return flags


class GoalSerializer(serializers.ModelSerializer):
    funded_pct = serializers.SerializerMethodField()
    flags = serializers.SerializerMethodField()
    target_amount = serializers.DecimalField(min_value=Decimal("1"), **MONEY)
    current_funded_amount = serializers.DecimalField(
        min_value=Decimal("0"), required=False, default=Decimal("0"), **MONEY
    )
    goal_name = serializers.CharField(max_length=120, trim_whitespace=True)

    class Meta:
        model = Goal
        fields = [
            "goal_id",
            "customer_id",
            "goal_type",
            "goal_name",
            "target_amount",
            "current_funded_amount",
            "funded_pct",
            "target_date",
            "priority",
            "flags",
            "updated_at",
        ]
        read_only_fields = ["goal_id", "customer_id", "updated_at"]

    def get_funded_pct(self, obj) -> str:
        """current_funded_amount / target_amount as a percentage string, e.g. "19.47"."""
        return str((obj.current_funded_amount / obj.target_amount * 100).quantize(Decimal("0.01")))

    def get_flags(self, obj) -> list[str]:
        return goal_flags(obj)

    def validate_goal_name(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Goal name cannot be blank.")
        return value

    def validate_target_date(self, value):
        today = timezone.localdate()
        unchanged = self.instance is not None and self.instance.target_date == value
        if value < today and not unchanged:
            raise serializers.ValidationError("Target date must be today or later.")
        if value.year > today.year + 60:
            raise serializers.ValidationError("Target date must be within 60 years.")
        return value

    def validate(self, attrs):
        target = attrs.get("target_amount", getattr(self.instance, "target_amount", None))
        funded = attrs.get(
            "current_funded_amount", getattr(self.instance, "current_funded_amount", None)
        )
        if target is not None and funded is not None and funded > target:
            raise serializers.ValidationError(
                {"current_funded_amount": ["Funded amount cannot exceed the target amount."]}
            )
        return attrs
