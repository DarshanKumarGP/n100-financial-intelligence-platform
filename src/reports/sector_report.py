"""
N100 Financial Intelligence Platform
Sprint 5, Day 34: Sector Report Generation

Location: src/reports/sector_report.py

Generates one PDF per distinct sector: a summary page with median KPIs
across all companies in that sector, plus a table listing every company
in the sector with 8 metrics each.

Spec says "11 PDFs" -- but sectors.xlsx has only 10 distinct
broad_sector values (confirmed repeatedly since Sprint 1/2: no
"Conglomerates/Other" company exists). This script generates one PDF
per ACTUAL distinct sector and prints the real count explicitly, rather
than forcing a fake 11th sector to match the spec's literal number.

8 metrics per company (chosen for consistency with the tearsheet's own
6 KPI tiles, extended to 8 for a fuller per-company row):
  ROE, ROCE, D/E, Revenue CAGR (5yr), OPM, Net Profit Margin,
  EPS CAGR (5yr), Dividend Payout Ratio
"""

import os
import sqlite3

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

DB_PATH = "data/nifty100.db"
SECTOR_DIR = "reports/sector"

NAVY = colors.HexColor("#1a2744")
LIGHT_GREY = colors.HexColor("#f0f0f0")

styles = getSampleStyleSheet()
cell_style = ParagraphStyle(
    "cell", parent=styles["Normal"], fontSize=7, leading=9, wordWrap="CJK"
)
header_cell_style = ParagraphStyle(
    "header_cell",
    parent=styles["Normal"],
    fontSize=7,
    leading=9,
    textColor=colors.white,
    wordWrap="CJK",
)

METRIC_COLUMNS = [
    ("return_on_equity_pct", "ROE %"),
    ("return_on_capital_employed_pct", "ROCE %"),
    ("debt_to_equity", "D/E"),
    ("revenue_cagr_5yr", "Rev CAGR 5yr %"),
    ("operating_profit_margin_pct", "OPM %"),
    ("net_profit_margin_pct", "NPM %"),
    ("eps_cagr_5yr", "EPS CAGR 5yr %"),
    ("dividend_payout_ratio_pct", "Payout %"),
]


def fmt(v):
    """Format a KPI value for display, returning 'N/A' for missing data."""
    if pd.isna(v):
        return "N/A"
    return f"{v:.1f}"


def build_header(sector_name):
    """Build the navy header bar for a sector report."""
    header_style = ParagraphStyle(
        "header", parent=styles["Title"], textColor=colors.white, fontSize=16
    )
    data = [[Paragraph(sector_name, header_style)]]
    t = Table(data, colWidths=[257 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    return t


def build_median_summary(sector_df):
    """Build the sector-level median KPI summary section."""
    rows = [["Metric (Sector Median)", "Value"]]
    for col, label in METRIC_COLUMNS:
        median_val = sector_df[col].median()
        rows.append([label, fmt(median_val)])

    t = Table(rows, colWidths=[90 * mm, 40 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (-1, -1), LIGHT_GREY),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def build_company_table(sector_df):
    """Build the table listing every company in the sector with its key metrics."""
    header_row = [Paragraph("Company", header_cell_style)] + [
        Paragraph(label, header_cell_style) for _, label in METRIC_COLUMNS
    ]
    rows = [header_row]

    for _, row in sector_df.sort_values("company_id").iterrows():
        row_cells = [Paragraph(row["company_id"], cell_style)]
        for col, _ in METRIC_COLUMNS:
            row_cells.append(Paragraph(fmt(row.get(col)), cell_style))
        rows.append(row_cells)

    col_widths = [28 * mm] + [28.6 * mm] * 8
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GREY]),
            ]
        )
    )
    return t


def generate_sector_report(sector_name, sector_df, output_path):
    """Generate the 2-part sector PDF (median summary + company table) for one sector."""
    doc = SimpleDocTemplate(
        output_path,
        pagesize=landscape(A4),
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
    )
    story = []
    story.append(build_header(sector_name))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"Companies in sector: {len(sector_df)}", styles["Normal"]))
    story.append(Spacer(1, 8))
    story.append(build_median_summary(sector_df))
    story.append(Spacer(1, 12))
    story.append(build_company_table(sector_df))

    doc.build(story)


def main():
    """CLI entry point: batch-generate all 10 sector report PDFs under reports/sector/."""
    conn = sqlite3.connect(DB_PATH)

    fr = pd.read_sql(
        """
        SELECT * FROM financial_ratios WHERE year != 'TTM' ORDER BY company_id, year
    """,
        conn,
    )
    sectors = pd.read_sql("SELECT company_id, broad_sector FROM sectors;", conn)
    conn.close()

    # Latest year per company
    latest = fr.sort_values("year").groupby("company_id").tail(1)
    latest = latest.merge(sectors, on="company_id", how="left")

    distinct_sectors = sorted(latest["broad_sector"].dropna().unique())
    print(f"Distinct sectors found: {len(distinct_sectors)}")
    print(
        f"(Spec text says 11; sectors.xlsx has been confirmed to contain "
        f"only {len(distinct_sectors)} genuine broad_sector values since Sprint 1/2 -- "
        f"generating {len(distinct_sectors)} real reports, not forcing an 11th.)"
    )
    print(distinct_sectors)

    os.makedirs(SECTOR_DIR, exist_ok=True)

    for sector_name in distinct_sectors:
        sector_df = latest[latest["broad_sector"] == sector_name]
        safe_name = sector_name.replace(" ", "_").replace("/", "-")
        output_path = f"{SECTOR_DIR}/{safe_name}_report.pdf"
        generate_sector_report(sector_name, sector_df, output_path)
        size_kb = os.path.getsize(output_path) / 1024
        print(f"Generated {output_path} ({len(sector_df)} companies, {size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
