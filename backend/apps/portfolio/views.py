import logging

from django.db.models import Count, DecimalField, F, OuterRef, Q, Subquery, Sum
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import (
    Customer,
    Goal,
    Instrument,
    KycStatus,
    PositionValuation,
    RiskProfile,
    Segment,
    Transaction,
)
from .serializers import (
    CustomerDetailSerializer,
    CustomerListSerializer,
    GoalSerializer,
    InstrumentSerializer,
    PortfolioSerializer,
    TransactionFilterSerializer,
    TransactionSerializer,
)

logger = logging.getLogger("finpilot.portfolio")

CUSTOMER_ORDERING = {
    "customer_id": "customer_id",
    "name": "full_name",
    "city": "city",
    "aum": "total_market_value",
}


@extend_schema(
    tags=["customers"],
    parameters=[
        OpenApiParameter("search", description="Matches customer ID, name, email or city"),
        OpenApiParameter("city", description="Exact city (case-insensitive)"),
        OpenApiParameter("kyc_status", enum=KycStatus.values),
        OpenApiParameter("segment", enum=Segment.values),
        OpenApiParameter(
            "ordering",
            enum=[*CUSTOMER_ORDERING, *(f"-{k}" for k in CUSTOMER_ORDERING)],
            default="customer_id",
        ),
    ],
)
class CustomerListView(generics.ListAPIView):
    """Search, filter and paginate customers."""

    serializer_class = CustomerListSerializer

    def get_queryset(self):
        params = self.request.query_params
        latest_risk = RiskProfile.objects.filter(customer=OuterRef("pk")).order_by("-assessed_at")
        aum = (
            PositionValuation.objects.filter(customer=OuterRef("pk"))
            .values("customer")
            .annotate(total=Sum("market_value"))
            .values("total")
        )
        qs = Customer.objects.annotate(
            risk_level=Subquery(latest_risk.values("risk_level")[:1]),
            account_count=Count("accounts", distinct=True),
            total_market_value=Subquery(
                aum, output_field=DecimalField(max_digits=24, decimal_places=2)
            ),
        )
        search = params.get("search", "").strip()[:100]
        if search:
            qs = qs.filter(
                Q(customer_id__iexact=search)
                | Q(full_name__icontains=search)
                | Q(email__icontains=search)
                | Q(city__icontains=search)
            )
        if city := params.get("city", "").strip():
            qs = qs.filter(city__iexact=city)
        if (kyc := params.get("kyc_status")) in KycStatus.values:
            qs = qs.filter(kyc_status=kyc)
        if (segment := params.get("segment")) in Segment.values:
            qs = qs.filter(segment=segment)

        ordering = params.get("ordering", "customer_id")
        field = CUSTOMER_ORDERING.get(ordering.lstrip("-"), "customer_id")
        expression = (
            F(field).desc(nulls_last=True)
            if ordering.startswith("-")
            else F(field).asc(nulls_last=True)
        )
        return qs.order_by(expression, "customer_id")


@extend_schema(tags=["customers"])
class CustomerDetailView(generics.RetrieveAPIView):
    """Customer profile with the latest risk profile and accounts."""

    serializer_class = CustomerDetailSerializer
    lookup_url_kwarg = "customer_id"
    queryset = services.customer_detail_queryset()


PORTFOLIO_EXAMPLE = {
    "customer_id": "C0002",
    "currency": "INR",
    "as_of": {"snapshot_date": "2026-09-18", "price_date": "2026-09-18", "unpriced_positions": 0},
    "totals": {
        "market_value": "412345.67",
        "cost_basis": "380000.00",
        "unrealised_pnl": "32345.67",
        "unrealised_pnl_pct": "8.51",
        "position_count": 7,
    },
    "accounts": [
        {
            "account_id": "A00002",
            "account_type": "BROKERAGE",
            "provider": "NorthStar Securities",
            "status": "ACTIVE",
            "snapshot_date": "2026-09-18",
            "market_value": "412345.67",
            "cost_basis": "380000.00",
            "unrealised_pnl": "32345.67",
            "unrealised_pnl_pct": "8.51",
            "position_count": 7,
        }
    ],
    "allocation": [
        {
            "asset_class": "EQUITY",
            "market_value": "250000.00",
            "weight_pct": "60.63",
            "position_count": 4,
        }
    ],
    "positions": [
        {
            "account_id": "A00002",
            "instrument_id": "I0046",
            "symbol": "MF014",
            "instrument_name": "FinPilot Mutual Fund 14",
            "asset_class": "MUTUAL_FUND",
            "quantity": "161.160000",
            "avg_cost": "133.1800",
            "last_price": "140.2500",
            "cost_basis": "21463.29",
            "market_value": "22602.69",
            "unrealised_pnl": "1139.40",
            "unrealised_pnl_pct": "5.31",
            "weight_pct": "5.48",
            "snapshot_date": "2026-09-18",
            "price_date": "2026-09-18",
        }
    ],
}


class CustomerPortfolioView(APIView):
    @extend_schema(
        tags=["portfolio"],
        parameters=[OpenApiParameter("account", description="Restrict to one account ID")],
        responses=PortfolioSerializer,
        examples=[OpenApiExample("Portfolio", value=PORTFOLIO_EXAMPLE, response_only=True)],
    )
    def get(self, request, customer_id: str):
        """Customer/account totals, asset allocation and positions (latest snapshot x price)."""
        customer = get_object_or_404(Customer, pk=customer_id)
        data = services.get_portfolio(customer, request.query_params.get("account") or None)
        return Response(PortfolioSerializer(data).data)


@extend_schema(
    tags=["transactions"],
    parameters=[
        OpenApiParameter("date_from", OpenApiTypes.DATE),
        OpenApiParameter("date_to", OpenApiTypes.DATE),
        OpenApiParameter("account"),
        OpenApiParameter("instrument"),
        OpenApiParameter("type", many=True, enum=["BUY", "SELL", "DIVIDEND", "FEE"]),
        OpenApiParameter("status", many=True, enum=["SETTLED", "PENDING", "REVERSED"]),
        OpenApiParameter(
            "ordering", enum=TransactionFilterSerializer.ORDERING, default="-trade_date"
        ),
    ],
)
class CustomerTransactionsView(generics.ListAPIView):
    """Server-side filtered, sorted and paginated transactions for one customer."""

    serializer_class = TransactionSerializer

    def get_queryset(self):
        customer_id = self.kwargs["customer_id"]
        get_object_or_404(Customer, pk=customer_id)
        params = self.request.query_params
        raw = {
            k: params.get(k)
            for k in ("date_from", "date_to", "account", "instrument", "ordering")
            if params.get(k)
        }
        for multi in ("type", "status"):
            values = [v for item in params.getlist(multi) for v in item.split(",") if v]
            if values:
                raw[multi] = values
        filters = TransactionFilterSerializer(data=raw)
        filters.is_valid(raise_exception=True)
        f = filters.validated_data

        qs = Transaction.objects.filter(account__customer_id=customer_id).select_related(
            "instrument"
        )
        if "date_from" in f:
            qs = qs.filter(trade_date__gte=f["date_from"])
        if "date_to" in f:
            qs = qs.filter(trade_date__lte=f["date_to"])
        if "account" in f:
            qs = qs.filter(account_id=f["account"])
        if "instrument" in f:
            qs = qs.filter(instrument_id=f["instrument"])
        if f.get("type"):
            qs = qs.filter(transaction_type__in=f["type"])
        if f.get("status"):
            qs = qs.filter(status__in=f["status"])
        tiebreak = "-transaction_id" if f["ordering"].startswith("-") else "transaction_id"
        return qs.order_by(f["ordering"], tiebreak)


@extend_schema(tags=["goals"])
class CustomerGoalsView(generics.ListCreateAPIView):
    """List a customer's goals with funded percentage and flags, or create a goal."""

    serializer_class = GoalSerializer
    pagination_class = None

    def get_customer(self) -> Customer:
        return get_object_or_404(Customer, pk=self.kwargs["customer_id"])

    def get_queryset(self):
        return Goal.objects.filter(customer=self.get_customer()).order_by("target_date", "goal_id")

    def create(self, request, *args, **kwargs):
        customer = self.get_customer()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        goal = services.create_goal(customer, serializer.validated_data)
        logger.info(
            "goal_created",
            extra={"goal_id": goal.pk, "customer_id": customer.pk, "user_id": request.user.pk},
        )
        return Response(self.get_serializer(goal).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["goals"])
class GoalDetailView(generics.RetrieveUpdateAPIView):
    """Read or partially update one goal (PATCH). PUT is not supported."""

    serializer_class = GoalSerializer
    queryset = Goal.objects.all()
    lookup_url_kwarg = "goal_id"
    http_method_names = ["get", "patch", "head", "options"]

    def partial_update(self, request, *args, **kwargs):
        goal = self.get_object()
        serializer = self.get_serializer(goal, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        goal = services.update_goal(goal.pk, serializer.validated_data)
        logger.info(
            "goal_updated",
            extra={
                "goal_id": goal.pk,
                "fields": sorted(serializer.validated_data),
                "user_id": request.user.pk,
            },
        )
        return Response(self.get_serializer(goal).data)


@extend_schema(tags=["reference"])
class InstrumentListView(generics.ListAPIView):
    """Security master (used for filter pickers)."""

    serializer_class = InstrumentSerializer
    queryset = Instrument.objects.order_by("symbol")
    pagination_class = None
