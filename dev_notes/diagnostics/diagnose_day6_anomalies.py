import sqlite3

conn = sqlite3.connect("data/nifty100.db")

print("=== BAJFINANCE: full P&L history, checking opm_percentage across all years ===")
rows = conn.execute("""
    SELECT year, sales, operating_profit, opm_percentage
    FROM profitandloss WHERE company_id='BAJFINANCE' ORDER BY year
""").fetchall()
for r in rows:
    print(r)

print("\n=== HAL: full Balance Sheet history, checking equity/reserves trend ===")
rows = conn.execute("""
    SELECT year, equity_capital, reserves, borrowings, total_assets
    FROM balancesheet WHERE company_id='HAL' ORDER BY year
""").fetchall()
for r in rows:
    print(r)

conn.close()