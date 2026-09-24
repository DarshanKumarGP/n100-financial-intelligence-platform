"""
N100 Financial Intelligence Platform
Sprint 6, Day 45: Regression tests for pros_cons_generator.py

Location: tests/nlp/test_pros_cons_generator.py

No test coverage existed for this module before this file -- a real
gap, since it's likely why C11 (Net Debt > 3x EBITDA) was never built
as its own testable function (it was inlined in main() instead) and
why con_06_low_icr's missing is_financials exemption went undetected
from Sprint 5 Day 30 through Sprint 6 Day 44's docstring/ruff pass,
only caught during Day 45's manual tearsheet visual check (AC-10).

These tests guard against both gaps recurring:
  - con_06_low_icr must exempt financials
  - con_11_high_net_debt exists as its own function and exempts financials
  - con_01_high_de (already correct) is included as a reference/baseline
    check, confirming the exemption pattern these tests assert against
    is the real, established one.

KNOWN, DEFERRED LIMITATION (not covered by a test here, intentionally):
con_10_low_roce has no is_financials exemption, the same structural gap
as con_06/con_11 -- deferred per project decision, documented in
notebooks/sprint6_retro.md, not silently dropped.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "nlp"))

from pros_cons_generator import (
    con_01_high_de,
    con_06_low_icr,
    con_11_high_net_debt,
)


def test_con_01_high_de_exempts_financials():
    latest = pd.Series({"debt_to_equity": 7.0})
    assert con_01_high_de(latest, is_financials=True) is None


def test_con_01_high_de_flags_non_financials():
    latest = pd.Series({"debt_to_equity": 3.0})
    result = con_01_high_de(latest, is_financials=False)
    assert result is not None
    confidence, text = result
    assert confidence > 60
    assert "Debt-to-equity" in text


def test_con_06_low_icr_exempts_financials():
    """
    Regression test: HDFCBANK previously showed 'Interest coverage
    ratio below 1.5x' as a con despite being a bank -- con_06_low_icr
    had no is_financials parameter at all before this fix.
    """
    latest = pd.Series({"interest_coverage": 0.8, "icr_label": "Weak"})
    assert con_06_low_icr(latest, is_financials=True) is None


def test_con_06_low_icr_flags_non_financials():
    latest = pd.Series({"interest_coverage": 0.8, "icr_label": "Weak"})
    result = con_06_low_icr(latest, is_financials=False)
    assert result is not None
    confidence, text = result
    assert confidence > 60
    assert "Interest coverage" in text


def test_con_06_low_icr_still_respects_debt_free_label():
    latest = pd.Series({"interest_coverage": None, "icr_label": "Debt Free"})
    assert con_06_low_icr(latest, is_financials=False) is None


def test_con_11_high_net_debt_exists_as_own_function():
    """
    Regression test: C11 was previously inlined in main() rather than
    built as its own function like every other rule -- confirmed via
    `grep -n "def con_" pros_cons_generator.py` returning no con_11
    match before this fix. This test just importing the function
    successfully is itself part of the regression guard.
    """
    latest = pd.Series({"net_debt_cr": 10000})
    pl_latest = pd.Series({"operating_profit": 2000})
    result = con_11_high_net_debt(latest, pl_latest, is_financials=False)
    assert result is not None
    confidence, text = result
    assert confidence > 60
    assert "Net debt" in text


def test_con_11_high_net_debt_exempts_financials():
    """
    Regression test: HDFCBANK previously showed 'Net debt exceeding 3
    times EBITDA' as a con despite being a bank -- the inlined C11
    logic had no is_financials check at all before this fix.
    """
    latest = pd.Series({"net_debt_cr": 10000})
    pl_latest = pd.Series({"operating_profit": 2000})
    assert con_11_high_net_debt(latest, pl_latest, is_financials=True) is None


def test_con_11_high_net_debt_returns_none_below_threshold():
    latest = pd.Series({"net_debt_cr": 3000})
    pl_latest = pd.Series({"operating_profit": 2000})
    assert con_11_high_net_debt(latest, pl_latest, is_financials=False) is None


def test_con_11_high_net_debt_returns_none_on_missing_data():
    latest = pd.Series({"net_debt_cr": None})
    pl_latest = pd.Series({"operating_profit": 2000})
    assert con_11_high_net_debt(latest, pl_latest, is_financials=False) is None