"""
N100 Financial Intelligence Platform
Sprint 2, Day 12: Populate the financial_ratios table

Two passes:
  Pass 1 -- compute every ratio/CAGR/cashflow KPI for every company-year,
            using functions from ratios.py, cagr.py, cashflow_kpis.py.
  Pass 2 -- compute composite_quality_score, which needs population-wide
            P10/P90 winsorization bounds (per spec Section 13), so it can
            only be computed after Pass 1 has all raw values in hand.
"""

import sys
import os
import sqlite3
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ratios import (
    net_profit_margin, operating_profit_margin, return_on_equity,
    return_on_capital_employed, return_on_assets, debt_to_equity,
    high_leverage_flag, interest_coverage, icr_label, icr_warning_flag,
    net_debt, asset_turnover,
)
from cagr import windowed_cagr
from cashflow_kpis import free_cash_flow, capex_intensity, fcf_conversion_rate

DB_PATH = "data/nifty100.db"


def load_merged_data(conn):
    """
    Outer-joins P&L, balance sheet, cash flow, and companies (for
    face_value) on (company_id, year) / company_id. Outer join on BS/CF
    is deliberate -- SBIN (Sprint 1 Finding 8) has zero balance sheet
    rows but real P&L/cashflow rows; an inner join would silently drop
    SBIN entirely, whereas outer join keeps its P&L-based ratios
    populated and correctly nulls out BS-dependent ones instead.
    """
    query = """
        SELECT
            p.company_id, p.year,
            p.sales, p.operating_profit, p.opm_percentage, p.other_income,
            p.interest, p.depreciation, p.net_profit, p.eps,
            p.dividend_payout,
            b.equity_capital, b.reserves, b.borrowings, b.total_assets,
            b.investments,
            c.operating_activity AS cfo, c.investing_activity AS cfi,
            c.financing_activity AS cff,
            co.face_value
        FROM profitandloss p
        LEFT JOIN balancesheet b ON p.company_id = b.company_id AND p.year = b.year
        LEFT JOIN cashflow c ON p.company_id = c.company_id AND p.year = c.year
        LEFT JOIN companies co ON p.company_id = co.id
        WHERE p.year != 'TTM'
        ORDER BY p.company_id, p.year
    """
    df = pd.read_sql(query, conn)

    sectors = dict(conn.execute("SELECT company_id, broad_sector FROM sectors;").fetchall())
    df["broad_sector"] = df["company_id"].map(sectors)

    return df


def book_value_per_share(equity_capital, reserves, face_value):
    """
    BVPS = (equity_capital + reserves) / (equity_capital / face_value).
    (equity_capital / face_value) approximates shares outstanding.
    None if face_value or equity_capital is missing/zero -- can't derive
    share count without them.
    """
    if equity_capital is None or reserves is None or face_value is None or face_value == 0 or equity_capital == 0:
        return None
    shares_outstanding = equity_capital / face_value
    return (equity_capital + reserves) / shares_outstanding


def compute_row_ratios(row, is_financials):
    """Computes every Day 8-11 KPI for a single company-year row."""
    npm = net_profit_margin(row["net_profit"], row["sales"])
    opm = operating_profit_margin(row["operating_profit"], row["sales"])
    roe = return_on_equity(row["net_profit"], row["equity_capital"], row["reserves"])
    roce = return_on_capital_employed(
        row["operating_profit"], row["depreciation"],
        row["equity_capital"], row["reserves"], row["borrowings"]
    )
    roa = return_on_assets(row["net_profit"], row["total_assets"])

    de = debt_to_equity(row["borrowings"], row["equity_capital"], row["reserves"])
    hlf = high_leverage_flag(de, is_financials)
    icr = interest_coverage(row["operating_profit"], row["other_income"], row["interest"])
    icr_lbl = icr_label(icr, row["interest"])
    icr_warn = icr_warning_flag(icr)
    ndebt = net_debt(row["borrowings"], row["investments"])
    at = asset_turnover(row["sales"], row["total_assets"])

    fcf = free_cash_flow(row["cfo"], row["cfi"])
    capex = abs(row["cfi"]) if row["cfi"] is not None else None
    capex_int, capex_label = capex_intensity(row["cfi"], row["sales"])
    fcf_conv = fcf_conversion_rate(fcf, row["operating_profit"])

    bvps = book_value_per_share(row["equity_capital"], row["reserves"], row["face_value"])

    return {
        "net_profit_margin_pct": npm,
        "operating_profit_margin_pct": opm,
        "return_on_equity_pct": roe,
        "return_on_capital_employed_pct": roce,
        "return_on_assets_pct": roa,
        "debt_to_equity": de,
        "high_leverage_flag": int(hlf),
        "interest_coverage": icr,
        "icr_label": icr_lbl,
        "icr_warning_flag": int(icr_warn),
        "net_debt_cr": ndebt,
        "asset_turnover": at,
        "free_cash_flow_cr": fcf,
        "capex_cr": capex,
        "capex_intensity_label": capex_label,
        "fcf_conversion_pct": fcf_conv,
        "earnings_per_share": row["eps"],
        "book_value_per_share": bvps,
        "dividend_payout_ratio_pct": row["dividend_payout"],
        "total_debt_cr": row["borrowings"],
        "cash_from_operations_cr": row["cfo"],
    }


def compute_company_cagrs(company_df):
    """
    For each fiscal year in a company's history, compute revenue/PAT/EPS
    CAGR "as of" that year -- i.e. using only data up to and including
    that year, not the company's overall latest year. This is what makes
    CAGR meaningful stored on every row, not just the most recent one.
    """
    results = {}
    sales_pairs_full = list(zip(company_df["year"], company_df["sales"]))
    pat_pairs_full = list(zip(company_df["year"], company_df["net_profit"]))
    eps_pairs_full = list(zip(company_df["year"], company_df["eps"]))

    for _, row in company_df.iterrows():
        target_year = row["year"]

        sales_asof = [(y, v) for y, v in sales_pairs_full if y <= target_year]
        pat_asof = [(y, v) for y, v in pat_pairs_full if y <= target_year]
        eps_asof = [(y, v) for y, v in eps_pairs_full if y <= target_year]

        rev3, rev3f = windowed_cagr(sales_asof, 3)
        rev5, rev5f = windowed_cagr(sales_asof, 5)
        rev10, rev10f = windowed_cagr(sales_asof, 10)
        pat3, pat3f = windowed_cagr(pat_asof, 3)
        pat5, pat5f = windowed_cagr(pat_asof, 5)
        pat10, pat10f = windowed_cagr(pat_asof, 10)
        eps5, eps5f = windowed_cagr(eps_asof, 5)

        results[target_year] = {
            "revenue_cagr_3yr": rev3, "revenue_cagr_3yr_flag": rev3f,
            "revenue_cagr_5yr": rev5, "revenue_cagr_5yr_flag": rev5f,
            "revenue_cagr_10yr": rev10, "revenue_cagr_10yr_flag": rev10f,
            "pat_cagr_3yr": pat3, "pat_cagr_3yr_flag": pat3f,
            "pat_cagr_5yr": pat5, "pat_cagr_5yr_flag": pat5f,
            "pat_cagr_10yr": pat10, "pat_cagr_10yr_flag": pat10f,
            "eps_cagr_5yr": eps5, "eps_cagr_5yr_flag": eps5f,
        }

    return results


def winsorized_score(value, p10, p90, invert=False):
    """
    Normalizes a value to 0-100 using P10/P90 winsorization (spec Section
    13). Values below P10 clip to 0, above P90 clip to 100, between is
    linear. invert=True for metrics where LOWER is better (e.g. D/E).
    """
    if value is None or p10 is None or p90 is None or p90 == p10:
        return None
    clipped = max(p10, min(p90, value))
    score = (clipped - p10) / (p90 - p10) * 100
    return 100 - score if invert else score


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")

    # Clear any prior run's rows before reinserting -- keeps this script
    # safely re-runnable without manual cleanup or duplicate rows.
    conn.execute("DELETE FROM financial_ratios;")
    conn.commit()

    df = load_merged_data(conn)
    print(f"Loaded {len(df)} merged company-year rows (P&L outer-joined with BS/CF/companies)")

    all_rows = []
    for company_id, company_df in df.groupby("company_id"):
        is_financials = (company_df["broad_sector"].iloc[0] == "Financials")
        company_df = company_df.sort_values("year").reset_index(drop=True)
        cagr_by_year = compute_company_cagrs(company_df)

        for _, row in company_df.iterrows():
            ratios = compute_row_ratios(row, is_financials)
            cagrs = cagr_by_year[row["year"]]
            record = {"company_id": row["company_id"], "year": row["year"]}
            record.update(ratios)
            record.update(cagrs)
            all_rows.append(record)

    result_df = pd.DataFrame(all_rows)
    print(f"Pass 1 complete: {len(result_df)} rows with ratios + CAGR computed")

    # Pass 2: composite_quality_score, needs population-wide P10/P90
    p10_90 = {}
    for col in ["return_on_equity_pct", "free_cash_flow_cr",
                "return_on_capital_employed_pct", "debt_to_equity"]:
        valid = result_df[col].dropna()
        p10_90[col] = (valid.quantile(0.10), valid.quantile(0.90)) if len(valid) > 0 else (None, None)

    def composite(row):
        roe_s = winsorized_score(row["return_on_equity_pct"], *p10_90["return_on_equity_pct"])
        fcf_s = winsorized_score(row["free_cash_flow_cr"], *p10_90["free_cash_flow_cr"])
        roce_s = winsorized_score(row["return_on_capital_employed_pct"], *p10_90["return_on_capital_employed_pct"])
        de_s = winsorized_score(row["debt_to_equity"], *p10_90["debt_to_equity"], invert=True)

        parts = [(roe_s, 0.30), (fcf_s, 0.25), (roce_s, 0.25), (de_s, 0.20)]
        valid_parts = [(s, w) for s, w in parts if s is not None]
        if not valid_parts:
            return None
        total_weight = sum(w for _, w in valid_parts)
        return sum(s * w for s, w in valid_parts) / total_weight

    result_df["composite_quality_score"] = result_df.apply(composite, axis=1)
    print("Pass 2 complete: composite_quality_score computed")

    result_df.to_sql("financial_ratios", conn, if_exists="append", index=False)
    conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM financial_ratios;").fetchone()[0]
    print(f"\nfinancial_ratios table now has {count} rows")

    null_check = result_df.isnull().sum()
    print("\nNull counts per column (context, not necessarily a problem):")
    print(null_check[null_check > 0].to_string())

    conn.close()


if __name__ == "__main__":
    main()