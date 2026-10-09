from datetime import date
from pathlib import Path

import pytest
from rest_framework.test import APIClient

from apps.ingestion.services import run_import
from apps.users.models import Role, User

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
TODAY = date(2026, 10, 9)

CUSTOMERS = """customer_id,full_name,email,phone,city,state,date_of_birth,onboarded_at,kyc_status,segment
C0001,Asha Rao,asha@example.test,+919876543210,Pune,MH,1985-06-02,2025-01-12,VERIFIED,Affluent
C0002,Vikram Iyer,vikram@example.test,+919876543211,Chennai,TN,1979-02-11,2024-03-01,PENDING,Mass
"""
INSTRUMENTS = """instrument_id,symbol,instrument_name,asset_class,sector,exchange,currency,last_price,price_as_of,risk_band
I0001,EQ001,Equity One,EQUITY,Technology,NSE,INR,110.00,2026-09-18,HIGH
I0002,BD001,Bond One,BOND,,OTC,INR,95.50,2026-09-18,LOW
"""
ACCOUNTS = """account_id,customer_id,account_type,provider,opened_at,status,base_currency
A00001,C0001,BROKERAGE,NorthStar,2025-02-01,ACTIVE,INR
A00002,C0001,RETIREMENT,Harbor,2025-03-01,ACTIVE,INR
A00003,C0002,BROKERAGE,NorthStar,2024-04-01,ACTIVE,INR
"""
RISK = """customer_id,risk_score,risk_level,assessed_at,horizon_years,liquidity_need
C0001,62,Growth,2026-07-01,12,MEDIUM
C0001,40,Moderate,2025-07-01,12,MEDIUM
"""
HOLDINGS = """account_id,instrument_id,quantity,avg_cost,snapshot_date
A00001,I0001,10,100.00,2026-09-18
A00001,I0002,20,100.00,2026-09-18
A00002,I0001,5,120.00,2026-09-18
A00002,I0001,5,120.00,2026-09-18
"""
TRANSACTIONS = """transaction_id,account_id,instrument_id,transaction_type,trade_date,quantity,price,amount,status
T0000001,A00001,I0001,BUY,2026-03-03,10,100,1000,SETTLED
T0000002,A00001,I0002,BUY,2026-03-04,20,100,2000,SETTLED
T0000003,A00001,I0001,DIVIDEND,2026-06-01,0,0,15.5,SETTLED
T0000004,A00002,I0001,BUY,2026-07-01,5,120,600,PENDING
T0000005,A00002,I0001,SELL,2026-08-01,1,125,125,REVERSED
T0000006,A00003,I0002,BUY,2026-08-02,1,95,95,SETTLED
"""
GOALS = """goal_id,customer_id,goal_type,goal_name,target_amount,current_funded_amount,target_date,priority
G00001,C0001,RETIREMENT,Retire,1000000,250000,2040-01-01,HIGH
G00002,C0001,TRAVEL,Trip,100000,10000,2026-01-01,LOW
"""

FIXTURE_FILES = [
    ("customers", CUSTOMERS),
    ("instruments", INSTRUMENTS),
    ("accounts", ACCOUNTS),
    ("risk_profiles", RISK),
    ("holdings_snapshot", HOLDINGS),
    ("transactions", TRANSACTIONS),
    ("goals", GOALS),
]


@pytest.fixture
def small_dataset(db):
    for dataset, content in FIXTURE_FILES:
        run_import(
            dataset, content.encode(), file_name=f"{dataset}.csv", source="seed", today=TODAY
        )


@pytest.fixture
def viewer(db):
    return User.objects.create_user("viewer", password="viewer-pass-123", role=Role.VIEWER)


@pytest.fixture
def admin(db):
    return User.objects.create_user("admin", password="admin-pass-123", role=Role.ADMIN)


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def viewer_client(client, viewer):
    client.force_authenticate(viewer)
    return client


@pytest.fixture
def admin_client(admin):
    c = APIClient()
    c.force_authenticate(admin)
    return c
