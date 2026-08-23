"""
N100 Financial Intelligence Platform
Sprint 1, Day 2: Tests for normalize_year() and normalize_ticker()

20 test cases for normalize_year(), 16 for normalize_ticker() -- matching
the spec's Day 2 exit criteria of 35+ unit tests.

Run from the project root:
    pytest tests/etl/test_normalise.py -v
"""

import sys
from pathlib import Path

# Make src/ importable without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "etl"))

from normaliser import normalize_year, normalize_ticker


# ============================================================
# normalize_year() -- 20 tests
# ============================================================

def test_year_mar23():
    assert normalize_year("Mar-23") == "2023-03"

def test_year_mar_space_23():
    assert normalize_year("Mar 23") == "2023-03"

def test_year_march_full_2023():
    assert normalize_year("March-2023") == "2023-03"

def test_year_bare_2023():
    assert normalize_year("2023") == "2023-03"

def test_year_fy24():
    assert normalize_year("FY24") == "2024-03"

def test_year_fy_full_2024():
    assert normalize_year("FY2024") == "2024-03"

def test_year_dec22():
    assert normalize_year("Dec-22") == "2022-12"

def test_year_jun23():
    assert normalize_year("Jun-23") == "2023-06"

def test_year_already_normalised():
    assert normalize_year("2023-03") == "2023-03"

def test_year_garbage():
    assert normalize_year("xyz") == "PARSE_ERROR"

def test_year_empty_string():
    assert normalize_year("") == "PARSE_ERROR"

def test_year_none():
    assert normalize_year(None) == "PARSE_ERROR"

def test_year_lowercase_month():
    assert normalize_year("mar-23") == "2023-03"

def test_year_september_full():
    assert normalize_year("September-2021") == "2021-09"

def test_year_jan23():
    assert normalize_year("Jan-23") == "2023-01"

def test_year_nov_full_year():
    assert normalize_year("Nov-2020") == "2020-11"

def test_year_whitespace_padding():
    assert normalize_year("  Mar-23  ") == "2023-03"

def test_year_invalid_month_name():
    assert normalize_year("Xyz-23") == "PARSE_ERROR"

def test_year_two_digit_alone():
    # "23" alone is ambiguous/too short -- must NOT be silently accepted
    assert normalize_year("23") == "PARSE_ERROR"

def test_year_fy_lowercase():
    assert normalize_year("fy23") == "2023-03"

def test_year_ttm():
    # Found during Day 2 loading: 100 real rows in profitandloss.xlsx.
    # TTM must be recognised, not rejected -- but NOT converted to a
    # fake YYYY-MM, since it's a rolling window, not a fixed year-end.
    assert normalize_year("TTM") == "TTM"

def test_year_ttm_lowercase():
    assert normalize_year("ttm") == "TTM"

def test_year_stub_period_rejected():
    # Found during Day 2 loading: 2 rows, likely a 9-month transition
    # period. Too rare and ambiguous to guess at -- correctly rejected.
    assert normalize_year("Mar 2016 9m") == "PARSE_ERROR"

def test_year_ambiguous_suffix_rejected():
    # Found during Day 2 loading: 1 row, meaning unclear. Correctly
    # rejected rather than silently misparsed.
    assert normalize_year("Mar 2023 15") == "PARSE_ERROR"


# ============================================================
# normalize_ticker() -- 16 tests
# ============================================================

def test_ticker_strip():
    assert normalize_ticker(" TCS ") == "TCS"

def test_ticker_lower():
    assert normalize_ticker("tcs") == "TCS"

def test_ticker_hyphen_preserved():
    assert normalize_ticker("bajaj-auto") == "BAJAJ-AUTO"

def test_ticker_ampersand_preserved():
    assert normalize_ticker("m&m") == "M&M"

def test_ticker_already_clean():
    assert normalize_ticker("TCS") == "TCS"

def test_ticker_mixed_case():
    assert normalize_ticker("InFy") == "INFY"

def test_ticker_none():
    assert normalize_ticker(None) is None

def test_ticker_empty_string():
    assert normalize_ticker("") is None

def test_ticker_whitespace_only():
    assert normalize_ticker("   ") is None

def test_ticker_leading_whitespace():
    assert normalize_ticker("  HDFCBANK") == "HDFCBANK"

def test_ticker_trailing_whitespace():
    assert normalize_ticker("HDFCBANK  ") == "HDFCBANK"

def test_ticker_alphanumeric_start():
    assert normalize_ticker("3m india") == "3M INDIA"

def test_ticker_single_char():
    assert normalize_ticker("a") == "A"

def test_ticker_multiple_hyphens():
    assert normalize_ticker("tata-steel-ltd") == "TATA-STEEL-LTD"

def test_ticker_dot_preserved():
    assert normalize_ticker("reliance.ind") == "RELIANCE.IND"

def test_ticker_agtl_corrected_to_atgl():
    # Confirmed source-data typo in cashflow.xlsx only (see
    # KNOWN_TICKER_CORRECTIONS comment in normaliser.py). Not a guess --
    # verified against profitandloss.xlsx and balancesheet.xlsx, where
    # ATGL has 8 rows each and AGTL has 0.
    assert normalize_ticker("AGTL") == "ATGL"
    assert normalize_ticker("agtl") == "ATGL"