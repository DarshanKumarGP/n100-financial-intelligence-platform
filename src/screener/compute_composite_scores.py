"""
N100 Financial Intelligence Platform
Sprint 3, Day 17: Composite Quality Score (spec formula, supersedes
Sprint 2's simpler placeholder version in populate_ratios.py)

Formula: 35% Profitability (ROE 15% + ROCE 10% + NPM 10%)
       + 30% Cash Quality (FCF CAGR 15% + CFO/PAT 10% + FCF-positive flag 5%)
       + 20% Growth (Revenue CAGR 10% + PAT CAGR 10%)
       + 15% Leverage (D/E score 10% + ICR score 5%)

All sub-scores are P10/P90 winsorized to 0-100, computed SECTOR-RELATIVE
(within broad_sector) per spec Day 17, not against the full universe --
this matters because, e.g., a "good" D/E for a bank looks nothing like a
"good" D/E for an IT company.
"""

import sys
import os
import sqlite3
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "analytics"))
from cagr import windowed_cagr

DB_PATH = "data/nifty100.db"


def compute_fcf_cagr_and_cfo_pat(conn):
    """
    For every company-year, computes FCF 5yr CAGR (as-of that year, same
    pattern as Sprint 2 Day 12's revenue/pat CAGR) and a rolling 5yr
    average CFO/PAT ratio. Returns a DataFrame keyed on (company_id, year).
    """
    query = """
        SELECT fr.company_id, fr.year, fr.free_cash_flow_cr,
               fr.cash_from_operations_cr, p.net_profit
        FROM financial_ratios fr
        LEFT JOIN profitandloss p ON fr.company_id = p.company_id AND fr.year = p.year
        ORDER BY fr.company_id, fr.year
    """
    df = pd.read_sql(query, conn)

    results = []
    for company_id, group in df.groupby("company_id"):
        group = group.sort_values("year").reset_index(drop=True)
        fcf_pairs_full = list(zip(group["year"], group["free_cash_flow_cr"]))

        for _, row in group.iterrows():
            target_year = row["year"]
            fcf_asof = [(y, v) for y, v in fcf_pairs_full if y <= target_year]
            fcf_cagr, fcf_flag = windowed_cagr(fcf_asof, 5)

            # CFO/PAT ratio: average over up to 5 trailing years as-of this row
            window = group[group["year"] <= target_year].tail(5)
            valid = window.dropna(subset=["cash_from_operations_cr", "net_profit"])
            valid = valid[valid["net_profit"] != 0]
            cfo_pat_ratio = (
                (valid["cash_from_operations_cr"] / valid["net_profit"]).mean()
                if len(valid) > 0 else None
            )

            results.append({
                "company_id": company_id, "year": target_year,
                "fcf_cagr_5yr": fcf_cagr, "fcf_cagr_5yr_flag": fcf_flag,
                "cfo_pat_ratio_5yr": cfo_pat_ratio,
            })

    return pd.DataFrame(results)


def winsorized_score_within_group(series, value, invert=False):
    """Same P10/P90 winsorization as Sprint 2, but caller controls the group."""
    valid = series.dropna()
    if len(valid) == 0 or value is None or pd.isna(value):
        return None
    p10, p90 = valid.quantile(0.10), valid.quantile(0.90)
    if p90 == p10:
        return None
    clipped = max(p10, min(p90, value))
    score = (clipped - p10) / (p90 - p10) * 100
    return 100 - score if invert else score


def compute_composite_for_sector(sector_df):
    """
    Computes the full Day 17 weighted composite score for every row in a
    single sector's DataFrame -- winsorization bounds are drawn from THIS
    sector only, per spec's sector-relative requirement.
    """
    scores = pd.DataFrame(index=sector_df.index)

    scores["roe_s"] = sector_df["return_on_equity_pct"].apply(
        lambda v: winsorized_score_within_group(sector_df["return_on_equity_pct"], v))
    scores["roce_s"] = sector_df["return_on_capital_employed_pct"].apply(
        lambda v: winsorized_score_within_group(sector_df["return_on_capital_employed_pct"], v))
    scores["npm_s"] = sector_df["net_profit_margin_pct"].apply(
        lambda v: winsorized_score_within_group(sector_df["net_profit_margin_pct"], v))

    scores["fcf_cagr_s"] = sector_df["fcf_cagr_5yr"].apply(
        lambda v: winsorized_score_within_group(sector_df["fcf_cagr_5yr"], v))
    scores["cfo_pat_s"] = sector_df["cfo_pat_ratio_5yr"].apply(
        lambda v: winsorized_score_within_group(sector_df["cfo_pat_ratio_5yr"], v))
    scores["fcf_positive_flag_s"] = (sector_df["free_cash_flow_cr"] > 0).map({True: 100, False: 0})

    scores["revenue_cagr_s"] = sector_df["revenue_cagr_5yr"].apply(
        lambda v: winsorized_score_within_group(sector_df["revenue_cagr_5yr"], v))
    scores["pat_cagr_s"] = sector_df["pat_cagr_5yr"].apply(
        lambda v: winsorized_score_within_group(sector_df["pat_cagr_5yr"], v))

    scores["de_s"] = sector_df["debt_to_equity"].apply(
        lambda v: winsorized_score_within_group(sector_df["debt_to_equity"], v, invert=True))
    # ICR score: Debt Free treated as best-possible (100), same "infinity" logic as Day 15
    icr_for_scoring = sector_df.apply(
        lambda r: 999 if r.get("icr_label") == "Debt Free" else r["interest_coverage"], axis=1)
    scores["icr_s"] = icr_for_scoring.apply(
        lambda v: winsorized_score_within_group(icr_for_scoring, v))

    def weighted_row(row):
        parts = [
            (row["roe_s"], 0.15), (row["roce_s"], 0.10), (row["npm_s"], 0.10),
            (row["fcf_cagr_s"], 0.15), (row["cfo_pat_s"], 0.10), (row["fcf_positive_flag_s"], 0.05),
            (row["revenue_cagr_s"], 0.10), (row["pat_cagr_s"], 0.10),
            (row["de_s"], 0.10), (row["icr_s"], 0.05),
        ]
        valid_parts = [(s, w) for s, w in parts if s is not None and not pd.isna(s)]
        if not valid_parts:
            return None
        total_weight = sum(w for _, w in valid_parts)
        return sum(s * w for s, w in valid_parts) / total_weight

    return scores.apply(weighted_row, axis=1)


def main():
    conn = sqlite3.connect(DB_PATH)

    print("Computing FCF CAGR and CFO/PAT ratio (missing pieces, not in Sprint 2)...")
    extra = compute_fcf_cagr_and_cfo_pat(conn)

    query = """
        SELECT fr.*, s.broad_sector
        FROM financial_ratios fr
        LEFT JOIN sectors s ON fr.company_id = s.company_id
    """
    df = pd.read_sql(query, conn)
    df = df.merge(extra, on=["company_id", "year"], how="left")

    print(f"Computing sector-relative composite scores across {df['broad_sector'].nunique()} sectors...")
    df["composite_quality_score_v2"] = None
    for sector, group in df.groupby("broad_sector"):
        sector_scores = compute_composite_for_sector(group)
        df.loc[group.index, "composite_quality_score_v2"] = sector_scores

    # Add the two new columns permanently if not already present, then update
    for col in ["fcf_cagr_5yr", "fcf_cagr_5yr_flag", "cfo_pat_ratio_5yr"]:
        try:
            conn.execute(f"ALTER TABLE financial_ratios ADD COLUMN {col} TEXT;")
        except sqlite3.OperationalError:
            pass  # column already exists from a prior run

    for _, row in df.iterrows():
        conn.execute("""
            UPDATE financial_ratios
            SET composite_quality_score = ?, fcf_cagr_5yr = ?, fcf_cagr_5yr_flag = ?, cfo_pat_ratio_5yr = ?
            WHERE company_id = ? AND year = ?
        """, (
            row["composite_quality_score_v2"], row["fcf_cagr_5yr"], row["fcf_cagr_5yr_flag"],
            row["cfo_pat_ratio_5yr"], row["company_id"], row["year"]
        ))

    conn.commit()
    print(f"\nUpdated composite_quality_score for {len(df)} rows using the Day 17 sector-relative formula.")
    print("(Supersedes Sprint 2's simpler population-wide formula in populate_ratios.py.)")

    sample = df[["company_id", "broad_sector", "composite_quality_score_v2"]].dropna().sample(min(5, len(df)))
    print("\nSample check:")
    print(sample.to_string())

    conn.close()


if __name__ == "__main__":
    main()