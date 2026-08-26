"""
N100 Financial Intelligence Platform
Sprint 2, Day 10: CAGR Engine Tests
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "analytics"))

from cagr import compute_cagr, get_fiscal_years_sorted, windowed_cagr


def test_cagr_normal_growth():
    cagr, flag = compute_cagr(start_value=100, end_value=161, years=5)
    assert flag is None
    assert round(cagr, 1) == 10.0


def test_cagr_turnaround_flag():
    cagr, flag = compute_cagr(start_value=-100, end_value=200, years=3)
    assert cagr is None
    assert flag == "TURNAROUND"


def test_cagr_decline_to_loss_flag():
    cagr, flag = compute_cagr(start_value=500, end_value=-50, years=3)
    assert cagr is None
    assert flag == "DECLINE_TO_LOSS"


def test_cagr_both_negative_flag():
    cagr, flag = compute_cagr(start_value=-100, end_value=-50, years=3)
    assert cagr is None
    assert flag == "BOTH_NEGATIVE"


def test_cagr_zero_base_flag():
    cagr, flag = compute_cagr(start_value=0, end_value=500, years=3)
    assert cagr is None
    assert flag == "ZERO_BASE"


def test_cagr_insufficient_years_flag():
    cagr, flag = compute_cagr(start_value=100, end_value=200, years=0)
    assert cagr is None
    assert flag == "INSUFFICIENT"


def test_cagr_none_input_returns_insufficient():
    cagr, flag = compute_cagr(start_value=None, end_value=200, years=5)
    assert cagr is None
    assert flag == "INSUFFICIENT"


def test_get_fiscal_years_excludes_ttm():
    # This directly guards against Sprint 1 Finding 6 resurfacing here
    pairs = [("2020-03", 100), ("TTM", 999), ("2021-03", 110), ("2019-03", 90)]
    result = get_fiscal_years_sorted(pairs)
    years_only = [y for y, v in result]
    assert "TTM" not in years_only
    assert years_only == ["2019-03", "2020-03", "2021-03"]  # sorted chronologically


def test_windowed_cagr_normal_case():
    pairs = [(f"{2015+i}-03", 100 * (1.1 ** i)) for i in range(6)]  # 6 years, ~10% growth
    cagr, flag = windowed_cagr(pairs, window_years=5)
    assert flag is None
    assert round(cagr, 1) == 10.0


def test_windowed_cagr_insufficient_history():
    pairs = [("2022-03", 100), ("2023-03", 110)]  # only 2 years, need 6 for a 5yr window
    cagr, flag = windowed_cagr(pairs, window_years=5)
    assert cagr is None
    assert flag == "INSUFFICIENT"


def test_windowed_cagr_ignores_ttm_when_selecting_latest():
    # TTM should NOT be picked as the "latest" endpoint -- 2024-03 should be
    pairs = [(f"{2019+i}-03", 100 * (1.1 ** i)) for i in range(6)] + [("TTM", 99999)]
    cagr, flag = windowed_cagr(pairs, window_years=5)
    assert flag is None
    assert round(cagr, 1) == 10.0  # NOT skewed by the absurd TTM value