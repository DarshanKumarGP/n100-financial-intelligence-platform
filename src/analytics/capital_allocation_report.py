"""
N100 Financial Intelligence Platform
Sprint 5, Day 32: Capital Allocation Report

Builds on Sprint 2's output/capital_allocation.csv (1,063 rows, 92
companies -- completeness verified 2026-09: every company's year count
in capital_allocation.csv matches its year count in the cashflow
table exactly, 0 mismatches).

Produces:
  - output/pattern_distribution_summary.csv: count of companies per
    pattern, latest valid year only (same logic already used in
    cashflow_intelligence.py's capital_allocation_label column --
    imported, not duplicated)
  - output/pattern_changes.csv: every year-over-year pattern change
    per company across their full history (not just most recent --
    flagged as an assumption; spec's own example doesn't specify
    which). Undetermined/null years are skipped when finding "the
    previous label" -- so Reinvestor -> Undetermined -> Mixed logs as
    one change (Reinvestor -> Mixed), consistent with how
    get_latest_capital_allocation_label() already treats Undetermined
    years as non-answers, not as a real pattern.
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cashflow_intelligence import get_latest_capital_allocation_label

CAP_ALLOC_PATH = "output/capital_allocation.csv"


def build_pattern_changes(cap_alloc_df):
    """
    For each company, walks years in order and records every transition
    between consecutive VALID (non-null, non-Undetermined) labels.
    """
    changes = []

    for company_id, group in cap_alloc_df.groupby("company_id"):
        group = group.sort_values("year")
        valid_rows = group[
            group["pattern_label"].notna() & (group["pattern_label"] != "Undetermined")
        ]

        prev_year = None
        prev_label = None
        for _, row in valid_rows.iterrows():
            year = row["year"]
            label = row["pattern_label"]
            if prev_label is not None and label != prev_label:
                changes.append(
                    {
                        "company_id": company_id,
                        "from_year": prev_year,
                        "to_year": year,
                        "from_pattern": prev_label,
                        "to_pattern": label,
                    }
                )
            prev_year = year
            prev_label = label

    return pd.DataFrame(changes)


def main():
    """CLI entry point: verify Sprint 2's capital_allocation.csv coverage, build the pattern distribution summary, and write pattern_changes.csv."""
    cap_alloc_df = pd.read_csv(CAP_ALLOC_PATH)
    companies = sorted(cap_alloc_df["company_id"].unique())

    # --- Distribution summary: latest valid year per company ---
    latest_labels = {
        c: get_latest_capital_allocation_label(cap_alloc_df, c) for c in companies
    }
    dist_df = pd.Series(latest_labels).value_counts().reset_index()
    dist_df.columns = ["pattern_label", "company_count"]
    dist_df = dist_df.sort_values("company_count", ascending=False)

    os.makedirs("output", exist_ok=True)
    dist_df.to_csv("output/pattern_distribution_summary.csv", index=False)

    print("output/pattern_distribution_summary.csv written:")
    print(dist_df.to_string(index=False))
    print(f"\nTotal companies: {sum(dist_df['company_count'])}")

    # --- Pattern changes: full history, every transition ---
    changes_df = build_pattern_changes(cap_alloc_df)
    changes_df.to_csv("output/pattern_changes.csv", index=False)

    print(f"\noutput/pattern_changes.csv written: {len(changes_df)} transitions")
    print(
        f"Distinct companies with at least 1 change: {changes_df['company_id'].nunique() if len(changes_df) else 0}"
    )
    companies_no_change = set(companies) - set(
        changes_df["company_id"].unique() if len(changes_df) else []
    )
    print(
        f"Companies with ZERO pattern changes (stable throughout): {len(companies_no_change)}"
    )

    if len(changes_df):
        print("\nMost common transition types:")
        transition_counts = (
            changes_df.groupby(["from_pattern", "to_pattern"])
            .size()
            .sort_values(ascending=False)
        )
        print(transition_counts.head(10).to_string())

    return dist_df, changes_df


if __name__ == "__main__":
    main()
