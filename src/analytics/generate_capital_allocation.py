"""
N100 Financial Intelligence Platform
Sprint 2, Day 11: Generate output/capital_allocation.csv

Pulls every (company_id, year) from cashflow, computes the sign-based
pattern classification for each, and writes the required CSV.
"""

import sys
import os
import sqlite3
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from cashflow_kpis import classify_capital_allocation, cfo_quality_score

DB_PATH = "data/nifty100.db"


def main():
    conn = sqlite3.connect(DB_PATH)

    # Cashflow gives us CFO/CFI/CFF directly. Join P&L for net_profit
    # (PAT) so we can compute cfo_over_pat -- needed to distinguish
    # 'Reinvestor' from 'Shareholder Returns' within the (+,-,-) pattern.
    query = """
        SELECT cf.company_id, cf.year,
               cf.operating_activity AS cfo,
               cf.investing_activity AS cfi,
               cf.financing_activity AS cff,
               pl.net_profit AS pat
        FROM cashflow cf
        LEFT JOIN profitandloss pl
            ON cf.company_id = pl.company_id AND cf.year = pl.year
        WHERE cf.year != 'TTM'
        ORDER BY cf.company_id, cf.year
    """
    df = pd.read_sql(query, conn)
    conn.close()

    print(f"Processing {len(df)} company-year rows...")

    rows = []
    for _, r in df.iterrows():
        cfo_over_pat = None
        if r["pat"] is not None and r["pat"] != 0 and r["cfo"] is not None:
            cfo_over_pat = r["cfo"] / r["pat"]

        pattern = classify_capital_allocation(
            cfo=r["cfo"], cfi=r["cfi"], cff=r["cff"], cfo_over_pat=cfo_over_pat
        )

        cfo_sign = "+" if r["cfo"] and r["cfo"] > 0 else ("-" if r["cfo"] and r["cfo"] < 0 else None)
        cfi_sign = "+" if r["cfi"] and r["cfi"] > 0 else ("-" if r["cfi"] and r["cfi"] < 0 else None)
        cff_sign = "+" if r["cff"] and r["cff"] > 0 else ("-" if r["cff"] and r["cff"] < 0 else None)

        rows.append({
            "company_id": r["company_id"],
            "year": r["year"],
            "cfo_sign": cfo_sign,
            "cfi_sign": cfi_sign,
            "cff_sign": cff_sign,
            "pattern_label": pattern,
        })

    out = pd.DataFrame(rows)
    os.makedirs("output", exist_ok=True)
    out.to_csv("output/capital_allocation.csv", index=False)

    print(f"\noutput/capital_allocation.csv written: {len(out)} rows")
    print("\nPattern distribution:")
    print(out["pattern_label"].value_counts().to_string())


if __name__ == "__main__":
    main()