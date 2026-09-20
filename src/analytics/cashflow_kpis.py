"""
N100 Financial Intelligence Platform
Sprint 2, Day 11: Cash Flow KPIs & Capital Allocation Classifier
Sprint 5, Day 31: Distress Signal & Deleveraging Detection (appended below,
existing functions unchanged)

2026-09 refactor: cfo_quality_score()'s labeling thresholds extracted into
_cfo_quality_label() so cashflow_intelligence.py can apply the same
thresholds to a pre-computed ratio (financial_ratios.cfo_pat_ratio_5yr)
without duplicating threshold logic in two places. Pure refactor -- no
behavior change, cfo_quality_score()'s return values are identical.
"""


def free_cash_flow(operating_activity, investing_activity):
    """FCF = CFO + CFI. Negative values are valid and meaningful."""
    if operating_activity is None or investing_activity is None:
        return None
    return operating_activity + investing_activity


def _cfo_quality_label(avg_ratio):
    """Shared thresholds: >1.0 High Quality, 0.5-1.0 Moderate, <0.5 Accrual Risk."""
    if avg_ratio > 1.0:
        return "High Quality"
    elif avg_ratio >= 0.5:
        return "Moderate"
    else:
        return "Accrual Risk"


def cfo_quality_score(cfo_values_5yr, pat_values_5yr):
    """
    Average CFO/PAT ratio over up to 5 years of matched (CFO, PAT) pairs.
    >1.0 = High Quality, 0.5-1.0 = Moderate, <0.5 = Accrual Risk.
    Returns (score, label). None/None if no valid PAT>0 years exist to average.
    """
    ratios = []
    for cfo, pat in zip(cfo_values_5yr, pat_values_5yr):
        if cfo is None or pat is None or pat == 0:
            continue
        ratios.append(cfo / pat)

    if not ratios:
        return None, None

    avg_ratio = sum(ratios) / len(ratios)
    label = _cfo_quality_label(avg_ratio)

    return avg_ratio, label


def capex_intensity(investing_activity, sales):
    """
    CapEx Intensity = abs(investing_activity) / sales * 100.
    <3% = Asset Light, 3-8% = Moderate, >8% = Capital Intensive.
    Returns (value, label). None/None if sales is 0 or missing.
    """
    if sales is None or sales == 0 or investing_activity is None:
        return None, None

    intensity = abs(investing_activity) / sales * 100

    if intensity < 3:
        label = "Asset Light"
    elif intensity <= 8:
        label = "Moderate"
    else:
        label = "Capital Intensive"

    return intensity, label


def fcf_conversion_rate(fcf, operating_profit):
    """FCF Conversion = FCF / operating_profit * 100. None if operating_profit=0."""
    if operating_profit is None or operating_profit == 0 or fcf is None:
        return None
    return (fcf / operating_profit) * 100


def _sign(value):
    """Returns '+', '-', or None for missing/zero-ambiguous input."""
    if value is None:
        return None
    if value > 0:
        return "+"
    if value < 0:
        return "-"
    return None  # exactly zero is genuinely ambiguous -- don't force a sign


def classify_capital_allocation(cfo, cfi, cff, cfo_over_pat=None):
    """
    Classifies a company-year into one of 8 capital allocation patterns
    based on the signs of (CFO, CFI, CFF), per spec Day 11.

    Two patterns share the identical sign combination (+,-,-):
      - 'Reinvestor' (the default case for +,-,-)
      - 'Shareholder Returns' (same signs, but CFO/PAT is notably high,
        indicating the company generates more cash than it needs for
        operations and is likely returning the excess to shareholders)
    cfo_over_pat is optional; if not provided, (+,-,-) always classifies
    as 'Reinvestor' rather than guessing at the distinction.

    Returns the pattern label string, or 'Undetermined' if any sign is
    missing/zero (spec doesn't define a 9th catch-all case, so this is
    an explicit "we don't know" rather than a forced guess).
    """
    cfo_sign = _sign(cfo)
    cfi_sign = _sign(cfi)
    cff_sign = _sign(cff)

    if None in (cfo_sign, cfi_sign, cff_sign):
        return "Undetermined"

    pattern = (cfo_sign, cfi_sign, cff_sign)

    if pattern == ("+", "-", "-"):
        # Ambiguous case -- use the CFO/PAT threshold if given
        if cfo_over_pat is not None and cfo_over_pat > 1.5:
            return "Shareholder Returns"
        return "Reinvestor"
    if pattern == ("+", "+", "-"):
        return "Liquidating Assets"
    if pattern == ("-", "+", "+"):
        return "Distress Signal"
    if pattern == ("-", "-", "+"):
        return "Growth Funded by Debt"
    if pattern == ("+", "+", "+"):
        return "Cash Accumulator"
    if pattern == ("-", "-", "-"):
        return "Pre-Revenue"
    if pattern == ("+", "-", "+"):
        return "Mixed"
    if pattern == ("-", "+", "-"):
        # Not explicitly named in spec's 8 patterns -- log as Undetermined
        # rather than inventing a label the spec never defined
        return "Undetermined"

    return "Undetermined"


# ============================================================
# SPRINT 5, DAY 31 ADDITIONS
# ============================================================

def detect_distress_signal(cfo, cff):
    """
    Flags CFO < 0 AND CFF > 0 in the latest year -- raising cash from
    financing while operations burn cash.

    Deliberately independent of classify_capital_allocation()'s
    "Distress Signal" pattern label -- that label is the narrower
    3-variable (-,+,+) sign combination. This function implements the
    spec's plain 2-variable definition instead, which also correctly
    catches (-,-,+) "Growth Funded by Debt" companies -- companies the
    classifier's existing label alone would miss. Confirmed intentional
    naming overlap; documented here and in the Day 31 retro notes so
    the two are never confused as the same check.

    Returns True/False, or None if either input is missing.
    """
    if cfo is None or cff is None:
        return None
    return cfo < 0 and cff > 0


def detect_deleveraging(cff, borrowings_current, borrowings_prior):
    """
    Flags CFF < 0 AND borrowings declining year-over-year -- actively
    paying down debt.

    Returns True/False, or None if any input is missing.
    """
    if cff is None or borrowings_current is None or borrowings_prior is None:
        return None
    return cff < 0 and borrowings_current < borrowings_prior