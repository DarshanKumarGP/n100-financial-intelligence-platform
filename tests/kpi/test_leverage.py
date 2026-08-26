"""
N100 Financial Intelligence Platform
Sprint 2, Day 9: Leverage & Efficiency Ratio Tests
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "analytics"))

from ratios import (
    debt_to_equity, high_leverage_flag, interest_coverage,
    icr_label, icr_warning_flag, net_debt, asset_turnover,
)


def test_de_debtfree_returns_zero_not_none():
    result = debt_to_equity(borrowings=0, equity_capital=100, reserves=500)
    assert result == 0
    assert result is not None


def test_de_normal_case():
    result = debt_to_equity(borrowings=300, equity_capital=100, reserves=500)
    assert result == 0.5


def test_de_invalid_denominator_returns_none():
    result = debt_to_equity(borrowings=100, equity_capital=0, reserves=-50)
    assert result is None


def test_high_leverage_flag_triggers_for_non_financials():
    assert high_leverage_flag(de_ratio=6.0, is_financials_sector=False) is True


def test_high_leverage_flag_suppressed_for_financials():
    # Same D/E of 6.0, but Financials sector -- flag must NOT trigger
    assert high_leverage_flag(de_ratio=6.0, is_financials_sector=True) is False


def test_icr_interest_zero_returns_none():
    assert interest_coverage(operating_profit=1000, other_income=50, interest=0) is None


def test_icr_label_debt_free():
    assert icr_label(icr_value=None, interest=0) == "Debt Free"


def test_icr_label_normal_value():
    assert icr_label(icr_value=4.5, interest=200) == "4.50x"


def test_icr_warning_flag_triggers_below_threshold():
    assert icr_warning_flag(icr_value=1.2) is True


def test_icr_warning_flag_not_triggered_above_threshold():
    assert icr_warning_flag(icr_value=3.0) is False


def test_net_debt_normal_case():
    assert net_debt(borrowings=500, investments=200) == 300


def test_asset_turnover_zero_assets_returns_none():
    assert asset_turnover(sales=1000, total_assets=0) is None