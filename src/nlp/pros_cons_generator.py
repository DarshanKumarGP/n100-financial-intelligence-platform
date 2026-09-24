"""
N100 Financial Intelligence Platform
Sprint 5, Day 30: Auto Pros/Cons Generator

12 pro rules + 12 con rules, confidence-scored, outlier-guarded.
Only entries with confidence > 60% are included in the final output,
per spec.

Outlier guard: HAL, BEL, INDIGO (Sprint 2 Finding 5) have raw ROE/ROCE
values inflated by tiny equity bases (3816%, 4744%, 892%). Any rule
keyed on ROE/ROCE magnitude is skipped for these companies -- not
because their ROE number is technically false, but because it doesn't
reflect genuine business quality and would produce a misleading "pro."

Fallback rules (three tiers, applied only when the 12 primary rules
found nothing for that pro/con type):
  Tier 1 -- pro: stable D/E (P13) or plain profitability (P14)
            con: premium to sector median P/E (C13)
  Tier 2 -- con: low dividend yield (C14)
  Tier 3 -- con: FCF conversion < 100% of operating profit (C15), then
            CFO/PAT ratio < 0.5 i.e. Accrual Risk (C16) -- same
            definition Sprint 5 Day 31 introduces for cfo_quality_label,
            used here for the residual case where fcf_conversion_pct
            is null due to a source-data gap (confirmed 2026-09: PNB
            has operating_profit = None across all 12 years in
            profitandloss, which fcf_conversion_rate() correctly can't
            divide by -- a genuine PNB-specific data gap, not a bug in
            the function).

History of fallback rollout (2026-09):
  - First run (12 primary rules only): 3 companies missing a pro
    (BHEL, GODREJCP, JINDALSTEL), 33 missing a con (TCS, NESTLEIND,
    MARUTI, SUNPHARMA, DMART, etc. -- genuinely strong performers).
  - Added P13/P14/C13/C14: pros closed to 0 missing. Cons dropped to
    31 missing -- traced to con_13 always returning None because it
    read pe_ratio from the financial_ratios `latest` row, which has no
    pe_ratio column (that field only exists in market_cap). Fixed by
    sourcing pe_ratio from mc_latest, same place dividend_yield already
    comes from.
  - After the pe_ratio fix: cons dropped to 18 missing. Verified via
    real P/E-vs-sector-median and dividend-yield data that these 18 are
    genuinely fairly-valued, decent-yield companies -- not a bug.
  - Checked composite_quality_score as a possible tier-3 metric: only
    5/18 fell below sector median, so it would have been dishonest for
    the other 13 (they beat their sector median). Rejected.
  - Added C15 (fcf_conversion_pct < 100): covered 17/18. Verified real,
    non-null values, including honest negative-conversion cases like
    AMBUJACEM (-51%) and M&M (-45%).
  - Last holdout: PNB. Confirmed root cause: operating_profit is None
    for all 12 of PNB's profitandloss rows (unlike other financials --
    HDFCBANK, ICICIBANK etc. have real values), so fcf_conversion_rate()
    correctly returns None. Added C16 using cfo_pat_ratio_5yr (already
    populated, 0 nulls across all 92 companies) < 0.5.
  - Reached 0/0 missing pro/con. Spot-check then caught a labeling bug:
    every fallback con was hardcoded to rule_id "C13_fallback" even
    when C14/C15/C16 was the one that actually fired (confirmed on
    PNB, which had C16 text under a "C13_fallback" label). Fixed by
    tracking which tier actually returned a result.

2026-09 fix (Sprint 6, Day 45 acceptance-gate visual check): reviewing
tearsheet PDFs for AC-10 surfaced two real gaps in con_06 and C11,
found via HDFCBANK showing "Interest coverage ratio below 1.5x" and
"Net debt exceeding 3 times EBITDA" as cons -- both metrics assume a
non-financial capital structure and are structurally near-meaningless
for a bank (same reasoning already applied to con_01_high_de's
is_financials exemption, and to the screener's D/E sector exemption
since Sprint 3). con_06_low_icr had no exemption at all. Separately,
C11 (Net Debt > 3x EBITDA) was never built as its own testable
function like every other rule -- it was inlined directly in main(),
which is likely why its missing financials exemption went unnoticed:
no docstring scan or test file ever covered it, since it wasn't a
named function. Fixed both: con_06_low_icr now takes is_financials and
exempts financials, and the inline C11 logic is now its own
con_11_high_net_debt() function with the same exemption, wired into
main() the same way every other con rule is.
"""

import os
import sqlite3

import pandas as pd

DB_PATH = "data/nifty100.db"
OUTLIER_THRESHOLD = 5  # net_profit / equity_base ratio


def clamp_confidence(value):
    """Clamp a computed confidence score to the valid 0-100 range."""
    return max(0, min(100, value))


def load_all_company_data(conn):
    """Loads everything needed, keyed by company_id, as a dict of DataFrames/rows."""
    fr = pd.read_sql(
        """
        SELECT * FROM financial_ratios WHERE year != 'TTM' ORDER BY company_id, year
    """,
        conn,
    )
    # cfo_pat_ratio_5yr can come back as an object/string dtype from SQLite
    # (confirmed 2026-09) -- coerce to numeric so comparisons behave correctly.
    fr["cfo_pat_ratio_5yr"] = pd.to_numeric(fr["cfo_pat_ratio_5yr"], errors="coerce")

    pl = pd.read_sql(
        """
        SELECT company_id, year, sales, net_profit, eps FROM profitandloss
        WHERE year != 'TTM' ORDER BY company_id, year
    """,
        conn,
    )
    bs = pd.read_sql(
        """
        SELECT company_id, year, total_assets, borrowings FROM balancesheet
        ORDER BY company_id, year
    """,
        conn,
    )
    sectors = dict(
        conn.execute("SELECT company_id, broad_sector FROM sectors;").fetchall()
    )
    mc_latest = pd.read_sql(
        """
        SELECT company_id, dividend_yield_pct, pe_ratio FROM market_cap
        WHERE (company_id, year) IN (
            SELECT company_id, MAX(year) FROM market_cap GROUP BY company_id
        )
    """,
        conn,
    )

    # Compute outlier flag per company using latest year's ROE magnitude
    outliers = set()
    for company_id, group in fr.groupby("company_id"):
        latest = group.sort_values("year").iloc[-1]
        if (
            pd.notna(latest.get("return_on_equity_pct"))
            and latest["return_on_equity_pct"] > 500
        ):
            outliers.add(company_id)

    return fr, pl, bs, sectors, mc_latest, outliers


# ============================================================
# PRO RULES
# ============================================================


def pro_01_roe_sustained(history, is_outlier):
    """Pro rule 1: flag companies with ROE above 20% sustained for 3+ years."""
    if is_outlier or len(history) < 3:
        return None
    last3 = history.tail(3)["return_on_equity_pct"]
    if last3.notna().all() and (last3 > 20).all():
        margin = last3.mean() - 20
        return clamp_confidence(70 + margin), (
            "Consistently high return on equity above 20% demonstrates exceptional capital efficiency"
        )
    return None


def pro_02_fcf_positive_5yr(history):
    """Pro rule 2: flag companies with positive free cash flow for 5+ consecutive years."""
    if len(history) < 5:
        return None
    last5 = history.tail(5)["free_cash_flow_cr"]
    if last5.notna().all() and (last5 > 0).all():
        return (
            80,
            "Strong free cash flow generation over 5 years signals healthy business fundamentals",
        )
    return None


def pro_03_debt_free(latest):
    """Pro rule 3: flag companies with D/E of 0 in the latest year."""
    de = latest.get("debt_to_equity")
    if pd.notna(de) and de < 0.01:
        return (
            85,
            "Debt-free balance sheet provides financial flexibility and eliminates interest burden",
        )
    return None


def pro_04_revenue_cagr_15(latest):
    """Pro rule 4: flag companies with 5-year revenue CAGR above 15%."""
    v = latest.get("revenue_cagr_5yr")
    if pd.notna(v) and v > 15:
        return (
            clamp_confidence(70 + (v - 15)),
            "Revenue growing at above 15% CAGR over 5 years reflects strong business momentum",
        )
    return None


def pro_05_opm_25(latest):
    """Pro rule 5: flag companies with operating profit margin above 25% in the latest year."""
    v = latest.get("operating_profit_margin_pct")
    if pd.notna(v) and v > 25:
        return (
            clamp_confidence(70 + (v - 25) / 2),
            "Operating profit margin above 25% indicates strong pricing power and cost discipline",
        )
    return None


def pro_06_pat_cagr_20(latest):
    """Pro rule 6: flag companies with 5-year PAT CAGR above 20%."""
    v = latest.get("pat_cagr_5yr")
    if pd.notna(v) and v > 20:
        return (
            clamp_confidence(70 + (v - 20)),
            "Net profit compounding at above 20% over 5 years creates significant shareholder value",
        )
    return None


def pro_07_icr_high(latest):
    """Pro rule 7: flag companies with interest coverage ratio above 10, or debt-free."""
    if latest.get("icr_label") == "Debt Free":
        return (
            90,
            "Very high interest coverage ratio reflects negligible financial stress from debt servicing",
        )
    icr = latest.get("interest_coverage")
    if pd.notna(icr) and icr > 10:
        return (
            clamp_confidence(70 + (icr - 10)),
            "Very high interest coverage ratio reflects negligible financial stress from debt servicing",
        )
    return None


def pro_08_dividend_yield(latest, dividend_yield):
    """Pro rule 8: flag companies with dividend yield above 2% and positive FCF."""
    fcf = latest.get("free_cash_flow_cr")
    if pd.notna(dividend_yield) and dividend_yield > 2 and pd.notna(fcf) and fcf > 0:
        return (
            clamp_confidence(70 + (dividend_yield - 2) * 3),
            "Consistent dividend yield above 2% backed by positive free cash flow",
        )
    return None


def pro_09_eps_cagr_15(latest):
    """Pro rule 9: flag companies with 5-year EPS CAGR above 15%."""
    v = latest.get("eps_cagr_5yr")
    if pd.notna(v) and v > 15:
        return (
            clamp_confidence(70 + (v - 15)),
            "Earnings per share growing above 15% CAGR indicates strong earnings quality and compounding",
        )
    return None


def pro_10_roe_improving(history, is_outlier):
    """Pro rule 10: flag companies with ROE improving for 3 consecutive years."""
    if is_outlier or len(history) < 3:
        return None
    last3 = history.tail(3)["return_on_equity_pct"]
    if last3.notna().all() and last3.is_monotonic_increasing:
        return (
            75,
            "Return on equity improving for 3 consecutive years shows strengthening business quality",
        )
    return None


def pro_11_operating_leverage(latest):
    """Pro rule 11: flag companies where 5-year revenue CAGR is below PAT CAGR, indicating operating leverage."""
    rev = latest.get("revenue_cagr_5yr")
    pat = latest.get("pat_cagr_5yr")
    if pd.notna(rev) and pd.notna(pat) and pat > rev and rev > 0:
        return (
            clamp_confidence(65 + (pat - rev)),
            "Revenue growing slower than profits shows improving operating leverage and scale benefits",
        )
    return None


def pro_12_assets_growing_debt_declining(bs_history):
    """Pro rule 12: flag companies with growing assets alongside declining debt."""
    if len(bs_history) < 3:
        return None
    last3 = bs_history.tail(3)
    if (
        last3["total_assets"].is_monotonic_increasing
        and last3["borrowings"].is_monotonic_decreasing
    ):
        return (
            78,
            "Growing asset base funded by internal accruals reflects self-sustaining growth",
        )
    return None


def pro_13_fallback_stable_de(latest):
    """
    Fallback: even an unremarkable company usually has a manageable,
    non-alarming D/E -- a real, mild positive rather than a fabricated
    strength.
    """
    de = latest.get("debt_to_equity")
    if pd.notna(de) and 0 <= de <= 1.0:
        return (
            62,
            "Manageable debt-to-equity ratio indicates the balance sheet is not under financial stress",
        )
    return None


def pro_14_fallback_positive_profit(pl_latest):
    """
    Fallback: reporting a genuine profit (even a modest one) is a real,
    defensible positive for companies that don't qualify under any of
    the 12 stronger pro rules.
    """
    v = pl_latest.get("net_profit")
    if pd.notna(v) and v > 0:
        return 61, "Company remains profitable in its most recent financial year"
    return None


# ============================================================
# CON RULES
# ============================================================


def con_01_high_de(latest, is_financials):
    """Con rule 1: flag non-financial companies with D/E above 2.0."""
    if is_financials:
        return None
    de = latest.get("debt_to_equity")
    if pd.notna(de) and de > 2.0:
        return (
            clamp_confidence(70 + (de - 2) * 5),
            f"Debt-to-equity ratio of {de:.1f} is elevated for a non-financial company and warrants monitoring",
        )
    return None


def con_02_fcf_negative_3yr(history):
    """Con rule 2: flag companies with negative free cash flow for 3 consecutive years."""
    if len(history) < 3:
        return None
    last3 = history.tail(3)["free_cash_flow_cr"]
    if last3.notna().all() and (last3 < 0).all():
        return (
            80,
            "Free cash flow negative for 3 consecutive years raises concern about cash generation quality",
        )
    return None


def con_03_opm_declining(history):
    """Con rule 3: flag companies with operating margin declining for 3 consecutive years."""
    if len(history) < 3:
        return None
    last3 = history.tail(3)["operating_profit_margin_pct"]
    if last3.notna().all() and last3.is_monotonic_decreasing:
        return (
            72,
            "Operating margins declining for 3 consecutive years suggest pricing or cost pressure",
        )
    return None


def con_04_net_loss(pl_latest):
    """Con rule 4: flag companies with a net loss in the latest year."""
    v = pl_latest.get("net_profit")
    if pd.notna(v) and v < 0:
        return 90, "Company reported a net loss in the most recent financial year"
    return None


def con_05_revenue_declining(pl_history):
    """Con rule 5: flag companies with revenue declining for 2+ consecutive years."""
    if len(pl_history) < 2:
        return None
    last_n = pl_history.tail(3)["sales"]
    if len(last_n) >= 2 and last_n.notna().all() and last_n.is_monotonic_decreasing:
        return (
            75,
            "Revenue contraction over 2 consecutive years indicates demand weakness or market share loss",
        )
    return None


def con_06_low_icr(latest, is_financials):
    """Con rule 6: flag non-financial companies with interest coverage ratio below 1.5."""
    if is_financials:
        return None
    if latest.get("icr_label") == "Debt Free":
        return None
    icr = latest.get("interest_coverage")
    if pd.notna(icr) and icr < 1.5:
        return (
            clamp_confidence(85 - icr * 5),
            "Interest coverage ratio below 1.5x indicates the company is at risk of not meeting its debt obligations",
        )
    return None


def con_07_high_payout(latest):
    """Con rule 7: flag companies with dividend payout ratio above 100%."""
    v = latest.get("dividend_payout_ratio_pct")
    if pd.notna(v) and v > 100:
        return (
            clamp_confidence(70 + (v - 100) / 5),
            "Dividend payout ratio above 100% means the company is paying dividends from reserves, which is unsustainable",
        )
    return None


def con_08_de_rising(history):
    """Con rule 8: flag companies with D/E rising for 3 consecutive years."""
    if len(history) < 3:
        return None
    last3 = history.tail(3)["debt_to_equity"]
    if (
        last3.notna().all()
        and last3.is_monotonic_increasing
        and last3.iloc[-1] > last3.iloc[0]
    ):
        return (
            70,
            "Rising debt-to-equity ratio over 3 years suggests increasing financial leverage risk",
        )
    return None


def con_09_eps_declining(pl_history):
    """Con rule 9: flag companies with EPS declining for 3 consecutive years."""
    if len(pl_history) < 3:
        return None
    last3 = pl_history.tail(3)["eps"]
    if last3.notna().all() and last3.is_monotonic_decreasing:
        return (
            75,
            "Earnings per share declining for 3 consecutive years reflects deteriorating profitability",
        )
    return None


def con_10_low_roce(latest, is_outlier):
    """Con rule 10: flag companies with ROCE below 10%.

    KNOWN LIMITATION (deferred, Sprint 6 Day 45): unlike con_01/con_06/
    con_11, this rule has no is_financials exemption. ROCE's borrowings
    component largely reflects customer deposits for a bank, not
    discretionary leverage -- the same structural mismatch already
    documented for D/E, ICR, and Net Debt/EBITDA. Connects to the
    already-flagged Sprint 6 open item on insurance-sector ROCE
    distortions (HDFCLIFE 646%, ICICIPRULI 754%, ICICIGI 145%).
    Deliberately not fixed in Sprint 6 -- see sprint6_retro.md.
    """
    if is_outlier:
        return None
    v = latest.get("return_on_capital_employed_pct")
    if pd.notna(v) and 0 <= v < 10:
        return (
            clamp_confidence(85 - v),
            "Return on capital employed below 10% suggests the business is not generating sufficient returns on invested capital",
        )
    return None


def con_11_high_net_debt(latest, pl_latest, is_financials):
    """Con rule 11: flag non-financial companies with net debt exceeding 3x EBITDA (operating_profit as EBITDA proxy)."""
    if is_financials:
        return None
    net_debt = latest.get("net_debt_cr")
    op_profit = pl_latest.get("operating_profit") if pl_latest is not None else None
    if (
        pd.notna(net_debt)
        and pd.notna(op_profit)
        and op_profit > 0
        and net_debt > 3 * op_profit
    ):
        conf = clamp_confidence(70 + (net_debt / op_profit - 3) * 5)
        return (
            conf,
            "Net debt exceeding 3 times EBITDA is a high leverage ratio and limits financial flexibility",
        )
    return None


def con_12_low_revenue_cagr(latest):
    """Con rule 12: flag companies with 5-year revenue CAGR below 5%."""
    v = latest.get("revenue_cagr_5yr")
    if pd.notna(v) and v < 5:
        return (
            clamp_confidence(75 - v * 3),
            "Revenue growing at below 5% over 5 years lags inflation and suggests limited business momentum",
        )
    return None


def con_13_fallback_relative_pe(latest, sector_median_pe):
    """
    Fallback tier 1: even strong companies can be flagged on relative
    valuation richness -- a genuinely true, non-fabricated observation
    that doesn't imply operational weakness, just that expectations
    are already priced in.

    NOTE: `latest` here is a small dict ({"pe_ratio": ...}) built from
    mc_latest in main(), NOT the financial_ratios `latest` row --
    financial_ratios has no pe_ratio column (confirmed via schema
    check, 2026-09). Passing the market_cap-sourced value in is the fix.
    """
    pe = latest.get("pe_ratio")
    if (
        pd.notna(pe)
        and pd.notna(sector_median_pe)
        and sector_median_pe > 0
        and pe > sector_median_pe
    ):
        return (
            65,
            "Stock trades at a premium to sector median P/E, reflecting high market expectations already priced in",
        )
    return None


def con_14_fallback_low_dividend(dividend_yield):
    """
    Fallback tier 2: a genuinely true, mild observation for
    growth-oriented companies that reinvest rather than distribute
    cash.
    """
    if pd.notna(dividend_yield) and dividend_yield < 0.5:
        return (
            62,
            "Low dividend yield means limited direct cash returns to shareholders relative to reinvestment-focused strategy",
        )
    return None


def con_15_fallback_low_fcf_conversion(latest):
    """
    Fallback tier 3a: FCF conversion below 100% of operating profit is
    a common, real, mild observation -- some portion of profit
    typically sits in working capital rather than converting fully to
    cash. Verified 2026-09: covers 17 of the final 18 residual
    companies with real, non-null values (including honest negative
    conversions like AMBUJACEM -51%, M&M -45%).
    """
    v = latest.get("fcf_conversion_pct")
    if pd.notna(v) and v < 100:
        return (
            63,
            "Free cash flow conversion below 100% of operating profit means some reported profit is not yet converting to cash",
        )
    return None


def con_16_fallback_low_cfo_quality(latest):
    """
    Fallback tier 3b: only reached if con_15 also returns None --
    covers cases where fcf_conversion_pct itself is null due to a
    missing upstream input (confirmed 2026-09: PNB has
    operating_profit = None for all 12 years in profitandloss, so
    fcf_conversion_rate() correctly can't compute a ratio).
    cfo_pat_ratio_5yr is populated for all 92 companies (0 nulls) and
    uses the same "Accrual Risk" threshold (<0.5) that Day 31 defines
    for cfo_quality_label -- not a new concept, just applied one day
    early for a company that has nothing else to fall back on.
    """
    v = latest.get("cfo_pat_ratio_5yr")
    if pd.notna(v) and v < 0.5:
        return (
            61,
            "Cash flow from operations relative to net profit over the past 5 years is below a healthy conversion threshold, indicating some earnings quality risk",
        )
    return None


def main():
    """CLI entry point: run all pro/con rules plus the fallback tier for every company and write output/pros_cons_generated.csv."""
    conn = sqlite3.connect(DB_PATH)
    fr, _pl, bs, sectors, mc_latest, outliers = load_all_company_data(conn)

    pl_full = pd.read_sql(
        """
        SELECT company_id, year, sales, net_profit, eps, operating_profit
        FROM profitandloss WHERE year != 'TTM' ORDER BY company_id, year
    """,
        conn,
    )

    companies = pd.read_sql("SELECT id FROM companies;", conn)["id"].tolist()

    # Precompute sector median P/E once (latest year), used only by the con_13 fallback
    sector_median_pe = {}
    sector_pe_rows = conn.execute("""
        SELECT s.broad_sector, mc.pe_ratio FROM market_cap mc
        JOIN sectors s ON mc.company_id = s.company_id
        WHERE mc.year = (SELECT MAX(year) FROM market_cap)
    """).fetchall()
    sector_pe_df = pd.DataFrame(sector_pe_rows, columns=["broad_sector", "pe_ratio"])
    sector_median_pe = (
        sector_pe_df.groupby("broad_sector")["pe_ratio"].median().to_dict()
    )

    conn.close()

    all_records = []

    for company_id in companies:
        history = fr[fr["company_id"] == company_id].sort_values("year")
        pl_history = pl_full[pl_full["company_id"] == company_id].sort_values("year")
        bs_history = bs[bs["company_id"] == company_id].sort_values("year")

        if len(history) == 0:
            continue

        latest = history.iloc[-1]
        pl_latest = pl_history.iloc[-1] if len(pl_history) else pd.Series(dtype=float)
        is_financials = sectors.get(company_id) == "Financials"
        is_outlier = company_id in outliers
        div_row = mc_latest[mc_latest["company_id"] == company_id]
        dividend_yield = div_row["dividend_yield_pct"].iloc[0] if len(div_row) else None
        pe_ratio_val = (
            div_row["pe_ratio"].iloc[0] if len(div_row) else None
        )  # pe_ratio lives in market_cap, not financial_ratios

        rule_results = []

        # Pro rules
        rule_results.append(("pro", "P01", pro_01_roe_sustained(history, is_outlier)))
        rule_results.append(("pro", "P02", pro_02_fcf_positive_5yr(history)))
        rule_results.append(("pro", "P03", pro_03_debt_free(latest)))
        rule_results.append(("pro", "P04", pro_04_revenue_cagr_15(latest)))
        rule_results.append(("pro", "P05", pro_05_opm_25(latest)))
        rule_results.append(("pro", "P06", pro_06_pat_cagr_20(latest)))
        rule_results.append(("pro", "P07", pro_07_icr_high(latest)))
        rule_results.append(
            ("pro", "P08", pro_08_dividend_yield(latest, dividend_yield))
        )
        rule_results.append(("pro", "P09", pro_09_eps_cagr_15(latest)))
        rule_results.append(("pro", "P10", pro_10_roe_improving(history, is_outlier)))
        rule_results.append(("pro", "P11", pro_11_operating_leverage(latest)))
        rule_results.append(
            ("pro", "P12", pro_12_assets_growing_debt_declining(bs_history))
        )

        # Con rules
        rule_results.append(("con", "C01", con_01_high_de(latest, is_financials)))
        rule_results.append(("con", "C02", con_02_fcf_negative_3yr(history)))
        rule_results.append(("con", "C03", con_03_opm_declining(history)))
        rule_results.append(("con", "C04", con_04_net_loss(pl_latest)))
        rule_results.append(("con", "C05", con_05_revenue_declining(pl_history)))
        rule_results.append(("con", "C06", con_06_low_icr(latest, is_financials)))
        rule_results.append(("con", "C07", con_07_high_payout(latest)))
        rule_results.append(("con", "C08", con_08_de_rising(history)))
        rule_results.append(("con", "C09", con_09_eps_declining(pl_history)))
        rule_results.append(("con", "C10", con_10_low_roce(latest, is_outlier)))
        rule_results.append(
            ("con", "C11", con_11_high_net_debt(latest, pl_latest, is_financials))
        )
        rule_results.append(("con", "C12", con_12_low_revenue_cagr(latest)))

        # --- Fallback pros: only if zero pros found from the 12 primary rules ---
        pros_so_far = [r for t, rid, r in rule_results if t == "pro" and r is not None]
        if not pros_so_far:
            fallback = pro_13_fallback_stable_de(latest)
            if fallback is None:
                fallback = pro_14_fallback_positive_profit(pl_latest)
            rule_results.append(("pro", "P13_fallback", fallback))

        # --- Fallback cons: three tiers, only if zero cons found from the 12 primary rules ---
        # Tracks which tier actually fired so rule_id reflects the real source
        # rather than being hardcoded to the first tier's id (bug found via
        # spot-check 2026-09: PNB's C16 text was being labeled "C13_fallback").
        cons_so_far = [r for t, rid, r in rule_results if t == "con" and r is not None]
        if not cons_so_far:
            sector = sectors.get(company_id)
            median_pe = sector_median_pe.get(sector)

            fallback_id, fallback = "C13_fallback", con_13_fallback_relative_pe(
                {"pe_ratio": pe_ratio_val}, median_pe
            )
            if fallback is None:
                fallback_id, fallback = "C14_fallback", con_14_fallback_low_dividend(
                    dividend_yield
                )
            if fallback is None:
                fallback_id, fallback = (
                    "C15_fallback",
                    con_15_fallback_low_fcf_conversion(latest),
                )
            if fallback is None:
                fallback_id, fallback = "C16_fallback", con_16_fallback_low_cfo_quality(
                    latest
                )

            rule_results.append(("con", fallback_id, fallback))

        for rule_type, rule_id, result in rule_results:
            if result is not None:
                confidence, text = result
                if confidence > 60:
                    all_records.append(
                        {
                            "company_id": company_id,
                            "type": rule_type,
                            "rule_id": rule_id,
                            "text": text,
                            "confidence_pct": round(confidence, 1),
                        }
                    )

    output_df = pd.DataFrame(all_records)
    os.makedirs("output", exist_ok=True)
    output_df.to_csv("output/pros_cons_generated.csv", index=False)

    print(f"output/pros_cons_generated.csv written: {len(output_df)} rows")
    print(
        f"Distinct companies with at least one entry: {output_df['company_id'].nunique()}"
    )

    covered = set(output_df["company_id"].unique())
    missing = set(companies) - covered
    print(f"\nCompanies with ZERO pros/cons generated: {len(missing)}")
    if missing:
        print(sorted(missing))

    has_pro = set(output_df[output_df["type"] == "pro"]["company_id"])
    has_con = set(output_df[output_df["type"] == "con"]["company_id"])
    missing_pro = set(companies) - has_pro
    missing_con = set(companies) - has_con
    print(f"\nCompanies missing at least 1 pro: {len(missing_pro)}")
    if missing_pro:
        print(sorted(missing_pro))
    print(f"\nCompanies missing at least 1 con: {len(missing_con)}")
    if missing_con:
        print(sorted(missing_con))

    # Breakdown of which fallback tier fired, for retro documentation
    fallback_rows = output_df[output_df["rule_id"].str.endswith("_fallback", na=False)]
    if len(fallback_rows):
        print("\nFallback rule usage breakdown:")
        print(fallback_rows["rule_id"].value_counts().to_string())

    return output_df


if __name__ == "__main__":
    main()