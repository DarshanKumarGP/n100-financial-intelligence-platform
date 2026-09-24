r"""
N100 Financial Intelligence Platform
Sprint 5, Day 29: Analysis Text Parser

Parses analysis.xlsx's 4 text columns (compounded_sales_growth,
compounded_profit_growth, stock_price_cagr, roe) into structured
(period_years, value_pct) pairs.

Coverage note: only 16 rows across 4 companies (HDFCBANK, SBILIFE, TCS,
INFY) have any analysis.xlsx data at all -- confirmed directly against
the database, not assumed from spec. Sprint 1's Section 5.5 stated ~20
rows / ~8 companies; the real figure is smaller. This is a known,
pre-existing data coverage gap, not a parsing failure.

Three distinct text shapes found in the real data (catalogued 2026-09
by inspecting all 16 rows directly, not guessed):
  'N Years: X%'    -- standard case, spec's regex handles this directly
  'TTM: X%'        -- no leading digit, needs its own branch
  'Last Year: X%'  -- no digit at all, needs its own branch
  Negative values ('-2%') confirmed present -- spec's [\d.]+ pattern
  would silently drop the minus sign; fixed by including it explicitly.
"""

import os
import re
import sqlite3

import pandas as pd

DB_PATH = "data/nifty100.db"

TARGET_COLUMNS = {
    "compounded_sales_growth": "sales_growth",
    "compounded_profit_growth": "profit_growth",
    "stock_price_cagr": "stock_price_cagr",
    "roe": "roe",
}

# Standard case: "10 Years: 21%", "1 Year: -2%", tolerant of irregular
# whitespace and an optional leading minus sign on the value.
STANDARD_PATTERN = re.compile(r"(\d+)\s*Years?:?\s*(-?[\d.]+)%")

# TTM: no period number at all -- represented as period_years=0 with a
# flag, since "0 years" isn't literally true but there's no real period
# length to record. Consistent with how Sprint 2 treated TTM: recognized
# explicitly, not forced into a fake numeric period.
TTM_PATTERN = re.compile(r"TTM:?\s*(-?[\d.]+)%")

# "Last Year:" -- same idea, represents a 1-year lookback but phrased
# without a digit.
LAST_YEAR_PATTERN = re.compile(r"Last\s*Year:?\s*(-?[\d.]+)%")


def parse_single_value(raw_text):
    """
    Returns (period_years, value_pct, period_label) or None if the text
    doesn't match any known pattern. period_label distinguishes TTM/
    Last Year from a real numeric period, since both are conceptually
    "period_years=1" but arose from different text shapes.
    """
    if raw_text is None or not isinstance(raw_text, str):
        return None

    text = raw_text.strip()
    if not text:
        return None

    m = STANDARD_PATTERN.search(text)
    if m:
        return int(m.group(1)), float(m.group(2)), "years"

    m = TTM_PATTERN.search(text)
    if m:
        return None, float(m.group(1)), "TTM"

    m = LAST_YEAR_PATTERN.search(text)
    if m:
        return 1, float(m.group(1)), "last_year"

    return None


def main():
    """CLI entry point: parse analysis.xlsx's text fields and write output/analysis_parsed.csv and output/parse_failures.csv."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT entry_id, company_id, compounded_sales_growth, "
        "compounded_profit_growth, stock_price_cagr, roe FROM analysis;"
    ).fetchall()
    conn.close()

    parsed_records = []
    failure_records = []

    for entry_id, company_id, sales_growth, profit_growth, stock_cagr, roe in rows:
        raw_values = {
            "compounded_sales_growth": sales_growth,
            "compounded_profit_growth": profit_growth,
            "stock_price_cagr": stock_cagr,
            "roe": roe,
        }

        for col_name, raw_text in raw_values.items():
            metric_type = TARGET_COLUMNS[col_name]
            result = parse_single_value(raw_text)

            if result is None:
                failure_records.append(
                    {
                        "entry_id": entry_id,
                        "company_id": company_id,
                        "column": col_name,
                        "raw_value": raw_text,
                    }
                )
            else:
                period_years, value_pct, period_label = result
                parsed_records.append(
                    {
                        "company_id": company_id,
                        "metric_type": metric_type,
                        "period_years": period_years,
                        "value_pct": value_pct,
                        "period_label": period_label,
                    }
                )

    os.makedirs("output", exist_ok=True)

    parsed_df = pd.DataFrame(parsed_records)
    parsed_df.to_csv("output/analysis_parsed.csv", index=False)
    print(f"output/analysis_parsed.csv written: {len(parsed_df)} rows")

    failures_df = pd.DataFrame(failure_records)
    failures_df.to_csv("output/parse_failures.csv", index=False)
    print(f"output/parse_failures.csv written: {len(failures_df)} rows")

    if len(failures_df) > 0:
        print("\nFailed entries:")
        print(failures_df.to_string())

    print(
        f"\nDistinct companies covered: {parsed_df['company_id'].nunique() if len(parsed_df) else 0}"
    )
    print("\nPeriod label distribution:")
    print(
        parsed_df["period_label"].value_counts().to_string()
        if len(parsed_df)
        else "none"
    )

    return parsed_df


if __name__ == "__main__":
    main()
