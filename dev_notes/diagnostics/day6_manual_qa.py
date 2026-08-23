"""
N100 Financial Intelligence Platform — Day 6: Manual QA
Pulls a full snapshot per company for human eyeball review.
"""

import sqlite3
import random

random.seed(42)

conn = sqlite3.connect("data/nifty100.db")

all_companies = [row[0] for row in conn.execute("SELECT id FROM companies;").fetchall()]
ANCHOR = "TCS"
remaining = [c for c in all_companies if c != ANCHOR]
sample = [ANCHOR] + random.sample(remaining, 4)

print(f"Reviewing 5 companies: {sample}\n")

for ticker in sample:
    print("=" * 70)
    print(f"COMPANY: {ticker}")
    print("=" * 70)

    name = conn.execute("SELECT company_name FROM companies WHERE id=?", (ticker,)).fetchone()
    print(f"Name: {name[0] if name else 'MISSING'}")

    # NOTE: year != 'TTM' excludes the rolling-window row so we get the
    # actual latest FISCAL year-end, not TTM (which always sorts last
    # alphabetically as text, incorrectly appearing "latest").
    pl = conn.execute("""
        SELECT year, sales, net_profit, eps, opm_percentage
        FROM profitandloss WHERE company_id=? AND year != 'TTM'
        ORDER BY year DESC LIMIT 1
    """, (ticker,)).fetchone()
    print(f"\nLatest fiscal-year P&L: {pl}")
    print("  (year, sales_cr, net_profit_cr, eps, opm_pct)")

    bs = conn.execute("""
        SELECT year, equity_capital, reserves, borrowings, total_assets, total_liabilities
        FROM balancesheet WHERE company_id=? ORDER BY year DESC LIMIT 1
    """, (ticker,)).fetchone()
    print(f"\nLatest Balance Sheet: {bs}")

    cf = conn.execute("""
        SELECT year, operating_activity, investing_activity, financing_activity
        FROM cashflow WHERE company_id=? ORDER BY year DESC LIMIT 1
    """, (ticker,)).fetchone()
    print(f"\nLatest Cash Flow: {cf}")

    pl_years = conn.execute("SELECT COUNT(DISTINCT year) FROM profitandloss WHERE company_id=? AND year != 'TTM'", (ticker,)).fetchone()[0]
    bs_years = conn.execute("SELECT COUNT(DISTINCT year) FROM balancesheet WHERE company_id=?", (ticker,)).fetchone()[0]
    cf_years = conn.execute("SELECT COUNT(DISTINCT year) FROM cashflow WHERE company_id=?", (ticker,)).fetchone()[0]
    print(f"\nYear coverage: P&L={pl_years}yr, BS={bs_years}yr, CF={cf_years}yr")

    if pl and bs and bs[1] is not None and bs[2] is not None:
        equity_plus_reserves = (bs[1] or 0) + (bs[2] or 0)
        if equity_plus_reserves > 0 and pl[2] is not None:
            roe = (pl[2] / equity_plus_reserves) * 100
            print(f"\nQuick ROE check (computed, NOT from opm_percentage field): {roe:.1f}%")
        if bs[4] and bs[5]:
            bs_diff_pct = abs(bs[4] - bs[5]) / bs[4] * 100
            print(f"Balance sheet check: assets={bs[4]}, liabilities={bs[5]}, diff={bs_diff_pct:.2f}%")

        # Computed OPM vs source field, side by side -- this is the Day 6 finding in action
        if pl[1] and pl[1] != 0:
            computed_opm = (None)  # operating_profit not selected above; see note
        print(f"Source opm_percentage field: {pl[4]}  (NOTE: unreliable for Financials sector, see day6_qa_review.md)")

    sector = conn.execute("SELECT broad_sector, sub_sector FROM sectors WHERE company_id=?", (ticker,)).fetchone()
    print(f"\nSector: {sector}")
    print()

conn.close()
print("=" * 70)
print("Review complete.")