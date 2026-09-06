"""
N100 Financial Intelligence Platform
Sprint 3, Day 15: Screener Engine Tests
"""

import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "screener"))

from engine import apply_single_filter, apply_outlier_guard, _icr_effective


TEST_CONFIG = {
    "metrics": {
        "roe_min": {"column": "return_on_equity_pct", "direction": "min"},
        "de_max": {"column": "debt_to_equity", "direction": "max", "sector_exempt": "Financials"},
        "icr_min": {"column": "interest_coverage", "direction": "min", "debt_free_as_infinity": True},
    },
    "outlier_guard": {"enabled": True, "max_profit_to_equity_ratio": 5},
}


def make_df():
    return pd.DataFrame({
        "company_id": ["A", "B", "C", "D"],
        "return_on_equity_pct": [20, 10, 25, 5],
        "debt_to_equity": [0.5, 1.5, 6.0, 0.2],
        "broad_sector": ["IT", "IT", "Financials", "IT"],
        "interest_coverage": [4.0, None, 2.0, None],
        "icr_label": ["4.00x", "Debt Free", "2.00x", "Debt Free"],
        "profit_to_equity_ratio": [0.5, 0.3, 0.4, 8.0],
    })


def test_roe_min_filter():
    df = make_df()
    result = apply_single_filter(df, "roe_min", 15, TEST_CONFIG)
    assert set(result["company_id"]) == {"A", "C"}


def test_de_max_exempts_financials():
    df = make_df()
    result = apply_single_filter(df, "de_max", 1.0, TEST_CONFIG)
    # A passes on D/E=0.5, D passes on D/E=0.2, C passes because Financials-exempt despite D/E=6.0
    assert set(result["company_id"]) == {"A", "C", "D"}


def test_icr_debt_free_treated_as_infinity():
    assert _icr_effective({"icr_label": "Debt Free", "interest_coverage": None}) == float("inf")


def test_icr_min_filter_passes_debt_free():
    df = make_df()
    result = apply_single_filter(df, "icr_min", 10, TEST_CONFIG)
    # B and D are Debt Free -> pass any threshold. A has ICR=4.0 -> fails 10 minimum.
    assert set(result["company_id"]) == {"B", "D"}


def test_outlier_guard_removes_extreme_ratio():
    df = make_df()
    result = apply_outlier_guard(df, TEST_CONFIG)
    # D has profit_to_equity_ratio=8.0, exceeds threshold of 5 -> excluded
    assert "D" not in set(result["company_id"])
    assert set(result["company_id"]) == {"A", "B", "C"}