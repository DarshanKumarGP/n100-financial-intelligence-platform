"""
N100 Financial Intelligence Platform
Sprint 2, Day 8: Profitability Ratio Tests
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "analytics"))

from ratios import (
    net_profit_margin, operating_profit_margin, opm_cross_check,
    return_on_equity, return_on_capital_employed, return_on_assets,
)


def test_npm_normal_case():
    assert net_profit_margin(net_profit=1000, sales=5000) == 20.0


def test_npm_zero_sales_returns_none():
    assert net_profit_margin(net_profit=1000, sales=0) is None


def test_opm_normal_case():
    assert operating_profit_margin(operating_profit=2382, sales=3577) == pytest_approx(66.59)


def test_roe_normal_case():
    # TCS-like: net_profit=46099, equity=362, reserves=101133
    result = return_on_equity(net_profit=46099, equity_capital=362, reserves=101133)
    assert result == pytest_approx(45.44, tol=0.1)


def test_roe_negative_equity_returns_none():
    result = return_on_equity(net_profit=100, equity_capital=5, reserves=-200)
    assert result is None


def test_roe_zero_equity_returns_none():
    result = return_on_equity(net_profit=100, equity_capital=0, reserves=0)
    assert result is None


def test_opm_cross_check_flags_mismatch():
    # BAJFINANCE-like: source field wildly off from computed value
    assert opm_cross_check(computed_opm=29.29, source_opm=19987.0) is True


def test_opm_cross_check_no_mismatch():
    assert opm_cross_check(computed_opm=27.0, source_opm=27.3) is False


def test_roa_zero_total_assets_returns_none():
    assert return_on_assets(net_profit=100, total_assets=0) is None


def test_roce_zero_capital_employed_returns_none():
    result = return_on_capital_employed(
        operating_profit=100, depreciation=10,
        equity_capital=0, reserves=0, borrowings=0
    )
    assert result is None


# Small helper since pytest.approx needs pytest imported --
# done this way to keep the test file dependency-light and explicit
def pytest_approx(value, tol=0.01):
    import pytest
    return pytest.approx(value, abs=tol)