"""
N100 Financial Intelligence Platform
Sprint 2, Day 11: Cash Flow KPI Tests
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "analytics"))

from cashflow_kpis import (
    free_cash_flow, cfo_quality_score, capex_intensity,
    fcf_conversion_rate, classify_capital_allocation,
)


def test_fcf_normal_case():
    assert free_cash_flow(operating_activity=500, investing_activity=-200) == 300


def test_fcf_negative_allowed():
    assert free_cash_flow(operating_activity=100, investing_activity=-300) == -200


def test_cfo_quality_high():
    score, label = cfo_quality_score([1200, 1300], [1000, 1000])
    assert label == "High Quality"


def test_cfo_quality_accrual_risk():
    score, label = cfo_quality_score([300, 400], [1000, 1000])
    assert label == "Accrual Risk"


def test_capex_intensity_asset_light():
    intensity, label = capex_intensity(investing_activity=-100, sales=10000)
    assert label == "Asset Light"


def test_capex_intensity_capital_intensive():
    intensity, label = capex_intensity(investing_activity=-1000, sales=10000)
    assert label == "Capital Intensive"


def test_fcf_conversion_zero_operating_profit_returns_none():
    assert fcf_conversion_rate(fcf=500, operating_profit=0) is None


def test_capital_allocation_reinvestor():
    label = classify_capital_allocation(cfo=500, cfi=-200, cff=-100)
    assert label == "Reinvestor"


def test_capital_allocation_shareholder_returns():
    label = classify_capital_allocation(cfo=500, cfi=-200, cff=-100, cfo_over_pat=2.0)
    assert label == "Shareholder Returns"


def test_capital_allocation_distress_signal():
    label = classify_capital_allocation(cfo=-100, cfi=50, cff=200)
    assert label == "Distress Signal"


def test_capital_allocation_undetermined_on_missing_sign():
    label = classify_capital_allocation(cfo=None, cfi=-200, cff=-100)
    assert label == "Undetermined"