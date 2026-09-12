"""
N100 Financial Intelligence Platform
Sprint 4, Day 25: Trend Analysis Screen
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "utils"))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from db import get_companies, get_ratios_history

st.title("Trend Analysis")

companies_df = get_companies()
search_options = [f"{row['id']} — {row['company_name']}" for _, row in companies_df.iterrows()]
selected = st.selectbox("Search company", options=[""] + search_options)

if not selected:
    st.info("Select a company to see its trend.")
    st.stop()

ticker = selected.split(" — ")[0]
history = get_ratios_history(ticker)

if history.empty:
    st.warning("No ratio history available for this company.")
    st.stop()

AVAILABLE_METRICS = {
    "ROE %": "return_on_equity_pct",
    "ROCE %": "return_on_capital_employed_pct",
    "Net Profit Margin %": "net_profit_margin_pct",
    "D/E": "debt_to_equity",
    "Revenue CAGR 5yr %": "revenue_cagr_5yr",
    "PAT CAGR 5yr %": "pat_cagr_5yr",
    "Composite Quality Score": "composite_quality_score",
}

selected_metrics = st.multiselect(
    "Select up to 3 metrics to overlay", options=list(AVAILABLE_METRICS.keys()),
    default=["ROE %"], max_selections=3,
)

if not selected_metrics:
    st.info("Select at least one metric to plot.")
    st.stop()

history_recent = history.tail(10)

fig = go.Figure()
for label in selected_metrics:
    col = AVAILABLE_METRICS[label]
    values = history_recent[col]
    yoy_change = values.pct_change() * 100

    hover_text = [
        f"{label}: {v:.1f}<br>YoY: {c:+.1f}%" if pd.notna(v) and pd.notna(c) else f"{label}: {v:.1f}" if pd.notna(v) else "N/A"
        for v, c in zip(values, yoy_change)
    ]

    fig.add_trace(go.Scatter(
        x=history_recent["year"], y=values, name=label,
        mode="lines+markers", text=hover_text, hoverinfo="text+x",
    ))

fig.update_layout(height=500, margin=dict(t=30, b=10), hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)

st.caption("Hover over a point to see the year-over-year % change alongside the value.")