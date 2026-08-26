"""
N100 Financial Intelligence Platform
Sprint 2, Day 10: CAGR Engine

CRITICAL: Any function here that selects "N years ago" or "latest year"
from a company's history MUST exclude year='TTM' first. TTM is a rolling
12-month window, not a fixed fiscal year-end -- comparing it against a
fixed year like '2019-03' would silently produce a meaningless growth
rate. This is Sprint 1 Finding 6, carried forward here as a hard rule.
"""


def compute_cagr(start_value, end_value, years):
    """
    Core CAGR formula: ((end/start)^(1/years) - 1) * 100

    Returns (cagr_value, flag) as a tuple -- flag is None for a normal,
    valid computation, or one of the 6 named edge-case strings.

    Edge cases (spec Day 10, all 6 required):
        start>0, end>0   -> compute normally, flag=None
        start>0, end<0   -> None, flag='DECLINE_TO_LOSS'
        start<0, end>0   -> None, flag='TURNAROUND'
        start<0, end<0   -> None, flag='BOTH_NEGATIVE'
        start==0         -> None, flag='ZERO_BASE'
        years < required -> None, flag='INSUFFICIENT' (checked by caller,
                             since this function doesn't know the required
                             window size on its own)
    """
    if start_value is None or end_value is None or years is None or years <= 0:
        return None, "INSUFFICIENT"

    if start_value == 0:
        return None, "ZERO_BASE"

    if start_value > 0 and end_value > 0:
        cagr = ((end_value / start_value) ** (1 / years) - 1) * 100
        return cagr, None

    if start_value > 0 and end_value < 0:
        return None, "DECLINE_TO_LOSS"

    if start_value < 0 and end_value > 0:
        return None, "TURNAROUND"

    if start_value < 0 and end_value < 0:
        return None, "BOTH_NEGATIVE"

    # end_value == 0 with start_value != 0 -- not explicitly named in spec,
    # treat conservatively as insufficient signal rather than guessing
    return None, "INSUFFICIENT"


def get_fiscal_years_sorted(year_value_pairs):
    """
    Given a list of (year_string, value) tuples for one company/metric,
    return them sorted chronologically, with TTM rows excluded entirely.

    year_value_pairs: list of tuples like [('2019-03', 1000), ('TTM', 1500), ...]
    """
    fiscal_only = [(y, v) for y, v in year_value_pairs if y != "TTM"]
    return sorted(fiscal_only, key=lambda pair: pair[0])


def windowed_cagr(year_value_pairs, window_years):
    """
    Computes CAGR over a given window (3, 5, or 10 years) using the
    LATEST available fiscal year as the end point, and the fiscal year
    closest to (latest - window_years) as the start point.

    Returns (cagr_value, flag). If fewer than window_years of history
    exist, returns (None, 'INSUFFICIENT') rather than guessing with a
    shorter window.
    """
    sorted_pairs = get_fiscal_years_sorted(year_value_pairs)

    if len(sorted_pairs) < window_years + 1:
        return None, "INSUFFICIENT"

    end_year, end_value = sorted_pairs[-1]
    start_year, start_value = sorted_pairs[-(window_years + 1)]

    return compute_cagr(start_value, end_value, window_years)