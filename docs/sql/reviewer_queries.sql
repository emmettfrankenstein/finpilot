-- FinPilot: reviewer SQL tasks (assignment section 6.1).
-- Run with: psql "$DATABASE_URL" -f docs/sql/reviewer_queries.sql
-- All valuation queries go through v_position_valuation (latest snapshot per account x latest price).

-- 1. Top 10 customers by current snapshot AUM
SELECT c.customer_id, c.full_name, c.segment,
       SUM(v.market_value) AS aum
FROM v_position_valuation v
JOIN customer c ON c.customer_id = v.customer_id
GROUP BY c.customer_id, c.full_name, c.segment
ORDER BY aum DESC
LIMIT 10;

-- 2a. Asset-class allocation for one customer
SELECT asset_class,
       SUM(market_value) AS market_value,
       ROUND(100 * SUM(market_value) / SUM(SUM(market_value)) OVER (), 2) AS weight_pct
FROM v_position_valuation
WHERE customer_id = 'C0026'
GROUP BY asset_class
ORDER BY market_value DESC;

-- 2b. Asset-class allocation for the whole dataset
SELECT asset_class,
       COUNT(*) AS positions,
       SUM(market_value) AS market_value,
       ROUND(100 * SUM(market_value) / SUM(SUM(market_value)) OVER (), 2) AS weight_pct
FROM v_position_valuation
GROUP BY asset_class
ORDER BY market_value DESC;

-- 3. Monthly BUY/SELL net cash flow for the last 12 months (settled trades only).
--    Net cash flow = SELL proceeds - BUY spend; generate_series keeps empty months visible.
WITH months AS (
    SELECT generate_series(date_trunc('month', CURRENT_DATE) - INTERVAL '11 months',
                           date_trunc('month', CURRENT_DATE), INTERVAL '1 month')::date AS month
)
SELECT m.month,
       COALESCE(SUM(f.buy_amount), 0)    AS buy_amount,
       COALESCE(SUM(f.sell_amount), 0)   AS sell_amount,
       COALESCE(SUM(f.net_cash_flow), 0) AS net_cash_flow
FROM months m
LEFT JOIN v_monthly_net_flows f ON f.month = m.month
GROUP BY m.month
ORDER BY m.month;

-- 4. Top instruments by number of distinct holders (customers) in the latest snapshot
SELECT v.instrument_id, v.symbol, v.instrument_name, v.asset_class,
       COUNT(DISTINCT v.customer_id) AS holders,
       SUM(v.market_value)           AS total_market_value
FROM v_position_valuation v
GROUP BY v.instrument_id, v.symbol, v.instrument_name, v.asset_class
ORDER BY holders DESC, total_market_value DESC
LIMIT 10;

-- 5. Customers with HIGH-priority goals below 25% funded
SELECT c.customer_id, c.full_name, g.goal_id, g.goal_name, g.goal_type,
       g.target_amount, g.current_funded_amount,
       ROUND(100 * g.current_funded_amount / g.target_amount, 2) AS funded_pct,
       g.target_date
FROM goal g
JOIN customer c ON c.customer_id = g.customer_id
WHERE g.priority = 'HIGH'
  AND g.current_funded_amount < 0.25 * g.target_amount
ORDER BY funded_pct, g.target_date;

-- 6. Data-quality / reconciliation exceptions.
-- 6a. Everything the import pipeline quarantined or skipped, with reasons
SELECT b.dataset, b.file_name, s.row_number, s.record_key, s.outcome,
       s.errors, s.warnings
FROM import_staged_row s
JOIN import_batch b ON b.id = s.batch_id
WHERE s.outcome <> 'INSERTED'
ORDER BY b.id, s.row_number;

-- 6b. Exception counts by reason (first token of each error/warning message)
SELECT b.dataset, s.outcome, split_part(regexp_replace(reason, '\s*\(.*\)$', ''), ':', 1) AS field_or_rule, COUNT(*) AS rows
FROM import_staged_row s
JOIN import_batch b ON b.id = s.batch_id
CROSS JOIN LATERAL jsonb_array_elements_text(s.errors || s.warnings) AS reason
GROUP BY 1, 2, 3
ORDER BY rows DESC;

-- 6c. Live reconciliation checks on the final tables (should all return 0 rows; the
--     constraints make most of them impossible, which is the point).
--     Duplicate positions, trades on unknown instruments, and trades dated before the
--     account was opened (loaded with a warning; see DECISIONS.md).
SELECT 'duplicate_position' AS exception, account_id || '/' || instrument_id AS ref
FROM holding_snapshot GROUP BY account_id, instrument_id, snapshot_date HAVING COUNT(*) > 1
UNION ALL
SELECT 'trade_unknown_instrument', t.transaction_id
FROM txn t LEFT JOIN instrument i ON i.instrument_id = t.instrument_id WHERE i.instrument_id IS NULL
UNION ALL
SELECT 'trade_before_account_opened', t.transaction_id
FROM txn t JOIN account a ON a.account_id = t.account_id WHERE t.trade_date < a.opened_at
LIMIT 50;

-- Performance evidence: the transaction listing query used by
-- GET /customers/{id}/transactions (index txn_account_date_idx)
EXPLAIN (ANALYZE, BUFFERS)
SELECT t.*, i.symbol, i.instrument_name
FROM txn t
JOIN account a ON a.account_id = t.account_id
JOIN instrument i ON i.instrument_id = t.instrument_id
WHERE a.customer_id = 'C0026' AND t.trade_date >= '2026-01-01'
ORDER BY t.trade_date DESC, t.transaction_id DESC
LIMIT 25;
