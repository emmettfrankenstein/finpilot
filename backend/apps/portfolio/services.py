"""Portfolio read model and goal write path.

All aggregation runs in PostgreSQL over the `v_position_valuation` view: one grouped query
for account totals, one for asset allocation and one for the position rows, independent of
the number of accounts or positions (no N+1).
"""

from decimal import Decimal

from django.db import connection, transaction
from django.db.models import Count, Max, Min, Prefetch, Q, Sum

from .models import Account, Customer, Goal, PositionValuation, RiskProfile

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


def _pct(part: Decimal | None, whole: Decimal | None) -> Decimal | None:
    if part is None or not whole:
        return None
    return (part / whole * 100).quantize(CENT)


def customer_detail_queryset():
    return Customer.objects.prefetch_related(
        "accounts",
        Prefetch(
            "risk_profiles",
            queryset=RiskProfile.objects.order_by("-assessed_at"),
            to_attr="latest_profiles",
        ),
    )


def get_portfolio(customer: Customer, account_id: str | None = None) -> dict:
    positions_qs = PositionValuation.objects.filter(customer_id=customer.pk)
    if account_id:
        positions_qs = positions_qs.filter(account_id=account_id)

    sums = {
        "market_value": Sum("market_value"),
        "cost_basis": Sum("cost_basis"),
        "unrealised_pnl": Sum("unrealised_pnl"),
        "position_count": Count("holding_id"),
    }
    totals = positions_qs.aggregate(
        **sums,
        latest_snapshot=Max("snapshot_date"),
        oldest_price=Min("price_date"),
        unpriced=Count("holding_id", filter=Q(last_price__isnull=True)),
    )
    total_mv = totals["market_value"] or ZERO

    by_account = {
        row["account_id"]: row
        for row in positions_qs.values("account_id").annotate(
            **sums, latest_snapshot=Max("snapshot_date")
        )
    }
    accounts = Account.objects.filter(customer=customer).order_by("account_id")
    if account_id:
        accounts = accounts.filter(account_id=account_id)
    account_rows = []
    for account in accounts:
        agg = by_account.get(account.account_id, {})
        account_rows.append(
            {
                "account_id": account.account_id,
                "account_type": account.account_type,
                "provider": account.provider,
                "status": account.status,
                "snapshot_date": agg.get("latest_snapshot"),
                "market_value": agg.get("market_value") or ZERO,
                "cost_basis": agg.get("cost_basis") or ZERO,
                "unrealised_pnl": agg.get("unrealised_pnl") or ZERO,
                "unrealised_pnl_pct": _pct(agg.get("unrealised_pnl"), agg.get("cost_basis")),
                "position_count": agg.get("position_count", 0),
            }
        )

    allocation = [
        {
            "asset_class": row["asset_class"],
            "market_value": row["market_value"] or ZERO,
            "weight_pct": _pct(row["market_value"], total_mv) or ZERO,
            "position_count": row["position_count"],
        }
        for row in positions_qs.values("asset_class")
        .annotate(market_value=Sum("market_value"), position_count=Count("holding_id"))
        .order_by("-market_value")
    ]

    positions = [
        {
            **row,
            "unrealised_pnl_pct": _pct(row["unrealised_pnl"], row["cost_basis"]),
            "weight_pct": _pct(row["market_value"], total_mv),
        }
        for row in positions_qs.order_by("-market_value", "symbol").values(
            "account_id",
            "instrument_id",
            "symbol",
            "instrument_name",
            "asset_class",
            "quantity",
            "avg_cost",
            "last_price",
            "cost_basis",
            "market_value",
            "unrealised_pnl",
            "snapshot_date",
            "price_date",
        )
    ]

    return {
        "customer_id": customer.pk,
        "currency": "INR",
        "as_of": {
            "snapshot_date": totals["latest_snapshot"],
            # Report the *oldest* price used so staleness is never hidden behind a newer one.
            "price_date": totals["oldest_price"],
            "unpriced_positions": totals["unpriced"],
        },
        "totals": {
            "market_value": total_mv,
            "cost_basis": totals["cost_basis"] or ZERO,
            "unrealised_pnl": totals["unrealised_pnl"] or ZERO,
            "unrealised_pnl_pct": _pct(totals["unrealised_pnl"], totals["cost_basis"]),
            "position_count": totals["position_count"],
        },
        "accounts": account_rows,
        "allocation": allocation,
        "positions": positions,
    }


def _next_goal_id() -> str:
    with connection.cursor() as cursor:
        cursor.execute("SELECT nextval('goal_number_seq')")
        (number,) = cursor.fetchone()
    return f"G{number:05d}"


@transaction.atomic
def create_goal(customer: Customer, data: dict) -> Goal:
    return Goal.objects.create(goal_id=_next_goal_id(), customer=customer, **data)


@transaction.atomic
def update_goal(goal_id: str, data: dict) -> Goal:
    # Row lock serialises concurrent edits of the same goal.
    goal = Goal.objects.select_for_update().get(pk=goal_id)
    for field, value in data.items():
        setattr(goal, field, value)
    goal.save()
    return goal
