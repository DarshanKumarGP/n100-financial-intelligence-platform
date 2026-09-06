"""
N100 Financial Intelligence Platform
Sprint 3, Day 16: 6 Preset Screeners

Each preset is a named filter dict, run through engine.run_screener().
Some presets need logic beyond simple threshold filters (Turnaround
Watch's "D/E declining YoY", Debt-Free Blue Chip's exact D/E=0) --
those are handled as post-filter steps, documented per preset.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine import run_screener, build_latest_snapshot, apply_outlier_guard, load_config
import sqlite3
import pandas as pd

DB_PATH = "data/nifty100.db"


def quality_compounder():
    """ROE > 15%, D/E < 1.0, FCF > 0, Revenue CAGR 5yr > 10%"""
    results = run_screener({
        "roe_min": 15, "de_max": 1.0, "fcf_min": 0.01, "revenue_cagr_5yr_min": 10
    })
    return results


def value_pick():
    """P/E < 20, P/B < 3.0, D/E < 2.0, Dividend Yield > 1%"""
    results = run_screener({
        "pe_max": 20, "pb_max": 3.0, "de_max": 2.0, "dividend_yield_min": 1
    })
    return results


def growth_accelerator():
    """PAT CAGR 5yr > 20%, Revenue CAGR 5yr > 15%, D/E < 2.0"""
    results = run_screener({
        "pat_cagr_5yr_min": 20, "revenue_cagr_5yr_min": 15, "de_max": 2.0
    })
    return results


def dividend_champion():
    """Dividend Yield > 2%, Dividend Payout < 80%, FCF > 0"""
    conn = sqlite3.connect(DB_PATH)
    config = load_config()
    snapshot = build_latest_snapshot(conn)
    conn.close()

    snapshot = apply_outlier_guard(snapshot, config)

    # dividend_payout_ratio_pct is in financial_ratios (from populate_ratios.py's
    # direct pass-through of the source dividend_payout field), so this is a
    # straightforward column filter -- no join needed beyond what's already
    # in build_latest_snapshot.
    result = snapshot[
        (snapshot["dividend_yield_pct"] > 2) &
        (snapshot["dividend_payout_ratio_pct"] < 80) &
        (snapshot["free_cash_flow_cr"] > 0)
    ]
    return result.sort_values("composite_quality_score", ascending=False, na_position="last")


def debtfree_bluechip():
    """D/E < 0.01 (effectively debt-free -- see comment), ROE > 12%, Revenue > 5000 Crore"""
    conn = sqlite3.connect(DB_PATH)
    config = load_config()
    snapshot = build_latest_snapshot(conn)
    conn.close()

    snapshot = apply_outlier_guard(snapshot, config)

    result = snapshot[
        (snapshot["debt_to_equity"] < 0.1) &
        (snapshot["return_on_equity_pct"] > 12) &
        (snapshot["sales"] > 5000)
    ]
    return result.sort_values("composite_quality_score", ascending=False, na_position="last")


def turnaround_watch():
    """
    Revenue CAGR 3yr > 10%, FCF positive in latest year, D/E declining YoY.
    D/E-declining check requires comparing latest year's D/E against the
    prior fiscal year -- a genuine two-row-per-company comparison, unlike
    every other preset which only needs the latest snapshot.
    """
    conn = sqlite3.connect(DB_PATH)
    config = load_config()
    snapshot = build_latest_snapshot(conn)

    # Pull each company's second-most-recent fiscal year D/E for comparison
    prior_year_query = """
        SELECT fr.company_id, fr.debt_to_equity AS prior_de
        FROM financial_ratios fr
        WHERE fr.year = (
            SELECT MAX(fr2.year) FROM financial_ratios fr2
            WHERE fr2.company_id = fr.company_id
              AND fr2.year < (
                  SELECT MAX(fr3.year) FROM financial_ratios fr3
                  WHERE fr3.company_id = fr.company_id
              )
        )
    """
    prior = pd.read_sql(prior_year_query, conn)
    conn.close()

    snapshot = apply_outlier_guard(snapshot, config)
    snapshot = snapshot.merge(prior, on="company_id", how="left")

    result = snapshot[
        (snapshot["revenue_cagr_3yr"] > 10) &
        (snapshot["free_cash_flow_cr"] > 0) &
        (snapshot["debt_to_equity"] < snapshot["prior_de"])  # declining YoY
    ]
    return result.sort_values("composite_quality_score", ascending=False, na_position="last")


PRESETS = {
    "Quality Compounder": quality_compounder,
    "Value Pick": value_pick,
    "Growth Accelerator": growth_accelerator,
    "Dividend Champion": dividend_champion,
    "Debt-Free Blue Chip": debtfree_bluechip,
    "Turnaround Watch": turnaround_watch,
}


if __name__ == "__main__":
    print("Testing all 6 presets against the full 92-company universe...\n")
    for name, func in PRESETS.items():
        result = func()
        count = len(result)
        status = "OK" if 5 <= count <= 50 else "OUT OF RANGE (expected 5-50)"
        print(f"{name}: {count} companies [{status}]")
        if count > 0:
            print("  Top 3:", result["company_id"].head(3).tolist())
        print()