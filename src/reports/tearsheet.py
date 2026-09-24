"""
N100 Financial Intelligence Platform
Sprint 5, Day 33: PDF Tearsheet Template

Location: src/reports/tearsheet.py

2-page ReportLab tearsheet per company.
  Page 1: navy header, 6 KPI tiles (2x3), Revenue/Net Profit 10yr bar chart,
          ROE/ROCE dual-axis line chart
  Page 2: Balance Sheet composition stacked bar, Cash Flow waterfall
          (latest year), Pros (green bullets), Cons (red bullets),
          Capital Allocation badge

Data sources (all pulled fresh from existing, already-verified outputs --
nothing recomputed):
  - financial_ratios (DB): ROE, ROCE, D/E, revenue_cagr_5yr, OPM, NPM, latest year
  - profitandloss (DB): 10yr sales/net_profit history
  - balancesheet (DB): equity_capital + reserves, borrowings, other_liabilities
  - cashflow (DB): latest year CFO/CFI/CFF/net_cash_flow
  - output/pros_cons_generated.csv: pros/cons text + confidence (Day 30)
  - output/cashflow_intelligence.xlsx: capital_allocation_label,
    resolved via Day 31's fallback-aware logic, not re-derived here

Charts are rendered with matplotlib to an in-memory PNG buffer and
embedded as ReportLab Image flowables -- chosen over ReportLab's native
charting so we can reuse the dual-axis pattern already proven correct
in Sprint 4's dashboard work (explicit twinx(), not a library that
silently drops a trace).

2026-09 fix (balancesheet fiscal-year filtering): balancesheet contains
interim/quarterly snapshots (June/Sept/Dec) mixed in with annual data --
127 non-March rows confirmed across the table, e.g. TCS's 2024-09 row
sitting alongside its clean March annual history. financial_ratios was
already implicitly clean of this (verified for TCS: March-only, 12
rows). One company, SIEMENS, genuinely reports on a September fiscal
year-end -- confirmed consistent in BOTH balancesheet (12 rows, all
September) AND financial_ratios (12 rows, all September) -- so a
hardcoded "-03" filter would have wrongly zeroed out SIEMENS's balance
sheet chart. Fix: filter balancesheet to only the years that already
appear in that company's financial_ratios (year != 'TTM'), since
financial_ratios is the one source confirmed correct and
company-specific for fiscal year-end across two different cases now.

2026-09 addition (Sprint 6, Day 44): added an optional --ticker CLI
arg so a single company's tearsheet can be regenerated on its own,
without editing this file. Confirmed via `tearsheet.py --help` that no
CLI existed before this -- running the script always silently ignored
any arguments and regenerated the same fixed 5-company Day 33 test
set. That fallback behavior is preserved exactly as-is when --ticker
is omitted; --ticker is purely additive.

Output PDFs from this test run go to: reports/tearsheets/<TICKER>_tearsheet.pdf
(the top-level reports/ folder -- NOT src/reports/, which is source code only)
"""

import io
import os
import sqlite3

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

DB_PATH = "data/nifty100.db"
PROS_CONS_PATH = "output/pros_cons_generated.csv"
CASHFLOW_INTEL_PATH = "output/cashflow_intelligence.xlsx"

NAVY = colors.HexColor("#1a2744")
GREEN = colors.HexColor("#1e7d32")
RED = colors.HexColor("#c62828")
LIGHT_GREY = colors.HexColor("#f0f0f0")

styles = getSampleStyleSheet()
wrap_style = ParagraphStyle(
    "wrap", parent=styles["Normal"], fontSize=8, leading=10, wordWrap="CJK"
)
pro_style = ParagraphStyle(
    "pro",
    parent=styles["Normal"],
    fontSize=9,
    leading=12,
    textColor=GREEN,
    wordWrap="CJK",
)
con_style = ParagraphStyle(
    "con",
    parent=styles["Normal"],
    fontSize=9,
    leading=12,
    textColor=RED,
    wordWrap="CJK",
)


# ============================================================
# DATA GATHERING
# ============================================================


def gather_company_data(company_id, conn):
    """Load a company's financial_ratios, P&L, balance sheet (fiscal-year-filtered), and cash flow data needed to build its tearsheet."""
    fr = pd.read_sql(
        f"""
        SELECT * FROM financial_ratios
        WHERE company_id = '{company_id}' AND year != 'TTM'
        ORDER BY year
    """,
        conn,
    )
    pl = pd.read_sql(
        f"""
        SELECT year, sales, net_profit FROM profitandloss
        WHERE company_id = '{company_id}' AND year != 'TTM'
        ORDER BY year
    """,
        conn,
    )

    # Filter balancesheet to only the years that already appear in this
    # company's financial_ratios -- financial_ratios is the source
    # confirmed clean of interim/quarterly noise and correctly aware of
    # company-specific fiscal year-ends (March for most, September for
    # SIEMENS -- both verified 2026-09).
    valid_years = tuple(fr["year"].tolist())
    if len(valid_years) == 1:
        year_filter = f"= '{valid_years[0]}'"
    elif len(valid_years) > 1:
        year_filter = f"IN {valid_years}"
    else:
        year_filter = "= '__none__'"  # no valid years -> bs query returns empty, handled downstream

    bs = pd.read_sql(
        f"""
        SELECT year, equity_capital, reserves, borrowings, other_liabilities
        FROM balancesheet WHERE company_id = '{company_id}' AND year {year_filter}
        ORDER BY year
    """,
        conn,
    )

    cf = pd.read_sql(
        f"""
        SELECT year, operating_activity, investing_activity,
               financing_activity, net_cash_flow
        FROM cashflow WHERE company_id = '{company_id}' AND year != 'TTM'
        ORDER BY year
    """,
        conn,
    )
    ticker_row = conn.execute(
        "SELECT id FROM companies WHERE id = ?", (company_id,)
    ).fetchone()

    return fr, pl, bs, cf, ticker_row


def get_pros_cons(company_id):
    """Load a company's generated pros and cons text from output/pros_cons_generated.csv."""
    df = pd.read_csv(PROS_CONS_PATH)
    company_df = df[df["company_id"] == company_id]
    pros = company_df[company_df["type"] == "pro"]["text"].tolist()
    cons = company_df[company_df["type"] == "con"]["text"].tolist()
    return pros, cons


def get_capital_allocation_label(company_id):
    """Load a company's capital allocation pattern label from output/cashflow_intelligence.xlsx."""
    df = pd.read_excel(CASHFLOW_INTEL_PATH)
    row = df[df["company_id"] == company_id]
    if len(row) == 0:
        return "Unknown"
    return row["capital_allocation_label"].iloc[0]


# ============================================================
# CHART BUILDERS (matplotlib -> PNG buffer -> ReportLab Image)
# ============================================================


def make_revenue_profit_chart(pl):
    """Build the 10-year Revenue vs Net Profit bar chart as a ReportLab Image."""
    last10 = pl.tail(10)
    fig, ax = plt.subplots(figsize=(6.2, 2.6), dpi=150)
    x = range(len(last10))
    width = 0.4
    ax.bar(
        [i - width / 2 for i in x],
        last10["sales"],
        width,
        label="Revenue",
        color="#2a5298",
    )
    ax.bar(
        [i + width / 2 for i in x],
        last10["net_profit"],
        width,
        label="Net Profit",
        color="#4caf50",
    )
    ax.set_xticks(list(x))
    ax.set_xticklabels(last10["year"], rotation=45, ha="right", fontsize=7)
    ax.set_title("Revenue vs Net Profit (10yr)", fontsize=9)
    ax.legend(fontsize=7)
    ax.tick_params(labelsize=7)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=160 * mm, height=65 * mm)


def make_roe_roce_chart(fr):
    """Build the 10-year ROE vs ROCE dual-axis line chart as a ReportLab Image."""
    last10 = fr.tail(10)
    fig, ax1 = plt.subplots(figsize=(6.2, 2.6), dpi=150)
    ax2 = (
        ax1.twinx()
    )  # explicit dual-axis -- confirmed pattern from Sprint 4, never make_subplots(secondary_y=True)

    ax1.plot(
        last10["year"],
        last10["return_on_equity_pct"],
        color="#1a2744",
        marker="o",
        label="ROE %",
    )
    ax2.plot(
        last10["year"],
        last10["return_on_capital_employed_pct"],
        color="#c62828",
        marker="s",
        label="ROCE %",
    )

    ax1.set_ylabel("ROE %", fontsize=7)
    ax2.set_ylabel("ROCE %", fontsize=7)
    ax1.set_xticks(
        range(len(last10))
    )  # pin tick positions before labeling, same pattern as the other 3 charts
    ax1.set_xticklabels(last10["year"], rotation=45, ha="right", fontsize=7)
    ax1.tick_params(labelsize=7)
    ax2.tick_params(labelsize=7)
    ax1.set_title("ROE vs ROCE (10yr)", fontsize=9)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=7, loc="upper left")

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=160 * mm, height=65 * mm)


def make_balance_sheet_stack_chart(bs):
    """Build the balance sheet composition stacked bar chart as a ReportLab Image, or None if no data is available."""
    if len(bs) == 0:
        return None
    last10 = bs.tail(10).copy()
    last10["equity"] = last10["equity_capital"].fillna(0) + last10["reserves"].fillna(0)

    fig, ax = plt.subplots(figsize=(6.2, 2.8), dpi=150)
    x = range(len(last10))
    ax.bar(x, last10["equity"], label="Equity", color="#2a5298")
    ax.bar(
        x,
        last10["borrowings"],
        bottom=last10["equity"],
        label="Borrowings",
        color="#c62828",
    )
    bottom2 = last10["equity"] + last10["borrowings"].fillna(0)
    ax.bar(
        x,
        last10["other_liabilities"],
        bottom=bottom2,
        label="Other Liabilities",
        color="#9e9e9e",
    )

    ax.set_xticks(list(x))
    ax.set_xticklabels(last10["year"], rotation=45, ha="right", fontsize=7)
    ax.set_title("Balance Sheet Composition (10yr)", fontsize=9)
    ax.legend(fontsize=7)
    ax.tick_params(labelsize=7)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=160 * mm, height=68 * mm)


def make_cashflow_waterfall_chart(cf):
    """Build the latest-year cash flow waterfall chart as a ReportLab Image, or None if no data is available."""
    if len(cf) == 0:
        return None
    latest = cf.iloc[-1]
    labels = ["CFO", "CFI", "CFF", "Net Cash Flow"]
    values = [
        latest["operating_activity"],
        latest["investing_activity"],
        latest["financing_activity"],
        latest["net_cash_flow"],
    ]
    colors_list = ["#2a5298" if v is not None and v >= 0 else "#c62828" for v in values]

    fig, ax = plt.subplots(figsize=(6.2, 2.4), dpi=150)
    ax.bar(labels, values, color=colors_list)
    ax.axhline(0, color="black", linewidth=0.6)
    ax.set_title(f"Cash Flow Waterfall ({latest['year']})", fontsize=9)
    ax.tick_params(labelsize=7)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=160 * mm, height=58 * mm)


# ============================================================
# LAYOUT BUILDERS
# ============================================================


def build_header(company_id):
    """Build the navy header bar showing the company ticker."""
    header_style = ParagraphStyle(
        "header", parent=styles["Title"], textColor=colors.white, fontSize=18
    )
    data = [[Paragraph(f"{company_id}", header_style)]]
    t = Table(data, colWidths=[170 * mm])
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


def build_kpi_tiles(fr_latest):
    """Build the 2x3 grid of latest-year KPI tiles."""

    def fmt(v, suffix="%"):
        """Format a KPI value for display, returning 'N/A' for missing data."""
        if pd.isna(v):
            return "N/A"
        return f"{v:.1f}{suffix}"

    kpis = [
        ("ROE", fmt(fr_latest.get("return_on_equity_pct"))),
        ("ROCE", fmt(fr_latest.get("return_on_capital_employed_pct"))),
        ("D/E", fmt(fr_latest.get("debt_to_equity"), "x")),
        ("Revenue CAGR (5yr)", fmt(fr_latest.get("revenue_cagr_5yr"))),
        ("OPM", fmt(fr_latest.get("operating_profit_margin_pct"))),
        ("Net Profit Margin", fmt(fr_latest.get("net_profit_margin_pct"))),
    ]

    label_style = ParagraphStyle(
        "kpi_label", parent=styles["Normal"], fontSize=8, wordWrap="CJK"
    )
    value_style = ParagraphStyle(
        "kpi_value", parent=styles["Normal"], fontSize=13, textColor=NAVY, leading=16
    )

    cells = []
    for label, value in kpis:
        cell_content = [Paragraph(value, value_style), Paragraph(label, label_style)]
        cells.append(cell_content)

    rows = [cells[0:3], cells[3:6]]
    t = Table(rows, colWidths=[57 * mm] * 3, rowHeights=[24 * mm] * 2)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GREY),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.white),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return t


def build_pros_cons_section(pros, cons):
    """Build the green pros / red cons bullet-list section."""
    elements = []
    elements.append(
        Paragraph("Pros", ParagraphStyle("pros_head", fontSize=11, textColor=GREEN))
    )
    if pros:
        for p in pros:
            elements.append(Paragraph(f"&#8226; {p}", pro_style))
    else:
        elements.append(
            Paragraph("No pros identified above confidence threshold.", wrap_style)
        )

    elements.append(Spacer(1, 6))
    elements.append(
        Paragraph("Cons", ParagraphStyle("cons_head", fontSize=11, textColor=RED))
    )
    if cons:
        for c in cons:
            elements.append(Paragraph(f"&#8226; {c}", con_style))
    else:
        elements.append(
            Paragraph("No cons identified above confidence threshold.", wrap_style)
        )

    return elements


def build_capital_allocation_badge(label):
    """Build the capital allocation pattern badge shown at the bottom of page 2."""
    badge_style = ParagraphStyle(
        "badge",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.white,
        alignment=1,
    )
    t = Table(
        [[Paragraph(f"Capital Allocation Pattern: {label}", badge_style)]],
        colWidths=[170 * mm],
    )
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return t


# ============================================================
# MAIN TEARSHEET BUILDER
# ============================================================


def generate_tearsheet(company_id, output_path):
    """Generate the 2-page tearsheet PDF for one company; returns (False, reason) if it has fewer than 3 years of ratio history."""
    conn = sqlite3.connect(DB_PATH)
    fr, pl, bs, cf, _ticker_row = gather_company_data(company_id, conn)
    conn.close()

    if len(fr) < 3:
        return False, f"Skipped {company_id}: fewer than 3 years of ratio history"

    fr_latest = fr.iloc[-1]
    pros, cons = get_pros_cons(company_id)
    capital_allocation_label = get_capital_allocation_label(company_id)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
    )
    story = []

    # --- PAGE 1 ---
    story.append(build_header(company_id))
    story.append(Spacer(1, 10))
    story.append(build_kpi_tiles(fr_latest))
    story.append(Spacer(1, 10))
    story.append(make_revenue_profit_chart(pl))
    story.append(Spacer(1, 6))
    story.append(make_roe_roce_chart(fr))

    story.append(PageBreak())

    # --- PAGE 2 ---
    story.append(build_header(company_id))
    story.append(Spacer(1, 10))
    bs_chart = make_balance_sheet_stack_chart(bs)
    if bs_chart:
        story.append(bs_chart)
    else:
        story.append(
            Paragraph("Balance sheet composition data not available.", wrap_style)
        )
    story.append(Spacer(1, 6))
    cf_chart = make_cashflow_waterfall_chart(cf)
    if cf_chart:
        story.append(cf_chart)
    else:
        story.append(Paragraph("Cash flow data not available.", wrap_style))
    story.append(Spacer(1, 10))
    story.extend(build_pros_cons_section(pros, cons))
    story.append(Spacer(1, 10))
    story.append(build_capital_allocation_badge(capital_allocation_label))

    doc.build(story)
    return True, f"Generated {output_path}"


# ============================================================
# CLI ENTRY POINT
#
# With --ticker: generate a single company's tearsheet.
# Without any args: unchanged from Day 33 -- reruns the original
# 5-company test harness (TCS, HDFCBANK, RELIANCE, SUNPHARMA,
# TATASTEEL), exactly as before this addition.
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate a company tearsheet PDF. With no arguments, "
        "reruns the original Day 33 test harness (5 companies "
        "across different sectors: TCS, HDFCBANK, RELIANCE, "
        "SUNPHARMA, TATASTEEL). Pass --ticker for a single "
        "arbitrary company instead."
    )
    parser.add_argument(
        "--ticker",
        default=None,
        help="Generate a tearsheet for a single ticker (e.g. --ticker INFY). "
        "If omitted, falls back to the 5-company test harness.",
    )
    args = parser.parse_args()

    os.makedirs("reports/tearsheets", exist_ok=True)

    if args.ticker:
        company_id = args.ticker.strip().upper()
        output_path = f"reports/tearsheets/{company_id}_tearsheet.pdf"
        try:
            ok, msg = generate_tearsheet(company_id, output_path)
            print(msg)
            if ok:
                size_kb = os.path.getsize(output_path) / 1024
                print(f"  -> {size_kb:.1f} KB")
            else:
                print(
                    f"Tearsheet not generated for {company_id} -- check the "
                    f"message above (e.g. insufficient history, unknown ticker)."
                )
        except Exception as e:  # noqa: BLE001 -- intentional: one company's failure must not abort the batch
            print(f"FAILED on {company_id}: {e}")
    else:
        test_companies = ["TCS", "HDFCBANK", "RELIANCE", "SUNPHARMA", "TATASTEEL"]
        for company_id in test_companies:
            output_path = f"reports/tearsheets/{company_id}_tearsheet.pdf"
            try:
                ok, msg = generate_tearsheet(company_id, output_path)
                print(msg)
                if ok:
                    size_kb = os.path.getsize(output_path) / 1024
                    print(f"  -> {size_kb:.1f} KB")
            except Exception as e:   # noqa: BLE001 -- intentional: one company's failure must not abort the batch
                print(f"FAILED on {company_id}: {e}")
