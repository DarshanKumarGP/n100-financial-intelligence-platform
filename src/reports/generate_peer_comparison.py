"""
N100 Financial Intelligence Platform
Sprint 3, Day 20: Peer Comparison Excel Report

11 sheets (one per peer group): company_id, company_name, 20 metric
columns + percentile rank per metric, colour-coded, benchmark row
highlighted gold, summary row with peer group medians.

Note: SBIN is the Public Sector Banks benchmark but has NULL for every
balance-sheet-dependent metric (Sprint 1 Finding 8) -- its row will show
blanks in those columns even though it's correctly gold-highlighted.
This is expected, not a bug in this report.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "analytics"))

import sqlite3
import pandas as pd
from openpyxl.styles import PatternFill, Font

DB_PATH = "data/nifty100.db"
OUTPUT_PATH = "output/peer_comparison.xlsx"

GREEN = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
YELLOW = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
RED = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
GOLD = PatternFill(start_color="FFD966", end_color="FFD966", fill_type="solid")
BOLD = Font(bold=True)

RANKED_METRICS = [
    ("return_on_equity_pct", "ROE %"),
    ("return_on_capital_employed_pct", "ROCE %"),
    ("net_profit_margin_pct", "NPM %"),
    ("debt_to_equity", "D/E"),
    ("free_cash_flow_cr", "FCF Cr"),
    ("pat_cagr_5yr", "PAT CAGR 5yr %"),
    ("revenue_cagr_5yr", "Rev CAGR 5yr %"),
    ("eps_cagr_5yr", "EPS CAGR 5yr %"),
    ("interest_coverage", "ICR"),
    ("asset_turnover", "Asset Turnover"),
]


def load_peer_data(conn):
    query = """
        SELECT fr.company_id, c.company_name, pg.peer_group_name, pg.is_benchmark,
               fr.return_on_equity_pct, fr.return_on_capital_employed_pct,
               fr.net_profit_margin_pct, fr.debt_to_equity, fr.free_cash_flow_cr,
               fr.pat_cagr_5yr, fr.revenue_cagr_5yr, fr.eps_cagr_5yr,
               fr.interest_coverage, fr.asset_turnover
        FROM financial_ratios fr
        JOIN companies c ON fr.company_id = c.id
        JOIN peer_groups pg ON fr.company_id = pg.company_id
        WHERE fr.year = (
            SELECT MAX(fr2.year) FROM financial_ratios fr2
            WHERE fr2.company_id = fr.company_id
        )
    """
    return pd.read_sql(query, conn)


def load_percentiles(conn):
    return pd.read_sql("SELECT company_id, peer_group_name, metric, percentile_rank FROM peer_percentiles;", conn)


def build_sheet_df(group_df, percentiles_df, group_name):
    """
    One row per company: raw metric values + one percentile column per
    ranked metric, sorted by company_name. Percentile values come
    straight from the peer_percentiles table via a clean pivot+merge --
    no re-reading from Excel cells later, which avoids type-coercion
    issues (openpyxl can read mixed-type cells back as strings).
    """
    group_pct = percentiles_df[percentiles_df["peer_group_name"] == group_name]
    pct_wide = group_pct.pivot(index="company_id", columns="metric", values="percentile_rank")

    result = group_df[["company_id", "company_name", "is_benchmark"] + [m for m, _ in RANKED_METRICS]].copy()
    result = result.set_index("company_id")

    pct_columns_ordered = []
    for metric_col, label in RANKED_METRICS:
        pct_col_name = f"{label} percentile"
        if metric_col in pct_wide.columns:
            result[pct_col_name] = pct_wide[metric_col].reindex(result.index)
        else:
            result[pct_col_name] = None
        pct_columns_ordered.append(pct_col_name)

    result = result.reset_index().sort_values("company_name")

    # Explicit column order: id, name, then each (raw metric, its percentile) pair
    ordered_cols = ["company_id", "company_name", "is_benchmark"]
    for metric_col, label in RANKED_METRICS:
        ordered_cols.append(metric_col)
        ordered_cols.append(f"{label} percentile")

    return result[ordered_cols]


def write_sheet(writer, sheet_name, df):
    safe_name = sheet_name[:31]
    df_out = df.drop(columns=["is_benchmark"])
    df_out.to_excel(writer, sheet_name=safe_name, index=False)

    ws = writer.sheets[safe_name]
    headers = [c.value for c in ws[1]]
    pct_col_indices = [i + 1 for i, h in enumerate(headers) if h and "percentile" in h]

    # Use the DataFrame directly for colour decisions -- not the written
    # cells -- so we control the exact dtype and avoid the earlier bug.
    for row_offset, (_, row) in enumerate(df.iterrows()):
        row_idx = row_offset + 2  # +2: header row + 1-indexed
        is_benchmark = bool(row["is_benchmark"] == 1)

        if is_benchmark:
            for col_idx in range(1, len(headers) + 1):
                ws.cell(row=row_idx, column=col_idx).fill = GOLD
                ws.cell(row=row_idx, column=col_idx).font = BOLD
            continue  # benchmark rows stay gold, skip percentile colouring

        for col_idx in pct_col_indices:
            header = headers[col_idx - 1]
            raw_value = row[header]
            if pd.isna(raw_value):
                continue
            value = float(raw_value)
            if value >= 0.75:
                ws.cell(row=row_idx, column=col_idx).fill = GREEN
            elif value >= 0.25:
                ws.cell(row=row_idx, column=col_idx).fill = YELLOW
            else:
                ws.cell(row=row_idx, column=col_idx).fill = RED

    # Summary row: peer group median for each numeric column
    summary_row_idx = len(df) + 2
    ws.cell(row=summary_row_idx, column=1, value="MEDIAN").font = BOLD
    for col_idx, header in enumerate(headers, start=1):
        if header in ("company_id", "company_name"):
            continue
        col_values = pd.to_numeric(df_out.iloc[:, col_idx - 1], errors="coerce")
        median_val = col_values.median()
        if pd.notna(median_val):
            ws.cell(row=summary_row_idx, column=col_idx, value=round(median_val, 4)).font = BOLD


def main():
    conn = sqlite3.connect(DB_PATH)
    group_data = load_peer_data(conn)
    percentiles = load_percentiles(conn)
    conn.close()

    os.makedirs("output", exist_ok=True)

    with pd.ExcelWriter(OUTPUT_PATH, engine="openpyxl") as writer:
        total = 0
        for group_name in sorted(group_data["peer_group_name"].unique()):
            group_df = group_data[group_data["peer_group_name"] == group_name]
            sheet_df = build_sheet_df(group_df, percentiles, group_name)
            write_sheet(writer, group_name, sheet_df)
            print(f"{group_name}: {len(sheet_df)} companies written")
            total += len(sheet_df)

    print(f"\n{OUTPUT_PATH} written with {group_data['peer_group_name'].nunique()} sheets, {total} total company rows.")


if __name__ == "__main__":
    main()