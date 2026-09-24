"""
N100 Financial Intelligence Platform
Sprint 5, Day 31: Cash Flow Intelligence Orchestration

Produces output/cashflow_intelligence.xlsx and output/distress_alerts.csv.

Deliberately reuses existing, already-verified sources rather than
recomputing anything that's already correct elsewhere:
  - cfo_pat_ratio_5yr (== cfo_quality_score), fcf_cagr_5yr,
    fcf_conversion_pct: pulled straight from financial_ratios
    (Sprint 2), latest non-TTM year per company
  - cfo_quality_label: DERIVED here via cashflow_kpis._cfo_quality_label(),
    NOT pulled from financial_ratios.cfo_quality_label. Confirmed
    2026-09: that column is None for all 1070 rows in the table --
    never populated by any script in the pipeline (a schema leftover,
    not a bug we introduced). The underlying ratio (cfo_pat_ratio_5yr)
    is correct and populated; only the label was never derived from it.
  - capital_allocation_label: pulled from output/capital_allocation.csv
    (Sprint 2's generate_capital_allocation.py), NOT recomputed here
  - capex_intensity_pct: recomputed via cashflow_kpis.capex_intensity()
    from raw cashflow.investing_activity + profitandloss.sales, since
    financial_ratios only stores the label, not the raw percentage

New Day 31 logic (added to cashflow_kpis.py, not duplicated here):
  - detect_distress_signal(cfo, cff): CFO<0 AND CFF>0, latest year
  - detect_deleveraging(cff, borrowings_t, borrowings_t-1): CFF<0 AND
    borrowings declining YoY

capital_allocation_label fallback: 2 companies (ICICIPRULI, JIOFIN)
have "Undetermined" as their LATEST year's pattern_label in
capital_allocation.csv (confirmed 2026-09). For these, we walk
backward to the most recent year with a real (non-null,
non-Undetermined) label instead of reporting "Undetermined" outright.
If no valid year exists at all, we report "Undetermined" honestly
rather than fabricate a pattern.

deleveraging_flag null: SBIN correctly gets None here -- it has zero
rows in balancesheet entirely (confirmed Sprint 1), so there's no
borrowings history to compare year-over-year. Same known quirk as
SBIN's null ROE/ROCE/D/E elsewhere in the project; this is the guard
working as intended, not a bug.

2026-09 fix: distress_flag/deleveraging_flag are computed as Python
True/False/None. When deleveraging_flag's single None (SBIN) is
written to Excel alongside True/False, pandas silently upcasts the
whole column to float64 (True->1.0, False->0.0, None->NaN) -- confirmed
via real output (TCS showed 0.0, SBIN showed NaN, inconsistent with
distress_flag's clean True/False since that column has no Nones).
Not a logic bug, just an unreadable deliverable. Diagnostics below
still run on the raw boolean/None values; only the Excel-bound copy
gets converted to explicit Yes/No/N/A strings.
"""

import os
import sqlite3
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cashflow_kpis import (
    _cfo_quality_label,
    capex_intensity,
    detect_deleveraging,
    detect_distress_signal,
)

DB_PATH = "data/nifty100.db"
CAP_ALLOC_PATH = "output/capital_allocation.csv"


def get_latest_capital_allocation_label(cap_alloc_df, company_id):
    """
    Returns the most recent year's pattern_label for company_id that is
    NOT null and NOT 'Undetermined'. Falls back to 'Undetermined' only
    if no valid year exists at all for that company.
    """
    rows = cap_alloc_df[cap_alloc_df["company_id"] == company_id].sort_values(
        "year", ascending=False
    )
    for _, row in rows.iterrows():
        label = row["pattern_label"]
        if pd.notna(label) and label != "Undetermined":
            return label
    return "Undetermined"


def _bool_to_label(v):
    """Excel-display-only conversion: True/False/None -> Yes/No/Not Available.
    Deliberately NOT "N/A" -- confirmed 2026-09 that pandas' default
    na_values list treats "N/A" as a missing-value marker on read-back
    (read_excel/read_csv), which silently turns it back into NaN and
    undoes this exact fix. "Not Available" doesn't collide.
    """
    if pd.isna(v):
        return "Not Available"
    return "Yes" if v else "No"


def main():
    """CLI entry point: compute CFO quality, CapEx intensity, and distress/deleveraging flags for all companies; write cashflow_intelligence.xlsx and distress_alerts.csv."""
    conn = sqlite3.connect(DB_PATH)

    companies = pd.read_sql("SELECT id FROM companies;", conn)["id"].tolist()
    sectors = dict(
        conn.execute("SELECT company_id, broad_sector FROM sectors;").fetchall()
    )

    fr = pd.read_sql(
        """
        SELECT company_id, year, cfo_pat_ratio_5yr, fcf_cagr_5yr, fcf_conversion_pct
        FROM financial_ratios WHERE year != 'TTM' ORDER BY company_id, year
    """,
        conn,
    )
    fr["cfo_pat_ratio_5yr"] = pd.to_numeric(fr["cfo_pat_ratio_5yr"], errors="coerce")

    cf = pd.read_sql(
        """
        SELECT company_id, year, operating_activity, investing_activity, financing_activity
        FROM cashflow WHERE year != 'TTM' ORDER BY company_id, year
    """,
        conn,
    )

    pl = pd.read_sql(
        """
        SELECT company_id, year, sales, net_profit
        FROM profitandloss WHERE year != 'TTM' ORDER BY company_id, year
    """,
        conn,
    )

    bs = pd.read_sql(
        """
        SELECT company_id, year, borrowings
        FROM balancesheet ORDER BY company_id, year
    """,
        conn,
    )

    conn.close()

    cap_alloc_df = pd.read_csv(CAP_ALLOC_PATH)

    records = []
    distress_records = []

    for company_id in companies:
        fr_hist = fr[fr["company_id"] == company_id].sort_values("year")
        cf_hist = cf[cf["company_id"] == company_id].sort_values("year")
        pl_hist = pl[pl["company_id"] == company_id].sort_values("year")
        bs_hist = bs[bs["company_id"] == company_id].sort_values("year")

        if len(fr_hist) == 0 or len(cf_hist) == 0:
            continue

        fr_latest = fr_hist.iloc[-1]
        cf_latest = cf_hist.iloc[-1]
        pl_latest = pl_hist.iloc[-1] if len(pl_hist) else pd.Series(dtype=float)

        cfo_latest = cf_latest.get("operating_activity")
        cfi_latest = cf_latest.get("investing_activity")
        cff_latest = cf_latest.get("financing_activity")
        sales_latest = pl_latest.get("sales")
        net_profit_latest = pl_latest.get("net_profit")

        # Recompute capex_intensity_pct fresh -- financial_ratios only stores the label
        capex_pct, capex_label = capex_intensity(cfi_latest, sales_latest)

        # Derive cfo_quality_label from the already-populated ratio -- the
        # financial_ratios.cfo_quality_label column itself is never written
        # by any script (confirmed None for all 1070 rows, 2026-09)
        cfo_ratio = fr_latest.get("cfo_pat_ratio_5yr")
        cfo_quality_label = (
            _cfo_quality_label(cfo_ratio) if pd.notna(cfo_ratio) else None
        )

        # Distress signal: latest year CFO/CFF only
        distress_flag = detect_distress_signal(cfo_latest, cff_latest)

        # Deleveraging: needs latest + prior year borrowings
        deleveraging_flag = None
        if len(bs_hist) >= 2:
            borrowings_current = bs_hist.iloc[-1].get("borrowings")
            borrowings_prior = bs_hist.iloc[-2].get("borrowings")
            deleveraging_flag = detect_deleveraging(
                cff_latest, borrowings_current, borrowings_prior
            )

        capital_allocation_label = get_latest_capital_allocation_label(
            cap_alloc_df, company_id
        )

        records.append(
            {
                "company_id": company_id,
                "sector": sectors.get(company_id),
                "cfo_quality_score": cfo_ratio,
                "cfo_quality_label": cfo_quality_label,
                "capex_intensity_pct": capex_pct,
                "capex_label": capex_label,
                "fcf_cagr_5yr": fr_latest.get("fcf_cagr_5yr"),
                "fcf_conversion_pct": fr_latest.get("fcf_conversion_pct"),
                "distress_flag": distress_flag,
                "deleveraging_flag": deleveraging_flag,
                "capital_allocation_label": capital_allocation_label,
            }
        )

        if distress_flag:
            distress_records.append(
                {
                    "company_id": company_id,
                    "cfo": cfo_latest,
                    "cff": cff_latest,
                    "net_profit": net_profit_latest,
                }
            )

    output_df = pd.DataFrame(records)

    distress_df = pd.DataFrame(distress_records)
    os.makedirs("output", exist_ok=True)
    distress_df.to_csv("output/distress_alerts.csv", index=False)

    print(f"output/distress_alerts.csv written: {len(distress_df)} rows")

    missing = set(companies) - set(output_df["company_id"])
    print(f"\nCompanies with no row (missing cashflow/ratio data): {len(missing)}")
    if missing:
        print(sorted(missing))

    print(f"\ncfo_quality_score nulls: {output_df['cfo_quality_score'].isna().sum()}")
    print(f"cfo_quality_label nulls: {output_df['cfo_quality_label'].isna().sum()}")
    print(f"capex_intensity_pct nulls: {output_df['capex_intensity_pct'].isna().sum()}")
    print(f"deleveraging_flag nulls: {output_df['deleveraging_flag'].isna().sum()}")
    print(f"\ndistress_flag True count: {output_df['distress_flag'].sum()}")
    print(
        f"deleveraging_flag True count: {(output_df['deleveraging_flag']==True).sum()}"
    )

    print("\ncfo_quality_label value counts:")
    print(output_df["cfo_quality_label"].value_counts(dropna=False))

    print("\ncapital_allocation_label value counts:")
    print(output_df["capital_allocation_label"].value_counts(dropna=False))

    # Excel-bound copy only: convert True/False/None -> Yes/No/N/A so mixed
    # dtypes don't get silently upcast to 1.0/0.0/NaN by the Excel writer.
    # distress_alerts.csv above and all diagnostics here already used the
    # raw values, so this conversion changes display only, not logic.
    excel_df = output_df.copy()
    excel_df["distress_flag"] = excel_df["distress_flag"].apply(_bool_to_label)
    excel_df["deleveraging_flag"] = excel_df["deleveraging_flag"].apply(_bool_to_label)
    excel_df.to_excel("output/cashflow_intelligence.xlsx", index=False)

    print(f"\noutput/cashflow_intelligence.xlsx written: {len(excel_df)} rows")

    return output_df


if __name__ == "__main__":
    main()
