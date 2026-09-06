"""
N100 Financial Intelligence Platform
Sprint 3, Day 15: Screener Filter Engine

Loads screener_config.yaml and applies threshold filters against a
"latest snapshot" DataFrame -- one row per company, using each
company's most recent fiscal year across financial_ratios,
profitandloss, market_cap, and sectors.
"""

import sqlite3
import yaml
import pandas as pd

DB_PATH = "data/nifty100.db"
CONFIG_PATH = "config/screener_config.yaml"


def load_config(path=CONFIG_PATH):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def build_latest_snapshot(conn):
    """
    One row per company: latest fiscal year's financial_ratios, joined
    with that year's P&L (net_profit, sales), sector, and an
    approximate-matched market_cap row (fiscal year 'YYYY-03' -> market_cap
    calendar year YYYY -- see Day 15 note on why this join isn't exact).

    Also computes the outlier-guard signal (net_profit / equity_base)
    so callers can filter it out without recomputing.
    """
    query = """
        SELECT
            fr.company_id, fr.year,
            fr.return_on_equity_pct, fr.return_on_capital_employed_pct,
            fr.net_profit_margin_pct, fr.operating_profit_margin_pct,
            fr.debt_to_equity, fr.high_leverage_flag,
            fr.interest_coverage, fr.icr_label,
            fr.free_cash_flow_cr, fr.fcf_conversion_pct,
            fr.revenue_cagr_3yr, fr.revenue_cagr_5yr,
            fr.pat_cagr_3yr, fr.pat_cagr_5yr,
            fr.eps_cagr_5yr, fr.asset_turnover,
            fr.dividend_payout_ratio_pct, fr.composite_quality_score,
            p.net_profit, p.sales,
            b.equity_capital, b.reserves,
            s.broad_sector,
            mc.pe_ratio, mc.pb_ratio, mc.dividend_yield_pct, mc.market_cap_crore
        FROM financial_ratios fr
        LEFT JOIN profitandloss p ON fr.company_id = p.company_id AND fr.year = p.year
        LEFT JOIN balancesheet b ON fr.company_id = b.company_id AND fr.year = b.year
        LEFT JOIN sectors s ON fr.company_id = s.company_id
        LEFT JOIN market_cap mc
            ON fr.company_id = mc.company_id
            AND mc.year = CAST(SUBSTR(fr.year, 1, 4) AS INTEGER)
        WHERE fr.year = (
            SELECT MAX(fr2.year) FROM financial_ratios fr2
            WHERE fr2.company_id = fr.company_id
        )
    """
    df = pd.read_sql(query, conn)

    df["equity_base"] = df["equity_capital"] + df["reserves"]
    df["profit_to_equity_ratio"] = df.apply(
        lambda r: (r["net_profit"] / r["equity_base"])
        if pd.notna(r["equity_base"]) and r["equity_base"] > 0 and pd.notna(r["net_profit"])
        else None,
        axis=1
    )

    return df


def apply_outlier_guard(df, config):
    """Drops company-years flagged as extreme small-equity-base outliers."""
    guard = config.get("outlier_guard", {})
    if not guard.get("enabled", False):
        return df
    threshold = guard.get("max_profit_to_equity_ratio", 5)
    mask = df["profit_to_equity_ratio"].isna() | (df["profit_to_equity_ratio"] <= threshold)
    return df[mask]


def _icr_effective(row):
    """
    Treats 'Debt Free' as infinity for ICR minimum-threshold filtering,
    per spec Day 15. A debt-free company should always pass any ICR
    minimum, since it has no interest obligation to fail to cover.
    """
    if row.get("icr_label") == "Debt Free":
        return float("inf")
    return row.get("interest_coverage")


def apply_single_filter(df, metric_key, threshold, config):
    """Applies one metric filter to the DataFrame, returns the filtered result."""
    metric = config["metrics"][metric_key]
    column = metric["column"]
    direction = metric["direction"]

    working = df.copy()

    if metric_key == "icr_min":
        working["_icr_effective"] = working.apply(_icr_effective, axis=1)
        compare_col = "_icr_effective"
    else:
        compare_col = column

    if metric.get("sector_exempt"):
        exempt_sector = metric["sector_exempt"]
        exempt_mask = working["broad_sector"] == exempt_sector
        pass_mask = pd.Series(False, index=working.index)
        pass_mask |= exempt_mask
        if direction == "max":
            pass_mask |= (working[compare_col] <= threshold)
        else:
            pass_mask |= (working[compare_col] >= threshold)
        return working[pass_mask].drop(columns=["_icr_effective"], errors="ignore")

    if direction == "max":
        result = working[working[compare_col] <= threshold]
    else:
        result = working[working[compare_col] >= threshold]

    return result.drop(columns=["_icr_effective"], errors="ignore")


def apply_filters(df, filters, config, apply_guard=True):
    """
    filters: dict like {'roe_min': 15, 'de_max': 1.0}
    Applies each filter in sequence (AND logic across all filters),
    then the outlier guard by default, then sorts by composite_quality_score.
    """
    result = df.copy()

    if apply_guard:
        result = apply_outlier_guard(result, config)

    for metric_key, threshold in filters.items():
        result = apply_single_filter(result, metric_key, threshold, config)

    result = result.sort_values("composite_quality_score", ascending=False, na_position="last")

    return result


def run_screener(filters, apply_guard=True):
    """Main entry point: connects, builds snapshot, applies filters."""
    conn = sqlite3.connect(DB_PATH)
    config = load_config()
    snapshot = build_latest_snapshot(conn)
    conn.close()

    return apply_filters(snapshot, filters, config, apply_guard=apply_guard)


if __name__ == "__main__":
    # Quick manual smoke test: ROE > 15%, D/E < 1
    results = run_screener({"roe_min": 15, "de_max": 1.0})
    print(f"ROE>15%% AND D/E<1: {len(results)} companies")
    print(results[["company_id", "return_on_equity_pct", "debt_to_equity", "composite_quality_score"]].head(10).to_string())