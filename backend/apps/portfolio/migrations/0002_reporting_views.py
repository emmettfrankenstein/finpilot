"""Reporting views used by the portfolio API and the reviewer SQL tasks.

Views (not materialised): the dataset is small and values must always reflect the latest
snapshot/prices. At larger scale v_position_valuation would become a materialised view
refreshed after each snapshot/price load.
"""

from django.db import migrations

LATEST_PRICE = """
CREATE VIEW v_latest_price AS
SELECT DISTINCT ON (instrument_id)
       instrument_id, price_date, close_price
FROM instrument_price
ORDER BY instrument_id, price_date DESC;
"""

POSITION_VALUATION = """
CREATE VIEW v_position_valuation AS
WITH latest_snapshot AS (
    SELECT account_id, MAX(snapshot_date) AS snapshot_date
    FROM holding_snapshot
    GROUP BY account_id
)
SELECT h.id                                         AS holding_id,
       h.account_id,
       a.customer_id,
       a.account_type,
       h.instrument_id,
       i.symbol,
       i.instrument_name,
       i.asset_class,
       h.snapshot_date,
       h.quantity,
       h.avg_cost,
       ROUND(h.quantity * h.avg_cost, 2)             AS cost_basis,
       p.close_price                                 AS last_price,
       p.price_date,
       ROUND(h.quantity * p.close_price, 2)          AS market_value,
       ROUND(h.quantity * (p.close_price - h.avg_cost), 2) AS unrealised_pnl
FROM holding_snapshot h
JOIN latest_snapshot ls
  ON ls.account_id = h.account_id AND ls.snapshot_date = h.snapshot_date
JOIN account a     ON a.account_id = h.account_id
JOIN instrument i  ON i.instrument_id = h.instrument_id
LEFT JOIN v_latest_price p ON p.instrument_id = h.instrument_id;
"""

MONTHLY_FLOWS = """
CREATE VIEW v_monthly_net_flows AS
SELECT a.customer_id,
       t.account_id,
       date_trunc('month', t.trade_date)::date                                  AS month,
       SUM(t.amount) FILTER (WHERE t.transaction_type = 'BUY')                  AS buy_amount,
       SUM(t.amount) FILTER (WHERE t.transaction_type = 'SELL')                 AS sell_amount,
       COALESCE(SUM(t.amount) FILTER (WHERE t.transaction_type = 'SELL'), 0)
     - COALESCE(SUM(t.amount) FILTER (WHERE t.transaction_type = 'BUY'), 0)     AS net_cash_flow,
       COUNT(*)                                                                 AS trade_count
FROM txn t
JOIN account a ON a.account_id = t.account_id
WHERE t.status = 'SETTLED' AND t.transaction_type IN ('BUY', 'SELL')
GROUP BY a.customer_id, t.account_id, date_trunc('month', t.trade_date);
"""


class Migration(migrations.Migration):
    dependencies = [("portfolio", "0001_initial")]

    operations = [
        migrations.RunSQL(LATEST_PRICE, "DROP VIEW IF EXISTS v_latest_price;"),
        migrations.RunSQL(POSITION_VALUATION, "DROP VIEW IF EXISTS v_position_valuation;"),
        migrations.RunSQL(MONTHLY_FLOWS, "DROP VIEW IF EXISTS v_monthly_net_flows;"),
        migrations.RunSQL(
            "CREATE SEQUENCE goal_number_seq START 1;", "DROP SEQUENCE IF EXISTS goal_number_seq;"
        ),
    ]
