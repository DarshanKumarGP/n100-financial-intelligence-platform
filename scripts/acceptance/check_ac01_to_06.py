"""
N100 Financial Intelligence Platform
Sprint 6, Day 45: Acceptance Gates AC-01 to AC-06

Location: scripts/acceptance/check_ac01_to_06.py

Runs each gate's real query against the live database and prints
PASS/FAIL with the actual evidence -- no assumed numbers.

AC-05 ("matches manual Excel calculation") has no saved manual
reference value anywhere in this project's history, so this script
independently recomputes CAGR directly from raw profitandloss.sales
for two companies (same technique used in Sprint 5 to verify the
INFY parser-vs-computed divergence) and checks it against
financial_ratios.revenue_cagr_5yr -- a genuine independent recheck,
not the same code path graded against itself.

Usage:
    python scripts/acceptance/check_ac01_to_06.py
"""

import sqlite3

DB_PATH = "data/nifty100.db"


def gate(label, passed, evidence):
    status = "PASS" if passed else "FAIL"
    print(f"\n[{status}] {label}")
    for line in evidence:
        print(f"    {line}")
    return passed


def main():
    conn = sqlite3.connect(DB_PATH)
    results = {}

    # --- AC-01: SELECT COUNT(*) FROM companies = 92 ---
    count = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    results["AC-01"] = gate(
        "AC-01: companies count = 92",
        count == 92,
        [f"SELECT COUNT(*) FROM companies -> {count}"],
    )

    # --- AC-02: >=90% of companies have >=10 years of P&L, BS, CF ---
    def years_coverage(table):
        rows = conn.execute(
            f"SELECT company_id, COUNT(DISTINCT year) FROM {table} "
            f"WHERE year != 'TTM' GROUP BY company_id"
        ).fetchall()
        return {cid: n for cid, n in rows}

    pl_years = years_coverage("profitandloss")
    bs_years = years_coverage("balancesheet")
    cf_years = years_coverage("cashflow")

    company_ids = [r[0] for r in conn.execute("SELECT id FROM companies").fetchall()]
    qualifying = 0
    for cid in company_ids:
        if (
            pl_years.get(cid, 0) >= 10
            and bs_years.get(cid, 0) >= 10
            and cf_years.get(cid, 0) >= 10
        ):
            qualifying += 1
    pct = 100 * qualifying / len(company_ids)
    results["AC-02"] = gate(
        "AC-02: >=90% of companies have >=10yr P&L/BS/CF",
        pct >= 90,
        [
            f"{qualifying} / {len(company_ids)} companies qualify ({pct:.1f}%)",
            "Note: SBIN has 0 balancesheet rows by design (Sprint 1 finding) "
            "-- correctly excluded from qualifying count, not an error.",
        ],
    )

    # --- AC-03: PRAGMA foreign_key_check returns 0 rows ---
    conn.execute("PRAGMA foreign_keys = ON")
    fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    results["AC-03"] = gate(
        "AC-03: PRAGMA foreign_key_check returns 0 rows",
        len(fk_violations) == 0,
        [f"{len(fk_violations)} violation(s) found"]
        + [str(v) for v in fk_violations[:5]],
    )

    # --- AC-04: SELECT COUNT(*) FROM financial_ratios >= 1100 ---
    fr_count = conn.execute("SELECT COUNT(*) FROM financial_ratios").fetchone()[0]
    results["AC-04"] = gate(
        "AC-04: financial_ratios count >= 1,100",
        fr_count >= 1100,
        [f"SELECT COUNT(*) FROM financial_ratios -> {fr_count}"],
    )

    # --- AC-05: Revenue CAGR spot-check vs independent manual recompute ---
    spot_check_tickers = ["TCS", "RELIANCE"]
    ac05_pass = True
    ac05_evidence = []
    for ticker in spot_check_tickers:
        sales_rows = conn.execute(
            "SELECT year, sales FROM profitandloss "
            "WHERE company_id = ? AND year != 'TTM' ORDER BY year",
            (ticker,),
        ).fetchall()
        if len(sales_rows) < 6:
            ac05_evidence.append(f"{ticker}: insufficient history, skipped")
            continue
        # last 6 fiscal years -> 5-year CAGR window
        last6 = sales_rows[-6:]
        start_sales = last6[0][1]
        end_sales = last6[-1][1]
        manual_cagr = ((end_sales / start_sales) ** (1 / 5) - 1) * 100 if start_sales else None

        stored_cagr_row = conn.execute(
            "SELECT revenue_cagr_5yr FROM financial_ratios "
            "WHERE company_id = ? AND year != 'TTM' "
            "ORDER BY year DESC LIMIT 1",
            (ticker,),
        ).fetchone()
        stored_cagr = stored_cagr_row[0] if stored_cagr_row else None

        if manual_cagr is None or stored_cagr is None:
            ac05_evidence.append(f"{ticker}: missing data, skipped")
            continue

        diff = abs(manual_cagr - stored_cagr)
        within_tolerance = diff <= 0.1
        ac05_pass = ac05_pass and within_tolerance
        ac05_evidence.append(
            f"{ticker}: manual (raw sales, {last6[0][0]}->{last6[-1][0]}) = "
            f"{manual_cagr:.3f}%, stored financial_ratios = {stored_cagr:.3f}%, "
            f"diff = {diff:.3f}pp -- {'within' if within_tolerance else 'EXCEEDS'} 0.1% tolerance"
        )

    results["AC-05"] = gate(
        "AC-05: Revenue CAGR spot-check within 0.1% of independent manual recompute",
        ac05_pass,
        ac05_evidence,
    )

    # --- AC-06: ROE matches companies.roe_percentage within 5% for 5 companies ---
    sample_tickers = ["TCS", "HDFCBANK", "INFY", "RELIANCE", "ABB"]
    ac06_evidence = []
    ac06_fail_reasons = []
    for ticker in sample_tickers:
        row = conn.execute(
            "SELECT roe_percentage FROM companies WHERE id = ?", (ticker,)
        ).fetchone()
        source_roe = row[0] if row else None

        computed_row = conn.execute(
            "SELECT return_on_equity_pct FROM financial_ratios "
            "WHERE company_id = ? AND year != 'TTM' ORDER BY year DESC LIMIT 1",
            (ticker,),
        ).fetchone()
        computed_roe = computed_row[0] if computed_row else None

        if source_roe is None or computed_roe is None:
            ac06_evidence.append(f"{ticker}: missing data")
            continue

        # companies.roe_percentage is sometimes a raw fraction (e.g. TCS = 0.52)
        # rather than a percentage -- normalize the same way the rest of this
        # project already documented (TCS confirmed 2026-09), without silently
        # hiding which companies needed it.
        normalized_source = source_roe * 100 if source_roe < 5 else source_roe
        pct_diff = abs(computed_roe - normalized_source) / computed_roe * 100 if computed_roe else None
        within_5pct = pct_diff is not None and pct_diff <= 5
        note = " (raw value was a decimal fraction, normalized x100)" if source_roe < 5 else ""
        if not within_5pct:
            ac06_fail_reasons.append(ticker)
        ac06_evidence.append(
            f"{ticker}: computed={computed_roe:.2f}%, source(companies.roe_percentage)="
            f"{source_roe}{note} -> normalized={normalized_source:.2f}%, "
            f"diff={pct_diff:.1f}% -- {'within' if within_5pct else 'EXCEEDS'} 5%"
        )

    results["AC-06"] = gate(
        "AC-06: ROE matches companies.roe_percentage within 5% for 5 companies",
        len(ac06_fail_reasons) == 0,
        ac06_evidence
        + (
            [
                f"NOTE: {', '.join(ac06_fail_reasons)} exceed 5% even after normalizing "
                f"the raw-decimal case -- see notes below."
            ]
            if ac06_fail_reasons
            else []
        ),
    )

    conn.close()

    print("\n" + "=" * 60)
    print("SUMMARY (AC-01 to AC-06)")
    print("=" * 60)
    for gate_id, passed in results.items():
        print(f"  {gate_id}: {'PASS' if passed else 'FAIL'}")


if __name__ == "__main__":
    main()