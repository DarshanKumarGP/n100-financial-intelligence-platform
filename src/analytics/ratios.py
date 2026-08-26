"""
N100 Financial Intelligence Platform
Sprint 2, Day 8: Profitability Ratios

All functions take raw numeric inputs (not DB rows) so they're independently
testable. Day 12 wires these to actual company-year rows from SQLite.
"""


def net_profit_margin(net_profit, sales):
    """NPM = net_profit / sales * 100. None if sales is 0 or missing."""
    if sales is None or sales == 0 or net_profit is None:
        return None
    return (net_profit / sales) * 100


def operating_profit_margin(operating_profit, sales):
    """
    Computed OPM = operating_profit / sales * 100.
    Per Sprint 1 Finding 4: this is the ONLY OPM value the Ratio Engine
    should trust. The source opm_percentage field is confirmed unreliable
    for 21 companies (mainly Financials sector, where OPM isn't a
    meaningful metric at all -- see spec Section 28).
    """
    if sales is None or sales == 0 or operating_profit is None:
        return None
    return (operating_profit / sales) * 100


def opm_cross_check(computed_opm, source_opm):
    """
    Compare computed OPM against the source field, purely for logging.
    Returns True if they differ by more than 1 percentage point (a
    mismatch worth recording in ratio_edge_cases.log on Day 13),
    False if they agree, None if either value is missing.
    """
    if computed_opm is None or source_opm is None:
        return None
    return abs(computed_opm - source_opm) > 1.0


def return_on_equity(net_profit, equity_capital, reserves):
    """ROE = net_profit / (equity_capital + reserves) * 100. None if <= 0."""
    if equity_capital is None or reserves is None or net_profit is None:
        return None
    equity_plus_reserves = equity_capital + reserves
    if equity_plus_reserves <= 0:
        return None
    return (net_profit / equity_plus_reserves) * 100


def ebit(operating_profit, depreciation):
    """EBIT = operating_profit - depreciation. Core operational earnings."""
    if operating_profit is None:
        return None
    return operating_profit - (depreciation or 0)


def return_on_capital_employed(operating_profit, depreciation,
                                equity_capital, reserves, borrowings,
                                is_financials_sector=False):
    """
    ROCE = EBIT / (equity + reserves + borrowings) * 100.
    None if the denominator is <= 0.

    is_financials_sector doesn't change the formula -- it's a signal for
    Day 13's interpretation layer, since Financials companies need a
    sector-relative benchmark instead of the standard >15%/>25% threshold
    (spec Section 28: D/E is structurally high for banks/NBFCs, so a
    universal ROCE threshold would misjudge them). The raw number is
    still computed the same way for everyone; only how it's judged differs.
    """
    ebit_val = ebit(operating_profit, depreciation)
    if ebit_val is None or equity_capital is None or reserves is None or borrowings is None:
        return None
    capital_employed = equity_capital + reserves + borrowings
    if capital_employed <= 0:
        return None
    return (ebit_val / capital_employed) * 100


def return_on_assets(net_profit, total_assets):
    """ROA = net_profit / total_assets * 100. None if total_assets is 0."""
    if total_assets is None or total_assets == 0 or net_profit is None:
        return None
    return (net_profit / total_assets) * 100


def debt_to_equity(borrowings, equity_capital, reserves):
    """
    D/E = borrowings / (equity_capital + reserves).
    Returns 0 (NOT None) when borrowings=0 -- debt-free is a real,
    meaningful value, unlike ROE's "undefined" zero-equity case.
    None only if the denominator itself is invalid (<=0).
    """
    if equity_capital is None or reserves is None or borrowings is None:
        return None
    equity_plus_reserves = equity_capital + reserves
    if equity_plus_reserves <= 0:
        return None
    return borrowings / equity_plus_reserves


def high_leverage_flag(de_ratio, is_financials_sector):
    """
    True if D/E > 5 AND the company is NOT in the Financials sector.
    Per spec Day 9 + Sprint 1 findings: high D/E is structurally normal
    for banks/NBFCs/insurers, so this flag would be meaningless noise
    if applied to them -- it's deliberately suppressed for that sector.
    """
    if de_ratio is None or is_financials_sector:
        return False
    return de_ratio > 5


def interest_coverage(operating_profit, other_income, interest):
    """
    ICR = (operating_profit + other_income) / interest.
    None when interest=0 -- see icr_label() for the paired display value.
    """
    if interest is None or interest == 0 or operating_profit is None:
        return None
    return (operating_profit + (other_income or 0)) / interest


def icr_label(icr_value, interest):
    """
    Paired display column for ICR. When interest=0 (debt-free), the raw
    ICR is None/undefined -- but "None" isn't informative to a reader.
    This gives an explicit human-readable label instead.
    """
    if interest is None or interest == 0:
        return "Debt Free"
    if icr_value is None:
        return "Unknown"
    return f"{icr_value:.2f}x"


def icr_warning_flag(icr_value):
    """True if ICR < 1.5 -- at risk of not covering interest payments."""
    if icr_value is None:
        return False
    return icr_value < 1.5


def net_debt(borrowings, investments):
    """Net Debt = borrowings - investments (investments as liquid asset proxy)."""
    if borrowings is None:
        return None
    return borrowings - (investments or 0)


def asset_turnover(sales, total_assets):
    """Asset Turnover = sales / total_assets. None if total_assets=0."""
    if total_assets is None or total_assets == 0 or sales is None:
        return None
    return sales / total_assets