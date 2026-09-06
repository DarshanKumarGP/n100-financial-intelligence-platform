"""
N100 Financial Intelligence Platform
Sprint 3, Day 18: Peer Percentile Tests
"""

import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "analytics"))

from peer import compute_percentiles_for_group


def test_de_percentile_is_inverted():
    df = pd.DataFrame({
        "company_id": ["A", "B", "C"],
        "debt_to_equity": [0.2, 1.0, 3.0],
        "icr_label": [None, None, None],
    })
    result = compute_percentiles_for_group(df, "debt_to_equity")
    # A has the LOWEST D/E -> should get the HIGHEST percentile
    assert result.loc[0] > result.loc[1] > result.loc[2]


def test_roe_percentile_not_inverted():
    df = pd.DataFrame({
        "company_id": ["A", "B", "C"],
        "return_on_equity_pct": [10, 20, 30],
        "icr_label": [None, None, None],
    })
    result = compute_percentiles_for_group(df, "return_on_equity_pct")
    # C has the HIGHEST ROE -> should get the HIGHEST percentile
    assert result.loc[2] > result.loc[1] > result.loc[0]


def test_icr_debt_free_ranks_at_top():
    df = pd.DataFrame({
        "company_id": ["A", "B", "C"],
        "interest_coverage": [2.0, 5.0, None],
        "icr_label": ["2.00x", "5.00x", "Debt Free"],
    })
    result = compute_percentiles_for_group(df, "interest_coverage")
    # C is Debt Free -> should rank highest, above even the 5.0x company
    assert result.loc[2] == result.max()