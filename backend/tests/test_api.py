"""API path: auth, role checks, portfolio aggregation, transaction filters and goal writes."""

from decimal import Decimal

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


class TestAuth:
    def test_login_returns_access_token_and_httponly_refresh_cookie(self, client, viewer):
        res = client.post(
            reverse("login"), {"username": "viewer", "password": "viewer-pass-123"}, format="json"
        )
        assert res.status_code == 200
        assert res.data["user"]["role"] == "VIEWER"
        cookie = res.cookies["finpilot_refresh"]
        assert cookie["httponly"] and cookie["samesite"] == "Strict"
        assert cookie["path"] == "/api/v1/auth/"

    def test_refresh_uses_cookie(self, client, viewer):
        client.post(
            reverse("login"), {"username": "viewer", "password": "viewer-pass-123"}, format="json"
        )
        res = client.post(reverse("refresh"))
        assert res.status_code == 200 and res.data["access"]

    def test_bad_credentials(self, client, viewer):
        res = client.post(
            reverse("login"), {"username": "viewer", "password": "nope"}, format="json"
        )
        assert res.status_code == 401
        assert res.data["error"]["code"] == "invalid_credentials"

    def test_protected_endpoints_require_token(self, client, small_dataset):
        res = client.get(reverse("customer-list"))
        assert res.status_code == 401
        assert res.data["error"]["code"] == "not_authenticated"

    def test_health_is_public(self, client):
        res = client.get(reverse("health"))
        assert res.status_code == 200
        assert res.data["checks"]["database"] == "ok"
        assert "X-Request-ID" in res


class TestCustomers:
    def test_search_by_name_email_city_and_id(self, viewer_client, small_dataset):
        url = reverse("customer-list")
        for term in ("asha", "VIKRAM@", "chennai", "C0001"):
            assert viewer_client.get(url, {"search": term}).data["count"] == 1, term

    def test_list_includes_aum_and_latest_risk(self, viewer_client, small_dataset):
        res = viewer_client.get(reverse("customer-list"), {"ordering": "-aum"})
        first = res.data["results"][0]
        assert first["customer_id"] == "C0001"
        assert first["risk_level"] == "Growth"

    def test_profile_shows_latest_risk(self, viewer_client, small_dataset):
        res = viewer_client.get(reverse("customer-detail", args=["C0001"]))
        assert res.data["latest_risk_profile"]["assessed_at"] == "2026-07-01"
        assert len(res.data["accounts"]) == 2

    def test_customer_without_risk_profile(self, viewer_client, small_dataset):
        res = viewer_client.get(reverse("customer-detail", args=["C0002"]))
        assert res.data["latest_risk_profile"] is None

    def test_unknown_customer_is_404_envelope(self, viewer_client, small_dataset):
        res = viewer_client.get(reverse("customer-portfolio", args=["C9999"]))
        assert res.status_code == 404
        assert res.data["error"]["code"] == "not_found"


class TestPortfolio:
    def test_totals_allocation_and_positions(self, viewer_client, small_dataset):
        res = viewer_client.get(reverse("customer-portfolio", args=["C0001"]))
        assert res.status_code == 200
        data = res.data
        # A00001: 10 x 110 + 20 x 95.5 = 3010; A00002: 5 x 110 = 550 (duplicate row not counted)
        assert Decimal(data["totals"]["market_value"]) == Decimal("3560.00")
        assert Decimal(data["totals"]["cost_basis"]) == Decimal("3600.00")
        assert Decimal(data["totals"]["unrealised_pnl"]) == Decimal("-40.00")
        accounts = {a["account_id"]: Decimal(a["market_value"]) for a in data["accounts"]}
        assert accounts == {"A00001": Decimal("3010.00"), "A00002": Decimal("550.00")}
        allocation = {a["asset_class"]: a["weight_pct"] for a in data["allocation"]}
        assert allocation == {"EQUITY": "46.35", "BOND": "53.65"}
        assert data["as_of"] == {
            "snapshot_date": "2026-09-18",
            "price_date": "2026-09-18",
            "unpriced_positions": 0,
        }
        assert len(data["positions"]) == 3

    def test_customer_without_holdings_returns_zeroes(self, viewer_client, small_dataset):
        data = viewer_client.get(reverse("customer-portfolio", args=["C0002"])).data
        assert data["totals"]["market_value"] == "0.00"
        assert data["positions"] == [] and data["accounts"][0]["position_count"] == 0

    def test_portfolio_query_count_is_constant(
        self, viewer_client, small_dataset, django_assert_max_num_queries
    ):
        with django_assert_max_num_queries(6):
            viewer_client.get(reverse("customer-portfolio", args=["C0001"]))


class TestTransactions:
    def url(self, cid="C0001"):
        return reverse("customer-transactions", args=[cid])

    def test_paginated_and_sorted_newest_first(self, viewer_client, small_dataset):
        res = viewer_client.get(self.url(), {"page_size": 2})
        assert res.data["count"] == 5
        assert [r["transaction_id"] for r in res.data["results"]] == ["T0000005", "T0000004"]
        assert res.data["next"]

    def test_filters(self, viewer_client, small_dataset):
        get = lambda **p: viewer_client.get(self.url(), p).data["count"]  # noqa: E731
        assert get(account="A00002") == 2
        assert get(instrument="I0002") == 1
        assert get(type="BUY,DIVIDEND") == 4
        assert get(status="REVERSED") == 1
        assert get(date_from="2026-06-01", date_to="2026-07-31") == 2

    def test_invalid_filters_are_400(self, viewer_client, small_dataset):
        res = viewer_client.get(self.url(), {"date_from": "2026-09-01", "date_to": "2026-01-01"})
        assert res.status_code == 400
        assert "date_to" in res.data["error"]["details"]
        assert viewer_client.get(self.url(), {"type": "STEAL"}).status_code == 400

    def test_does_not_leak_other_customers(self, viewer_client, small_dataset):
        res = viewer_client.get(self.url(), {"account": "A00003"})
        assert res.data["count"] == 0


class TestGoals:
    def test_list_with_funded_pct_and_flags(self, viewer_client, small_dataset):
        res = viewer_client.get(reverse("customer-goals", args=["C0001"]))
        goals = {g["goal_id"]: g for g in res.data}
        assert goals["G00001"]["funded_pct"] == "25.00"
        assert goals["G00002"]["flags"] == ["OVERDUE"]

    def test_create_goal(self, viewer_client, small_dataset):
        payload = {
            "goal_type": "EDUCATION",
            "goal_name": "College",
            "target_amount": "500000",
            "current_funded_amount": "50000",
            "target_date": "2035-06-01",
            "priority": "HIGH",
        }
        res = viewer_client.post(reverse("customer-goals", args=["C0002"]), payload, format="json")
        assert res.status_code == 201
        assert res.data["goal_id"] == "G00003"
        assert res.data["funded_pct"] == "10.00"

    def test_create_validation_messages(self, viewer_client, small_dataset):
        payload = {
            "goal_type": "NOPE",
            "goal_name": " ",
            "target_amount": "-5",
            "target_date": "2001-01-01",
            "priority": "HIGH",
        }
        res = viewer_client.post(reverse("customer-goals", args=["C0002"]), payload, format="json")
        assert res.status_code == 400
        assert set(res.data["error"]["details"]) == {
            "goal_type",
            "goal_name",
            "target_amount",
            "target_date",
        }

    def test_patch_validates_against_existing_values(self, viewer_client, small_dataset):
        url = reverse("goal-detail", args=["G00001"])
        res = viewer_client.patch(url, {"current_funded_amount": "2000000"}, format="json")
        assert res.status_code == 400
        res = viewer_client.patch(url, {"current_funded_amount": "300000"}, format="json")
        assert res.status_code == 200 and res.data["funded_pct"] == "30.00"

    def test_put_not_allowed(self, viewer_client, small_dataset):
        res = viewer_client.put(reverse("goal-detail", args=["G00001"]), {}, format="json")
        assert res.status_code == 405


class TestAdminImport:
    CSV = (
        b"transaction_id,account_id,instrument_id,transaction_type,trade_date,quantity,price,"
        b"amount,status\nT0000901,A00001,I0001,BUY,2026-09-01,1,100,100,SETTLED\n"
        b"T0000902,A00001,I9999,BUY,2026-09-01,1,100,100,SETTLED\n"
    )

    def upload(self, api, content=CSV, name="tx.csv"):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return api.post(
            reverse("import-upload", args=["transactions"]),
            {"file": SimpleUploadedFile(name, content, "text/csv")},
            format="multipart",
        )

    def test_viewer_is_forbidden(self, viewer_client, small_dataset):
        assert self.upload(viewer_client).status_code == 403

    def test_admin_import_returns_counts_and_rejections(self, admin_client, small_dataset):
        res = self.upload(admin_client)
        assert res.status_code == 201
        assert (res.data["inserted_rows"], res.data["rejected_rows"]) == (1, 1)
        assert res.data["rejected"][0]["row_number"] == 2
        rows = admin_client.get(
            reverse("import-rows", args=[res.data["id"]]), {"outcome": "REJECTED"}
        )
        assert rows.data["count"] == 1

    def test_same_file_twice_is_409(self, admin_client, small_dataset):
        self.upload(admin_client)
        res = self.upload(admin_client)
        assert res.status_code == 409
        assert res.data["error"]["code"] == "conflict"

    def test_wrong_extension_and_bad_header_are_400(self, admin_client, small_dataset):
        assert self.upload(admin_client, name="tx.txt").status_code == 400
        res = self.upload(admin_client, content=b"a,b\n1,2\n")
        assert res.status_code == 400
        assert "Missing required column" in res.data["error"]["details"]["file"][0]
