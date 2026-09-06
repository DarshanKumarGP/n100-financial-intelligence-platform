"""
N100 Financial Intelligence Platform
Sprint 3, Day 19: Radar Charts

Two chart types, per spec:
  - Grouped companies (56 of 92): 8-axis radar, company polygon filled,
    peer group average as a dashed overlay.
  - Ungrouped companies (36 of 92): standalone bar chart, composite score
    vs the Nifty 100 universe average -- spec explicitly calls for a
    simpler chart here, not a radar with no peer to compare against.

All 8 radar axes are normalized to 0-100 (reusing the same P10/P90
winsorization pattern from Day 17) before plotting -- raw values would
be visually meaningless on one chart (ROE ~15-50, D/E ~0-2, Composite
Score ~0-100 are wildly different scales).
"""

import sys
import os
import sqlite3
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # no display needed, just file output
import matplotlib.pyplot as plt

DB_PATH = "data/nifty100.db"
OUTPUT_DIR = "reports/radar_charts"

RADAR_METRICS = [
    ("return_on_equity_pct", "ROE", False),
    ("return_on_capital_employed_pct", "ROCE", False),
    ("net_profit_margin_pct", "NPM", False),
    ("debt_to_equity", "D/E", True),   # invert=True: lower is better
    ("free_cash_flow_cr", "FCF", False),
    ("pat_cagr_5yr", "PAT CAGR 5yr", False),
    ("revenue_cagr_5yr", "Rev CAGR 5yr", False),
    ("composite_quality_score", "Composite", False),
]


def load_latest_snapshot(conn):
    query = """
        SELECT fr.company_id, fr.year, c.company_name,
               fr.return_on_equity_pct, fr.return_on_capital_employed_pct,
               fr.net_profit_margin_pct, fr.debt_to_equity,
               fr.free_cash_flow_cr, fr.pat_cagr_5yr, fr.revenue_cagr_5yr,
               fr.composite_quality_score, pg.peer_group_name
        FROM financial_ratios fr
        JOIN companies c ON fr.company_id = c.id
        LEFT JOIN peer_groups pg ON fr.company_id = pg.company_id
        WHERE fr.year = (
            SELECT MAX(fr2.year) FROM financial_ratios fr2
            WHERE fr2.company_id = fr.company_id
        )
    """
    return pd.read_sql(query, conn)


def normalize_axis(series, value, invert=False):
    """Same P10/P90 winsorization pattern used throughout Sprint 3."""
    valid = series.dropna()
    if len(valid) == 0 or value is None or pd.isna(value):
        return 50  # neutral midpoint if we can't normalize -- avoids a blank/zero axis
    p10, p90 = valid.quantile(0.10), valid.quantile(0.90)
    if p90 == p10:
        return 50
    clipped = max(p10, min(p90, value))
    score = (clipped - p10) / (p90 - p10) * 100
    return 100 - score if invert else score


def generate_radar_chart(company_row, peer_group_df, ticker, os_path):
    """8-axis radar: company polygon (filled) + peer group average (dashed)."""
    labels = [label for _, label, _ in RADAR_METRICS]
    num_axes = len(labels)

    company_values = []
    peer_avg_values = []
    for col, _, invert in RADAR_METRICS:
        company_norm = normalize_axis(peer_group_df[col], company_row[col], invert)
        company_values.append(company_norm)

        peer_avg_raw = peer_group_df[col].mean()
        peer_avg_norm = normalize_axis(peer_group_df[col], peer_avg_raw, invert)
        peer_avg_values.append(peer_avg_norm)

    angles = np.linspace(0, 2 * np.pi, num_axes, endpoint=False).tolist()
    company_values += company_values[:1]
    peer_avg_values += peer_avg_values[:1]
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    ax.plot(angles, company_values, color="#2563eb", linewidth=2, label=company_row["company_id"])
    ax.fill(angles, company_values, color="#2563eb", alpha=0.25)
    ax.plot(angles, peer_avg_values, color="#94a3b8", linewidth=1.5, linestyle="--", label="Peer Group Avg")

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_ylim(0, 100)
    ax.set_title(f"{company_row['company_id']} vs Peer Group Average", fontsize=13, pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=10)

    plt.tight_layout()
    plt.savefig(os_path, dpi=100, bbox_inches="tight")
    plt.close(fig)


def generate_standalone_chart(company_row, universe_df, ticker, os_path):
    """Simpler bar chart for ungrouped companies: composite score vs Nifty 100 average."""
    company_score = company_row["composite_quality_score"]
    universe_avg = universe_df["composite_quality_score"].mean()

    fig, ax = plt.subplots(figsize=(5, 5))
    bars = ax.bar(
        [company_row["company_id"], "Nifty 100 Avg"],
        [company_score if pd.notna(company_score) else 0, universe_avg],
        color=["#2563eb", "#94a3b8"]
    )
    ax.set_ylabel("Composite Quality Score", fontsize=11)
    ax.set_title(f"{company_row['company_id']} — No Peer Group Assigned\n(Composite Score vs Nifty 100 Average)", fontsize=12)
    ax.set_ylim(0, 100)
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f"{height:.1f}", xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points", ha="center", fontsize=10)

    plt.tight_layout()
    plt.savefig(os_path, dpi=100, bbox_inches="tight")
    plt.close(fig)


def main(sample_tickers=None):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    df = load_latest_snapshot(conn)
    conn.close()

    targets = df if sample_tickers is None else df[df["company_id"].isin(sample_tickers)]

    generated = 0
    for _, row in targets.iterrows():
        ticker = row["company_id"]
        out_path = os.path.join(OUTPUT_DIR, f"{ticker}_radar.png")

        if pd.notna(row["peer_group_name"]):
            peer_group_df = df[df["peer_group_name"] == row["peer_group_name"]]
            generate_radar_chart(row, peer_group_df, ticker, out_path)
            print(f"  {ticker}: radar chart (peer group: {row['peer_group_name']})")
        else:
            generate_standalone_chart(row, df, ticker, out_path)
            print(f"  {ticker}: standalone chart (no peer group)")

        generated += 1

    print(f"\n{generated} charts written to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()