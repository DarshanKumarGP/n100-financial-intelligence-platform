import pandas as pd
from src.etl.validator import (
    dq01_company_pk_uniqueness, dq02_annual_pk_uniqueness, dq03_fk_integrity,
    dq04_balance_sheet_balance, dq05_opm_cross_check, dq06_positive_sales,
    dq07_year_format, dq08_ticker_format, dq09_net_cash_check,
    dq10_non_negative_fixed_assets, dq11_tax_rate_range,
    dq12_dividend_payout_cap, dq14_eps_sign_consistency,
    dq15_strict_balance_info, dq16_coverage_check,
)


def test_dq01_duplicate_id():
    companies = pd.DataFrame({"id": ["TCS", "TCS", "INFY"]})
    result = dq01_company_pk_uniqueness(companies)
    assert len(result) == 2
    assert result[0]["severity"] == "CRITICAL"


def test_dq04_bs_balance_violation():
    bs = pd.DataFrame({
        "company_id": ["TCS"], "year": ["2023-03"],
        "total_assets": [1000], "total_liabilities": [1020],
    })
    result = dq04_balance_sheet_balance(bs)
    assert len(result) == 1
    assert result[0]["severity"] == "WARNING"


def test_dq04_bs_within_tolerance():
    bs = pd.DataFrame({
        "company_id": ["TCS"], "year": ["2023-03"],
        "total_assets": [1000], "total_liabilities": [1005],
    })
    assert dq04_balance_sheet_balance(bs) == []


def test_dq06_zero_sales():
    pl = pd.DataFrame({"company_id": ["X"], "year": ["2023-03"], "sales": [0]})
    result = dq06_positive_sales(pl)
    assert len(result) == 1 and result[0]["severity"] == "WARNING"


def test_dq09_net_cash_mismatch():
    cf = pd.DataFrame({
        "company_id": ["X"], "year": ["2023-03"],
        "operating_activity": [100], "investing_activity": [-50],
        "financing_activity": [-20], "net_cash_flow": [50],  # should be 30
    })
    result = dq09_net_cash_check(cf)
    assert len(result) == 1


def test_dq11_tax_rate_out_of_range():
    pl = pd.DataFrame({"company_id": ["X"], "year": ["2023-03"], "tax_percentage": [75]})
    assert len(dq11_tax_rate_range(pl)) == 1


def test_dq12_dividend_payout_over_cap():
    pl = pd.DataFrame({"company_id": ["X"], "year": ["2023-03"], "dividend_payout": [250]})
    assert len(dq12_dividend_payout_cap(pl)) == 1


def test_dq14_eps_sign_mismatch():
    pl = pd.DataFrame({
        "company_id": ["X"], "year": ["2023-03"],
        "net_profit": [500], "eps": [-2],
    })
    result = dq14_eps_sign_consistency(pl)
    assert len(result) == 1


# ============================================================
# Sprint 3, Day 21: Remaining DQ rule tests (closing gap from
# Sprint 1 -- validator.py implements all 16 rules, but only 7
# had test coverage before this addition)
# ============================================================

def test_dq02_duplicate_year_pair():
    df = pd.DataFrame({
        "company_id": ["TCS", "TCS", "INFY"],
        "year": ["2023-03", "2023-03", "2023-03"],
    })
    result = dq02_annual_pk_uniqueness(df, "profitandloss")
    assert len(result) == 2
    assert result[0]["severity"] == "CRITICAL"


def test_dq03_orphan_row_rejected():
    df = pd.DataFrame({"company_id": ["FAKECO"], "year": ["2023-03"]})
    valid_ids = {"TCS", "INFY"}
    result = dq03_fk_integrity(df, "profitandloss", valid_ids)
    assert len(result) == 1
    assert result[0]["severity"] == "CRITICAL"


def test_dq05_opm_mismatch_flagged():
    pl = pd.DataFrame({
        "company_id": ["X"], "year": ["2023-03"],
        "sales": [1000], "operating_profit": [200], "opm_percentage": [50.0],  # real OPM=20%, source says 50%
    })
    result = dq05_opm_cross_check(pl)
    assert len(result) == 1
    assert result[0]["severity"] == "WARNING"


def test_dq07_unparseable_year_rejected():
    df = pd.DataFrame({
        "company_id": ["X"], "year": ["PARSE_ERROR"], "year_raw": ["garbage value"],
    })
    result = dq07_year_format(df, "profitandloss")
    assert len(result) == 1
    assert result[0]["severity"] == "CRITICAL"


def test_dq08_ticker_too_short_rejected():
    df = pd.DataFrame({"company_id": ["A"], "year": ["2023-03"]})  # 1 char, below the 2-char minimum
    result = dq08_ticker_format(df, "profitandloss")
    assert len(result) == 1
    assert result[0]["severity"] == "CRITICAL"


def test_dq10_negative_fixed_assets_flagged():
    bs = pd.DataFrame({
        "company_id": ["X"], "year": ["2023-03"], "fixed_assets": [-50],
    })
    result = dq10_non_negative_fixed_assets(bs)
    assert len(result) == 1
    assert result[0]["severity"] == "WARNING"


def test_dq15_strict_balance_info_returns_one_entry():
    bs = pd.DataFrame({
        "total_assets": [1000, 1000], "total_liabilities": [1000, 1005],
    })
    result = dq15_strict_balance_info(bs)
    assert len(result) == 1
    assert result[0]["severity"] == "INFO"
    assert "1 rows not strictly equal" in result[0]["issue"]


def test_dq16_thin_coverage_flagged():
    pl = pd.DataFrame({
        "company_id": ["X", "X"], "year": ["2023-03", "2022-03"],
    })
    bs = pd.DataFrame({"company_id": ["X"], "year": ["2023-03"]})
    cf = pd.DataFrame({"company_id": ["X"], "year": ["2023-03"]})
    result = dq16_coverage_check(pl, bs, cf)
    assert len(result) == 1  # only 2 years of history, below the 5-year threshold
    assert result[0]["severity"] == "WARNING"


def test_dq16_sufficient_coverage_not_flagged():
    years = [f"{2015+i}-03" for i in range(6)]  # 6 years, above threshold
    pl = pd.DataFrame({"company_id": ["X"] * 6, "year": years})
    bs = pd.DataFrame({"company_id": ["X"] * 6, "year": years})
    cf = pd.DataFrame({"company_id": ["X"] * 6, "year": years})
    result = dq16_coverage_check(pl, bs, cf)
    assert len(result) == 0