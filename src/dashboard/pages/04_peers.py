"""
N100 Financial Intelligence Platform
Sprint 4, Day 24: Peer Comparison Screen
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "utils"))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sqlite3
from db import get_peers, _connect

st.title("Peer Comparison")

conn = _connect()
groups = pd.read_sql("SELECT DISTINCT peer_group_name FROM peer_groups ORDER BY peer_group_name;", conn)["peer_group_name"].tolist()
conn.close()

selected_group = st.selectbox("Select Peer Group", groups)

peers_long = get_peers(selected_group)

if peers_long.empty:
    st.warning("No data found for this peer group.")
    st.stop()

company_options = peers_long["company_id"].unique().tolist()
selected_company = st.selectbox("Select Company for Radar Chart", company_options)

# --- Radar chart: selected company's 8 metrics vs peer group average ---
RADAR_METRICS = [
    "return_on_equity_pct", "return_on_capital_employed_pct", "net_profit_margin_pct",
    "debt_to_equity", "free_cash_flow_cr", "pat_cagr_5yr", "revenue_cagr_5yr",
]

conn = _connect()
metrics_df = pd.read_sql("""
    SELECT fr.company_id, fr.return_on_equity_pct, fr.return_on_capital_employed_pct,
           fr.net_profit_margin_pct, fr.debt_to_equity, fr.free_cash_flow_cr,
           fr.pat_cagr_5yr, fr.revenue_cagr_5yr, fr.composite_quality_score
    FROM financial_ratios fr
    JOIN peer_groups pg ON fr.company_id = pg.company_id
    WHERE pg.peer_group_name = ?
      AND fr.year = (SELECT MAX(y2.year) FROM financial_ratios y2 WHERE y2.company_id = fr.company_id)
""", conn, params=(selected_group,))
conn.close()

labels = ["ROE", "ROCE", "NPM", "D/E", "FCF", "PAT CAGR 5yr", "Rev CAGR 5yr", "Composite"]
all_metrics = RADAR_METRICS + ["composite_quality_score"]


def normalize(series, value, invert=False):
    valid = series.dropna()
    if len(valid) == 0 or pd.isna(value):
        return 50
    p10, p90 = valid.quantile(0.10), valid.quantile(0.90)
    if p90 == p10:
        return 50
    clipped = max(p10, min(p90, value))
    score = (clipped - p10) / (p90 - p10) * 100
    return 100 - score if invert else score


company_row = metrics_df[metrics_df["company_id"] == selected_company]
if company_row.empty:
    st.warning("No ratio data available for this company.")
else:
    company_row = company_row.iloc[0]
    company_values = []
    avg_values = []
    for m in all_metrics:
        invert = (m == "debt_to_equity")
        company_values.append(normalize(metrics_df[m], company_row[m], invert))
        avg_values.append(normalize(metrics_df[m], metrics_df[m].mean(), invert))

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=company_values + [company_values[0]], theta=labels + [labels[0]],
                                    fill="toself", name=selected_company))
    fig.add_trace(go.Scatterpolar(r=avg_values + [avg_values[0]], theta=labels + [labels[0]],
                                    name="Peer Group Avg", line=dict(dash="dash")))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), height=500)
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# --- Side-by-side KPI table, benchmark row highlighted ---
st.subheader(f"{selected_group} — Full Comparison")

pivot = peers_long.pivot_table(index=["company_id", "company_name", "is_benchmark"],
                                 columns="metric", values="value").reset_index()

def highlight_benchmark(row):
    color = "background-color: #4a3b00" if row["is_benchmark"] == 1 else ""
    return [color] * len(row)

st.dataframe(
    pivot.drop(columns=["is_benchmark"]).style.apply(
        lambda row: ["background-color: #4a3b00" if pivot.loc[row.name, "is_benchmark"] == 1 else "" for _ in row],
        axis=1
    ),
    hide_index=True, use_container_width=True
)