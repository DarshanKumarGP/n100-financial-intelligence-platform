"""
N100 Financial Intelligence Platform
Sprint 4, Day 26: Valuation Module

FCF yield, sector median P/E, and overvaluation/discount flags.
Outlier guard applied when computing sector medians -- HAL/BEL/INDIGO-
style extreme small-equity-base companies would otherwise distort the
benchmark every other company in the sector gets compared against.
"""

import sqlite3
import pandas as pd
import os

DB_PATH = "data/nifty100.db"


def load_valuation_base(conn):
    """
    One row per company: latest fiscal year's financial_ratios (for FCF,
    equity_base for the outlier check), matched market_cap row via the
    fiscal-year-to-calendar-year approximation (verified Day 22: 92/92
    companies have complete 2019-2024 market_cap coverage).
    """
    query = """
        SELECT fr.company_id, fr.year, c.company_name, s.broad_sector,
               fr.free_cash_flow_cr,
               b.equity_capital, b.reserves,
               mc.year AS mc_year, mc.market_cap_crore, mc.enterprise_value_crore,
               mc.pe_ratio, mc.pb_ratio, mc.ev_ebitda, mc.dividend_yield_pct,
               p.net_profit
        FROM financial_ratios fr
        JOIN companies c ON fr.company_id = c.id
        LEFT JOIN sectors s ON fr.company_id = s.company_id
        LEFT JOIN balancesheet b ON fr.company_id = b.company_id AND fr.year = b.year
        LEFT JOIN profitandloss p ON fr.company_id = p.company_id AND fr.year = p.year
        LEFT JOIN market_cap mc
            ON fr.company_id = mc.company_id
            AND mc.year = CAST(SUBSTR(fr.year, 1, 4) AS INTEGER)
        WHERE fr.year = (
            SELECT MAX(fr2.year) FROM financial_ratios fr2
            WHERE fr2.company_id = fr.company_id
        )
    """
    df = pd.read_sql(query, conn)

    df["equity_base"] = df["equity_capital"] + df["reserves"]
    df["profit_to_equity_ratio"] = df.apply(
        lambda r: (r["net_profit"] / r["equity_base"])
        if pd.notna(r["equity_base"]) and r["equity_base"] > 0 and pd.notna(r["net_profit"])
        else None,
        axis=1
    )
    # Same guard threshold used throughout the project since Sprint 2 Finding 5
    df["is_outlier"] = df["profit_to_equity_ratio"] > 5

    return df


def compute_fcf_yield(fcf, market_cap):
    if fcf is None or market_cap is None or pd.isna(fcf) or pd.isna(market_cap) or market_cap == 0:
        return None
    return (fcf / market_cap) * 100


def get_5yr_median_pe(conn, ticker):
    """Company's own trailing 5-year median P/E from market_cap."""
    df = pd.read_sql(
        "SELECT pe_ratio FROM market_cap WHERE company_id = ? ORDER BY year DESC LIMIT 5",
        conn, params=(ticker,)
    )
    valid = df["pe_ratio"].dropna()
    return valid.median() if len(valid) > 0 else None


def compute_sector_median_pe(df):
    """
    Sector median P/E, EXCLUDING outlier companies from the calculation
    so the benchmark itself isn't distorted -- outliers still appear in
    the final output with their own flag, just don't corrupt what
    "normal" looks like for their sector.
    """
    clean = df[~df["is_outlier"]]
    return clean.groupby("broad_sector")["pe_ratio"].median()


def assign_flag(pe, sector_median_pe):
    """
    Caution if P/E > 1.5x sector median, Discount if < 0.7x, else Fair.
    None if either input is missing -- can't flag without both.
    """
    if pe is None or sector_median_pe is None or pd.isna(pe) or pd.isna(sector_median_pe) or sector_median_pe == 0:
        return None
    if pe > sector_median_pe * 1.5:
        return "Caution"
    if pe < sector_median_pe * 0.7:
        return "Discount"
    return "Fair"


def main():
    conn = sqlite3.connect(DB_PATH)
    df = load_valuation_base(conn)

    print(f"Loaded {len(df)} companies for valuation.")
    outlier_count = df["is_outlier"].sum()
    print(f"{outlier_count} companies flagged as outliers (excluded from sector median calc only): "
          f"{df[df['is_outlier']]['company_id'].tolist()}")

    df["fcf_yield_pct"] = df.apply(lambda r: compute_fcf_yield(r["free_cash_flow_cr"], r["market_cap_crore"]), axis=1)

    df["5yr_median_pe"] = df["company_id"].apply(lambda t: get_5yr_median_pe(conn, t))

    sector_medians = compute_sector_median_pe(df)
    df["sector_median_pe"] = df["broad_sector"].map(sector_medians)

    df["pe_vs_sector_median_pct"] = df.apply(
        lambda r: ((r["pe_ratio"] - r["sector_median_pe"]) / r["sector_median_pe"] * 100)
        if pd.notna(r["pe_ratio"]) and pd.notna(r["sector_median_pe"]) and r["sector_median_pe"] != 0
        else None,
        axis=1
    )

    df["flag"] = df.apply(lambda r: assign_flag(r["pe_ratio"], r["sector_median_pe"]), axis=1)

    output_cols = ["company_id", "company_name", "broad_sector", "pe_ratio", "pb_ratio",
                   "ev_ebitda", "fcf_yield_pct", "5yr_median_pe", "pe_vs_sector_median_pct", "flag"]
    final = df[output_cols].rename(columns={"company_id": "company_id"})

    os.makedirs("output", exist_ok=True)
    final.to_excel("output/valuation_summary.xlsx", index=False)
    print(f"\noutput/valuation_summary.xlsx written: {len(final)} rows")

    flagged = final[final["flag"].isin(["Caution", "Discount"])]
    flagged.to_csv("output/valuation_flags.csv", index=False)
    print(f"output/valuation_flags.csv written: {len(flagged)} flagged companies")

    print("\nFlag distribution:")
    print(final["flag"].value_counts(dropna=False).to_string())

    conn.close()
    return final


if __name__ == "__main__":
    main()