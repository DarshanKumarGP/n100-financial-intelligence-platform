"""
N100 Financial Intelligence Platform
Sprint 4, Day 25: Sector Analysis Screen
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "utils"))

import streamlit as st
import pandas as pd
import plotly.express as px
from db import get_sectors, _connect

st.title("Sector Analysis")

sectors_df = get_sectors()
selected_sector = st.selectbox("Select Sector", sectors_df["broad_sector"].tolist())

conn = _connect()
sector_data = pd.read_sql("""
    SELECT fr.company_id, c.company_name, s.sub_sector,
           p.sales, fr.return_on_equity_pct, mc.market_cap_crore
    FROM financial_ratios fr
    JOIN companies c ON fr.company_id = c.id
    JOIN sectors s ON fr.company_id = s.company_id
    LEFT JOIN profitandloss p ON fr.company_id = p.company_id AND fr.year = p.year
    LEFT JOIN market_cap mc ON fr.company_id = mc.company_id
        AND mc.year = CAST(SUBSTR(fr.year, 1, 4) AS INTEGER)
    WHERE s.broad_sector = ?
      AND fr.year = (SELECT MAX(y2.year) FROM financial_ratios y2 WHERE y2.company_id = fr.company_id)
""", conn, params=(selected_sector,))
conn.close()

# Defensive: bubble chart needs sales, ROE, and market cap all present.
plot_data = sector_data.dropna(subset=["sales", "return_on_equity_pct", "market_cap_crore"])
missing_count = len(sector_data) - len(plot_data)

if missing_count > 0:
    st.caption(f"{missing_count} of {len(sector_data)} companies in this sector are missing "
               f"data needed for the bubble chart and are excluded from it below.")

if plot_data.empty:
    st.warning("No companies in this sector have complete data for the bubble chart.")
else:
    fig = px.scatter(
        plot_data, x="sales", y="return_on_equity_pct", size="market_cap_crore",
        color="sub_sector", hover_name="company_name",
        labels={"sales": "Revenue (Cr)", "return_on_equity_pct": "ROE (%)", "market_cap_crore": "Market Cap"},
        size_max=50,
    )
    fig.update_layout(height=500, margin=dict(t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

st.divider()

st.subheader(f"{selected_sector} — Median KPIs")
median_kpis = sector_data[["return_on_equity_pct"]].median()
conn = _connect()
full_ratios = pd.read_sql("""
    SELECT fr.debt_to_equity, fr.net_profit_margin_pct, fr.revenue_cagr_5yr
    FROM financial_ratios fr
    JOIN sectors s ON fr.company_id = s.company_id
    WHERE s.broad_sector = ? AND fr.year = (
        SELECT MAX(y2.year) FROM financial_ratios y2 WHERE y2.company_id = fr.company_id
    )
""", conn, params=(selected_sector,))
conn.close()

col_a, col_b = st.columns(2)

with col_a:
    pct_fig = px.bar(
        x=["ROE %", "NPM %", "Revenue CAGR 5yr %"],
        y=[
            sector_data["return_on_equity_pct"].median(),
            full_ratios["net_profit_margin_pct"].median(),
            full_ratios["revenue_cagr_5yr"].median(),
        ],
        title="Percentage Metrics",
    )
    pct_fig.update_layout(height=350, margin=dict(t=40, b=10), yaxis_title="Median %")
    st.plotly_chart(pct_fig, use_container_width=True)

with col_b:
    de_fig = px.bar(x=["D/E"], y=[full_ratios["debt_to_equity"].median()], title="Debt-to-Equity")
    de_fig.update_layout(height=350, margin=dict(t=40, b=10), yaxis_title="Median D/E")
    st.plotly_chart(de_fig, use_container_width=True)