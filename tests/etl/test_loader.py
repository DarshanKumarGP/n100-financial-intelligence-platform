"""
N100 Financial Intelligence Platform
Sprint 6, Day 41: Loader Unit Tests

Location: tests/etl/test_loader.py

10 tests verifying src/etl/loader.py reads correct row counts and
column names for each of the 7 core files, plus its two normalisation
wrapper functions' edge-case behavior.

Row counts and columns below are the REAL, confirmed values from
loader.load_core_file() as of 2026-09 -- verified by direct execution,
not assumed from the spec. These reflect the RAW loaded file (before
Day 3's DQ rules and Day 4's SQLite write), so they intentionally do
NOT match final database table row counts where those differ -- e.g.
documents loads 1585 raw rows here vs. 1457 rows in the documents
table, a gap explained by Day 3's DQ filtering (dq13_url_validity and
similar), which is out of scope for this file. Testing the loader in
isolation from downstream filtering is the point.
"""

import os
import sys

import pandas as pd
import pytest

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src", "etl"),
)
from loader import (
    CORE_FILES,
    apply_ticker_normalisation,
    apply_year_normalisation,
    load_core_file,
)

# ============================================================
# Real row-count / column checks against the actual raw files
# ============================================================


def test_companies_row_and_column_count():
    df = load_core_file("companies", CORE_FILES["companies"])
    assert len(df) == 92
    assert set(df.columns) == {
        "id",
        "company_logo",
        "company_name",
        "chart_link",
        "about_company",
        "website",
        "nse_profile",
        "bse_profile",
        "face_value",
        "book_value",
        "roce_percentage",
        "roe_percentage",
    }


def test_profitandloss_row_and_column_count():
    df = load_core_file("profitandloss", CORE_FILES["profitandloss"])
    assert len(df) == 1276
    assert set(df.columns) == {
        "id",
        "company_id",
        "year",
        "sales",
        "expenses",
        "operating_profit",
        "opm_percentage",
        "other_income",
        "interest",
        "depreciation",
        "profit_before_tax",
        "tax_percentage",
        "net_profit",
        "eps",
        "dividend_payout",
    }


def test_balancesheet_row_and_column_count():
    df = load_core_file("balancesheet", CORE_FILES["balancesheet"])
    assert len(df) == 1312
    assert set(df.columns) == {
        "id",
        "company_id",
        "year",
        "equity_capital",
        "reserves",
        "borrowings",
        "other_liabilities",
        "total_liabilities",
        "fixed_assets",
        "cwip",
        "investments",
        "other_asset",
        "total_assets",
    }


def test_cashflow_row_and_column_count():
    df = load_core_file("cashflow", CORE_FILES["cashflow"])
    assert len(df) == 1187
    assert set(df.columns) == {
        "id",
        "company_id",
        "year",
        "operating_activity",
        "investing_activity",
        "financing_activity",
        "net_cash_flow",
    }


def test_analysis_row_and_column_count():
    df = load_core_file("analysis", CORE_FILES["analysis"])
    assert len(df) == 20
    assert set(df.columns) == {
        "id",
        "company_id",
        "compounded_sales_growth",
        "compounded_profit_growth",
        "stock_price_cagr",
        "roe",
    }


def test_documents_row_and_column_count():
    df = load_core_file("documents", CORE_FILES["documents"])
    assert len(df) == 1585
    assert set(df.columns) == {"id", "company_id", "Year", "Annual_Report"}


def test_prosandcons_row_and_column_count():
    df = load_core_file("prosandcons", CORE_FILES["prosandcons"])
    assert len(df) == 16
    assert set(df.columns) == {"id", "company_id", "pros", "cons"}


# ============================================================
# apply_ticker_normalisation() -- pure unit tests, synthetic data
# ============================================================


def test_apply_ticker_normalisation_cleans_whitespace_and_case():
    df = pd.DataFrame({"id": [" tcs ", "ABB", " reliance"]})
    result = apply_ticker_normalisation(df, "companies")
    assert list(result["id"]) == ["TCS", "ABB", "RELIANCE"]


def test_apply_ticker_normalisation_fixes_company_name_newlines():
    df = pd.DataFrame(
        {
            "id": ["TCS"],
            "company_name": ["Tata Consultancy\nServices Ltd"],
        }
    )
    result = apply_ticker_normalisation(df, "companies")
    assert "\n" not in result["company_name"].iloc[0]
    assert result["company_name"].iloc[0] == "Tata Consultancy Services Ltd"


def test_apply_ticker_normalisation_missing_id_column_warns_and_returns_unchanged():
    df = pd.DataFrame({"some_other_col": [1, 2, 3]})
    result = apply_ticker_normalisation(df, "unknown_table")
    # No id/company_id column -- function should return the df untouched
    # rather than raise, per its own docstring ("skipping ticker normalisation")
    assert list(result.columns) == ["some_other_col"]
    assert len(result) == 3


# ============================================================
# apply_year_normalisation() -- pure unit tests, synthetic data
# ============================================================


def test_apply_year_normalisation_only_applies_to_tables_with_year_column():
    # "companies" is not in YEAR_COLUMN -- function should no-op, not error
    df = pd.DataFrame({"id": ["TCS"], "some_field": [123]})
    result = apply_year_normalisation(df, "companies")
    assert result.equals(df)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
