"""
N100 Financial Intelligence Platform
Sprint 1, Day 2: Excel Loader

Loads all 7 core datasets with the correct header row, applies
normalize_year() and normalize_ticker() to every table that has
those columns, and reports basic load statistics.

This does NOT yet write to SQLite (that's Day 4) or run the full
16 data quality rules (that's Day 3) -- Day 2's job is just: load
cleanly, with consistent tickers and consistent year labels.

Run from the project root:
    python src/etl/loader.py
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normaliser import normalize_year, normalize_ticker

RAW_DIR = Path("data/raw")

# Core files use header=1 (row 0 is a metadata banner, row 1 is the
# real header row) -- confirmed directly against companies.xlsx.
CORE_FILES = {
    "companies": "companies.xlsx",
    "profitandloss": "profitandloss.xlsx",
    "balancesheet": "balancesheet.xlsx",
    "cashflow": "cashflow.xlsx",
    "analysis": "analysis.xlsx",
    "documents": "documents.xlsx",
    "prosandcons": "prosandcons.xlsx",
}

# Which tables have a 'year' column, and what it's actually called
# (documents.xlsx uses a capital-Y 'Year' -- confirmed in the spec).
YEAR_COLUMN = {
    "profitandloss": "year",
    "balancesheet": "year",
    "cashflow": "year",
    "documents": "Year",
}


def load_core_file(name: str, filename: str) -> pd.DataFrame:
    """Load one core Excel file with the correct header row."""
    path = RAW_DIR / filename
    df = pd.read_excel(path, header=1)
    print(f"  [{name}] loaded {len(df)} rows, {len(df.columns)} columns")
    return df


def apply_ticker_normalisation(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """Apply normalize_ticker() to whichever ID column this table has."""
    id_col = "id" if "id" in df.columns else "company_id"
    if id_col not in df.columns:
        print(f"  [{name}] WARNING - no id/company_id column found, skipping ticker normalisation")
        return df

    before_nulls = df[id_col].isna().sum()
    df[id_col] = df[id_col].apply(normalize_ticker)
    rejected = df[id_col].isna().sum() - before_nulls

    if rejected > 0:
        print(f"  [{name}] WARNING - {rejected} rows have unusable {id_col} after normalisation")

    # Also fix the company_name embedded-newline issue found during data inspection
    if "company_name" in df.columns:
        df["company_name"] = df["company_name"].astype(str).str.strip().str.replace("\n", " ", regex=False)

    return df


def apply_year_normalisation(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """Apply normalize_year() if this table has a year column."""
    if name not in YEAR_COLUMN:
        return df

    year_col = YEAR_COLUMN[name]
    if year_col not in df.columns:
        print(f"  [{name}] WARNING - expected year column '{year_col}' not found")
        return df

    df[year_col] = df[year_col].apply(normalize_year)
    parse_errors = (df[year_col] == "PARSE_ERROR").sum()
    ttm_rows = (df[year_col] == "TTM").sum()

    if parse_errors > 0:
        print(f"  [{name}] WARNING - {parse_errors} rows had unparseable year values (logged, not fixed -- see validation_failures.csv in Day 3)")
    if ttm_rows > 0:
        print(f"  [{name}] NOTE - {ttm_rows} rows are TTM (Trailing Twelve Months) -- valid, but excluded from year-over-year calculations downstream")

    return df


def main():
    print("Loading 7 core datasets...\n")

    loaded = {}
    for name, filename in CORE_FILES.items():
        df = load_core_file(name, filename)
        df = apply_ticker_normalisation(df, name)
        df = apply_year_normalisation(df, name)
        loaded[name] = df

    print("\nLoad summary:")
    for name, df in loaded.items():
        print(f"  {name}: {len(df)} rows")

    # Quick sanity check on the fix from data inspection
    companies = loaded["companies"]
    remaining_newlines = companies["company_name"].str.contains("\n").sum()
    print(f"\nCompany names with embedded newlines remaining: {remaining_newlines} (should be 0)")


if __name__ == "__main__":
    main()