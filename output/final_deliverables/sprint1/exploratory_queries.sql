-- ============================================================
-- N100 Financial Intelligence Platform
-- Sprint 1, Day 7: Exploratory Queries
-- Run against: data/nifty100.db
-- ============================================================

-- 1. Row counts across all 12 tables (matches load_audit.csv)
SELECT 'companies' AS table_name, COUNT(*) AS row_count FROM companies
UNION ALL SELECT 'profitandloss', COUNT(*) FROM profitandloss
UNION ALL SELECT 'balancesheet', COUNT(*) FROM balancesheet
UNION ALL SELECT 'cashflow', COUNT(*) FROM cashflow
UNION ALL SELECT 'documents', COUNT(*) FROM documents
UNION ALL SELECT 'analysis', COUNT(*) FROM analysis
UNION ALL SELECT 'prosandcons', COUNT(*) FROM prosandcons
UNION ALL SELECT 'sectors', COUNT(*) FROM sectors
UNION ALL SELECT 'stock_prices', COUNT(*) FROM stock_prices
UNION ALL SELECT 'market_cap', COUNT(*) FROM market_cap
UNION ALL SELECT 'financial_ratios', COUNT(*) FROM financial_ratios
UNION ALL SELECT 'peer_groups', COUNT(*) FROM peer_groups;

-- 2. Null check on key numeric fields in profitandloss
SELECT
    SUM(CASE WHEN sales IS NULL THEN 1 ELSE 0 END) AS null_sales,
    SUM(CASE WHEN net_profit IS NULL THEN 1 ELSE 0 END) AS null_net_profit,
    SUM(CASE WHEN eps IS NULL THEN 1 ELSE 0 END) AS null_eps
FROM profitandloss;

-- 3. Year coverage per company (fiscal years only, excludes TTM --
--    see Day 6 finding on TTM sort behavior)
SELECT company_id, COUNT(DISTINCT year) AS fiscal_years
FROM profitandloss
WHERE year != 'TTM'
GROUP BY company_id
ORDER BY fiscal_years ASC
LIMIT 10;  -- companies with the LEAST coverage -- worth knowing

-- 4. Companies with fewer than 5 years of P&L history (DQ-16 territory)
SELECT company_id, COUNT(DISTINCT year) AS fiscal_years
FROM profitandloss
WHERE year != 'TTM'
GROUP BY company_id
HAVING fiscal_years < 5;

-- 5. TTM row count -- confirms Day 2's finding is still reflected in the DB
SELECT COUNT(*) AS ttm_rows FROM profitandloss WHERE year = 'TTM';

-- 6. Sector distribution of loaded companies
SELECT broad_sector, COUNT(*) AS company_count
FROM sectors
GROUP BY broad_sector
ORDER BY company_count DESC;

-- 7. Top 10 companies by latest-year net profit (real fiscal year, not TTM)
SELECT p.company_id, c.company_name, p.year, p.net_profit
FROM profitandloss p
JOIN companies c ON p.company_id = c.id
WHERE p.year = (
    SELECT MAX(year) FROM profitandloss p2
    WHERE p2.company_id = p.company_id AND p2.year != 'TTM'
)
ORDER BY p.net_profit DESC
LIMIT 10;

-- 8. Balance sheet integrity spot-check -- confirms DQ-04 in practice
--    (should return 0 rows: every row already passed FK+PK constraints,
--    this checks the ACTUAL stored numbers balance within 1%)
SELECT company_id, year, total_assets, total_liabilities,
       ROUND(ABS(total_assets - total_liabilities) / total_assets * 100, 2) AS diff_pct
FROM balancesheet
WHERE ABS(total_assets - total_liabilities) / total_assets >= 0.01;

-- 9. Financials-sector OPM field spot check -- confirms Day 6 Finding 1
--    is visible directly in the loaded database, not just the CSV log
SELECT p.company_id, p.year, p.sales, p.operating_profit, p.opm_percentage,
       ROUND(p.operating_profit / p.sales * 100, 2) AS computed_opm
FROM profitandloss p
JOIN sectors s ON p.company_id = s.company_id
WHERE s.broad_sector = 'Financials' AND p.year = '2024-03'
LIMIT 10;

-- 10. Coverage matrix -- how many companies have data in EVERY core table
--     (a company missing from one table entirely is worth knowing)
SELECT c.id,
       (SELECT COUNT(*) FROM profitandloss p WHERE p.company_id = c.id) AS pl_rows,
       (SELECT COUNT(*) FROM balancesheet b WHERE b.company_id = c.id) AS bs_rows,
       (SELECT COUNT(*) FROM cashflow cf WHERE cf.company_id = c.id) AS cf_rows,
       (SELECT COUNT(*) FROM sectors s WHERE s.company_id = c.id) AS sector_rows
FROM companies c
WHERE pl_rows = 0 OR bs_rows = 0 OR cf_rows = 0 OR sector_rows = 0;