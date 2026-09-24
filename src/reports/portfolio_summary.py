"""
N100 Financial Intelligence Platform
Sprint 5, Day 35: Portfolio Summary PDF

Location: src/reports/portfolio_summary.py

One page per company, alphabetical by ticker. Each page: company name,
sector, top 6 KPIs (same set as the Day 33 tearsheet: ROE, ROCE, D/E,
Revenue CAGR 5yr, OPM, NPM), with a trend indicator comparing latest
year to prior year.

Trend direction (decided explicitly, not assumed -- spec's "up if
improved" is ambiguous for a leverage ratio):
  - ROE, ROCE, Revenue CAGR 5yr, OPM, NPM: UP = increased, DOWN = decreased
  - D/E: UP = DECREASED (lower leverage is the improvement), DOWN = increased
  - Flat: within a 2-percentage-point band for the 5 percentage metrics;
    within a 2% RELATIVE change for D/E (a ratio, not a percentage --
    an absolute 2pp band is meaningless for values like 0.1x)
  - Companies with fewer than 2 years of financial_ratios history
    (JIOFIN) get "N/A" / no trend for every KPI, not a forced guess

2026-09 fix: trend indicators use plain ASCII text ("UP"/"DOWN"/"FLAT"),
not Unicode arrow glyphs. Confirmed via real PDF text extraction:
ReportLab's default Helvetica font (WinAnsi/Latin-1 encoding) does not
support U+2191/U+2193/U+2192, so those characters rendered as garbled
glyphs ('fi', 'fl', a stray angle-bracket char) across all 92 pages.
ASCII text has no font-encoding dependency, so it's used here instead
of trying to embed a Unicode-capable font for three characters.
"""

import os
import sqlite3

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

DB_PATH = "data/nifty100.db"
OUTPUT_PATH = "reports/portfolio/portfolio_summary.pdf"

NAVY = colors.HexColor("#1a2744")
LIGHT_GREY = colors.HexColor("#f0f0f0")
GREEN = colors.HexColor("#1e7d32")
RED = colors.HexColor("#c62828")

styles = getSampleStyleSheet()

KPI_COLUMNS = [
    ("return_on_equity_pct", "ROE", "higher_better"),
    ("return_on_capital_employed_pct", "ROCE", "higher_better"),
    ("debt_to_equity", "D/E", "lower_better"),
    ("revenue_cagr_5yr", "Revenue CAGR (5yr)", "higher_better"),
    ("operating_profit_margin_pct", "OPM", "higher_better"),
    ("net_profit_margin_pct", "Net Profit Margin", "higher_better"),
]


def trend_arrow(col, direction, latest_val, prior_val):
    """
    Returns (label, color). Uses plain ASCII text, not Unicode arrow
    glyphs -- confirmed 2026-09: ReportLab's default Helvetica font
    (WinAnsi/Latin-1 encoding) does not support U+2191/U+2193/U+2192,
    so those characters rendered as garbage glyphs ('fi', 'fl', '\u203a')
    across all 92 pages. ASCII text has no such font dependency.
    """
    if pd.isna(latest_val) or pd.isna(prior_val):
        return "N/A", colors.grey

    if col == "debt_to_equity":
        if prior_val == 0:
            return "N/A", colors.grey
        pct_change = (latest_val - prior_val) / abs(prior_val) * 100
        if abs(pct_change) < 2:
            return "FLAT", colors.grey
        improved = pct_change < 0  # D/E: lower is better
    else:
        diff = latest_val - prior_val
        if abs(diff) < 2:
            return "FLAT", colors.grey
        improved = diff > 0  # higher is better for these 5

    if improved:
        return "UP", GREEN
    return "DOWN", RED


def fmt(v, suffix="%"):
    """Format a KPI value for display, returning 'N/A' for missing data."""
    if pd.isna(v):
        return "N/A"
    if suffix == "x":
        return f"{v:.1f}x"
    return f"{v:.1f}%"


def build_header(company_id, sector):
    """Build the navy header bar for a portfolio summary page."""
    header_style = ParagraphStyle(
        "header", parent=styles["Title"], textColor=colors.white, fontSize=18
    )
    sub_style = ParagraphStyle(
        "sub", parent=styles["Normal"], textColor=colors.white, fontSize=10
    )
    data = [
        [Paragraph(company_id, header_style)],
        [Paragraph(sector or "Sector: N/A", sub_style)],
    ]
    t = Table(data, colWidths=[170 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    return t


def build_kpi_table(latest_row, prior_row):
    """Build the top-6-KPI table with UP/DOWN/FLAT trend labels for a company's portfolio summary page."""
    rows = [["KPI", "Value", "Trend"]]
    arrow_colors = []

    for col, label, direction in KPI_COLUMNS:
        latest_val = latest_row.get(col)
        prior_val = prior_row.get(col) if prior_row is not None else None
        suffix = "x" if col == "debt_to_equity" else "%"
        value_str = fmt(latest_val, suffix)
        arrow, arrow_color = trend_arrow(col, direction, latest_val, prior_val)
        rows.append([label, value_str, arrow])
        arrow_colors.append(arrow_color)

    t = Table(rows, colWidths=[80 * mm, 40 * mm, 30 * mm])
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, -1), LIGHT_GREY),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
    ]
    for i, color in enumerate(arrow_colors):
        style_cmds.append(("TEXTCOLOR", (2, i + 1), (2, i + 1), color))
    t.setStyle(TableStyle(style_cmds))
    return t


def generate_portfolio_pdf():
    """Generate the one-page-per-company portfolio summary PDF for all companies, alphabetical by ticker."""
    conn = sqlite3.connect(DB_PATH)
    fr = pd.read_sql(
        """
        SELECT * FROM financial_ratios WHERE year != 'TTM' ORDER BY company_id, year
    """,
        conn,
    )
    sectors = dict(
        conn.execute("SELECT company_id, broad_sector FROM sectors;").fetchall()
    )
    companies = sorted(pd.read_sql("SELECT id FROM companies;", conn)["id"].tolist())
    conn.close()

    os.makedirs("reports/portfolio", exist_ok=True)
    doc = SimpleDocTemplate(
        OUTPUT_PATH,
        pagesize=A4,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
    )
    story = []
    skipped = []

    for i, company_id in enumerate(companies):
        hist = fr[fr["company_id"] == company_id].sort_values("year")
        if len(hist) == 0:
            skipped.append(company_id)
            continue

        latest_row = hist.iloc[-1]
        prior_row = hist.iloc[-2] if len(hist) >= 2 else None

        story.append(build_header(company_id, sectors.get(company_id)))
        story.append(Spacer(1, 10))
        story.append(build_kpi_table(latest_row, prior_row))

        if i < len(companies) - 1:
            story.append(PageBreak())

    doc.build(story)
    print(f"{OUTPUT_PATH} written: {len(companies) - len(skipped)} pages")
    if skipped:
        print(
            f"Companies with NO financial_ratios data at all (excluded entirely): {skipped}"
        )


if __name__ == "__main__":
    generate_portfolio_pdf()
