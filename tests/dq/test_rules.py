import pandas as pd
from src.etl.validator import (
    dq01_company_pk_uniqueness, dq04_balance_sheet_balance,
    dq06_positive_sales, dq09_net_cash_check, dq11_tax_rate_range,
    dq12_dividend_payout_cap, dq14_eps_sign_consistency,
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