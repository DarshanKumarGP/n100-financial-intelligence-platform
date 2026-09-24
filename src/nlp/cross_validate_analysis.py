"""
N100 Financial Intelligence Platform
Sprint 5, Day 29: Cross-validate parsed analysis.xlsx values against
the Ratio Engine's own computed CAGR (Sprint 2).

Only "years"-labeled entries with a period matching an available
computed CAGR window (3/5/10yr) are compared. TTM and "Last Year"
entries have no clean CAGR equivalent and are excluded from this
comparison, not force-matched to a wrong window.
"""

import sqlite3

import pandas as pd

DB_PATH = "data/nifty100.db"

METRIC_TO_COLUMN = {
    "sales_growth": "revenue_cagr_{p}yr",
    "profit_growth": "pat_cagr_{p}yr",
}


def main():
    """CLI entry point: cross-validate parser.py's parsed CAGR values against the Ratio Engine's computed CAGR and flag divergences over 5%."""
    parsed = pd.read_csv("output/analysis_parsed.csv")
    comparable = parsed[
        (parsed["period_label"] == "years")
        & (parsed["metric_type"].isin(METRIC_TO_COLUMN.keys()))
        & (parsed["period_years"].isin([3, 5, 10]))
    ]

    conn = sqlite3.connect(DB_PATH)
    results = []

    for _, row in comparable.iterrows():
        col_template = METRIC_TO_COLUMN[row["metric_type"]]
        computed_col = col_template.format(p=int(row["period_years"]))

        computed = conn.execute(
            f"""
            SELECT {computed_col} FROM financial_ratios
            WHERE company_id = ? AND year = (
                SELECT MAX(y2.year) FROM financial_ratios y2
                WHERE y2.company_id = financial_ratios.company_id AND y2.year != 'TTM'
            )
        """,
            (row["company_id"],),
        ).fetchone()

        computed_value = computed[0] if computed else None

        if computed_value is not None:
            diff_pct = abs(row["value_pct"] - computed_value)
            flagged = diff_pct > 5
        else:
            diff_pct = None
            flagged = None

        results.append(
            {
                "company_id": row["company_id"],
                "metric_type": row["metric_type"],
                "period_years": row["period_years"],
                "parsed_value_pct": row["value_pct"],
                "computed_value_pct": computed_value,
                "abs_diff_pct": diff_pct,
                "flagged_divergence": flagged,
            }
        )

    conn.close()

    results_df = pd.DataFrame(results)
    results_df.to_csv("output/analysis_cross_validation.csv", index=False)

    print(f"Compared {len(results_df)} parsed values against computed CAGR.")
    print(f"\nRows with divergence >5%: {results_df['flagged_divergence'].sum()}")
    print(results_df.to_string())


if __name__ == "__main__":
    main()
