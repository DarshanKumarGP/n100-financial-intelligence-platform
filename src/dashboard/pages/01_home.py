"""
N100 Financial Intelligence Platform
Sprint 4, Day 23: Home Screen
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "utils"))

import streamlit as st
import pandas as pd
import plotly.express as px
from db import get_companies, get_sectors, _connect

st.title("Home — Nifty 100 Universe Overview")

year_options = [2019, 2020, 2021, 2022, 2023, 2024]
selected_year = st.sidebar.selectbox("Select Year", year_options, index=len(year_options) - 1)
fiscal_year_str = f"{selected_year}-03"

conn = _connect()
ratios_for_year = pd.read_sql(
    "SELECT * FROM financial_ratios WHERE year = ?", conn, params=(fiscal_year_str,)
)
conn.close()

if ratios_for_year.empty:
    st.warning(f"No financial_ratios data found for fiscal year {fiscal_year_str}. "
               f"Showing latest available year instead.")
    conn = _connect()
    ratios_for_year = pd.read_sql(
        "SELECT * FROM financial_ratios WHERE year != 'TTM' ORDER BY year DESC LIMIT 92", conn
    )
    conn.close()

# --- 6 summary KPI tiles ---
# NOTE: uses MEDIAN, not mean, for Average ROE -- confirmed via direct
# query that a handful of extreme small-equity-base outliers (HAL 3816%,
# BEL 4744%, INDIGO 892% raw ROE) drag the mean from a realistic ~21%
# up to a meaningless 125%. Median is naturally robust to this without
# needing a hardcoded exclusion list, which wouldn't generalize to
# outliers in other years/metrics we haven't specifically checked.
col1, col2, col3, col4, col5, col6 = st.columns(6)

median_roe = ratios_for_year["return_on_equity_pct"].median()
median_de = ratios_for_year["debt_to_equity"].median()
total_companies = len(get_companies())
median_rev_cagr = ratios_for_year["revenue_cagr_5yr"].median()
debt_free_count = (ratios_for_year["debt_to_equity"] < 0.01).sum()

conn = _connect()
median_pe = pd.read_sql(
    "SELECT pe_ratio FROM market_cap WHERE year = ?", conn, params=(selected_year,)
)["pe_ratio"].median()
conn.close()

col1.metric("Median ROE", f"{median_roe:.1f}%" if pd.notna(median_roe) else "N/A")
col2.metric("Median P/E", f"{median_pe:.1f}x" if pd.notna(median_pe) else "N/A")
col3.metric("Median D/E", f"{median_de:.2f}" if pd.notna(median_de) else "N/A")
col4.metric("Total Companies", total_companies)
col5.metric("Median Rev CAGR 5yr", f"{median_rev_cagr:.1f}%" if pd.notna(median_rev_cagr) else "N/A")
col6.metric("Debt-Free Companies", int(debt_free_count))

st.divider()

col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("Sector Breakdown")
    sectors_df = get_sectors()
    fig = px.pie(sectors_df, values="company_count", names="broad_sector", hole=0.5)
    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.subheader("Top 5 by Composite Quality Score")
    top5 = ratios_for_year.merge(
        get_companies()[["id", "company_name"]], left_on="company_id", right_on="id"
    ).sort_values("composite_quality_score", ascending=False).head(5)
    st.dataframe(
        top5[["company_id", "company_name", "composite_quality_score"]].rename(
            columns={"company_id": "Ticker", "company_name": "Company", "composite_quality_score": "Score"}
        ),
        hide_index=True, use_container_width=True
    )