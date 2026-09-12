"""
N100 Financial Intelligence Platform
Sprint 4, Day 23: Company Profile Screen
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "utils"))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from db import get_companies, get_ratios, get_ratios_history, get_pl, get_pros_cons

st.title("Company Profile")

companies_df = get_companies()

# --- Search box with autocomplete-style selection ---
# Streamlit's selectbox has built-in type-to-filter, which serves as the
# autocomplete behavior the spec asks for -- no separate widget needed.
search_options = [f"{row['id']} — {row['company_name']}" for _, row in companies_df.iterrows()]
selected = st.selectbox("Search company name or ticker", options=[""] + search_options)

if not selected:
    st.info("Start typing a company name or ticker above to see its profile.")
    st.stop()

ticker = selected.split(" — ")[0]

company_row = companies_df[companies_df["id"] == ticker]
if company_row.empty:
    st.error("Ticker not found — please try another")
    st.stop()

company = company_row.iloc[0]

# --- Company card ---
st.header(f"{company['company_name']} ({ticker})")
col1, col2 = st.columns([1, 2])
with col1:
    st.write(f"**Sector:** {company['broad_sector'] or 'N/A'}")
    st.write(f"**Sub-sector:** {company['sub_sector'] or 'N/A'}")
    st.write(f"**NSE Ticker:** {ticker}")
with col2:
    st.write(company["about_company"] or "No description available.")

st.divider()

# --- 6 KPI tiles (latest fiscal year, never TTM) ---
latest_ratios = get_ratios(ticker)

if latest_ratios.empty:
    st.warning("No financial ratio data available for this company yet.")
else:
    r = latest_ratios.iloc[0]

    def fmt(value, suffix=""):
        return f"{value:.1f}{suffix}" if pd.notna(value) else "N/A"

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("ROE", fmt(r["return_on_equity_pct"], "%"))
    c2.metric("ROCE", fmt(r["return_on_capital_employed_pct"], "%"))
    c3.metric("Net Profit Margin", fmt(r["net_profit_margin_pct"], "%"))
    c4.metric("D/E", fmt(r["debt_to_equity"]))
    c5.metric("Revenue CAGR 5yr", fmt(r["revenue_cagr_5yr"], "%"))
    c6.metric("FCF (Cr)", fmt(r["free_cash_flow_cr"]))

st.divider()

# --- Historical charts ---
pl_history = get_pl(ticker)
ratios_history = get_ratios_history(ticker)

if len(pl_history) < 2:
    st.info(f"Limited history available ({len(pl_history)} year(s)) — charts need at least 2 years to display a trend.")
else:
    # Revenue and Net Profit on separate y-axes -- a shared axis makes
    # Net Profit's bars visually flatten to near-nothing, since profit
    # is always a fraction of revenue. Confirmed on ABB, SBIN, HDFCBANK.
    st.subheader("Revenue & Net Profit (up to 10 years)")
    pl_recent = pl_history.tail(10)

    # Flag a likely partial/stub first year -- e.g. a company listed
    # mid-year will show one year's sales as a small fraction of the
    # next, making the bar chart look extreme even though it's accurate.
    # Confirmed on JIOFIN: 2023-03 sales=45 Cr vs 2024-03 sales=1855 Cr,
    # a genuine ~41x jump from a partial listing-year, not a data error.
    if len(pl_recent) >= 2:
        first_year_sales = pl_recent["sales"].iloc[0]
        second_year_sales = pl_recent["sales"].iloc[1]
        if pd.notna(first_year_sales) and pd.notna(second_year_sales) and first_year_sales > 0:
            if second_year_sales / first_year_sales > 10:
                st.caption(f"⚠️ {pl_recent['year'].iloc[0]} shows unusually low revenue relative to "
                           f"the following year — likely a partial/stub reporting period (e.g. a "
                           f"recently listed or demerged company).")

    fig1 = go.Figure()
    fig1.add_trace(go.Bar(x=pl_recent["year"], y=pl_recent["sales"], name="Revenue (Cr)", yaxis="y1"))
    fig1.add_trace(go.Bar(x=pl_recent["year"], y=pl_recent["net_profit"], name="Net Profit (Cr)", yaxis="y2"))
    fig1.update_layout(
        barmode="group", height=400, margin=dict(t=30, b=10),
        yaxis=dict(title="Revenue (Cr)"),
        yaxis2=dict(title="Net Profit (Cr)", overlaying="y", side="right"),
    )
    st.plotly_chart(fig1, use_container_width=True)

    if len(ratios_history) >= 2:
        # Explicit dual-axis via named yaxis/yaxis2 on each trace, rather
        # than make_subplots(secondary_y=True) -- the latter silently
        # failed to render the ROE line (confirmed on HDFCBANK: clean
        # float64 data, values 14-20%, but only ROCE ever drew).
        st.subheader("ROE vs ROCE (up to 10 years)")
        r_recent = ratios_history.tail(10)

        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=r_recent["year"], y=r_recent["return_on_equity_pct"],
            name="ROE %", mode="lines+markers", yaxis="y1",
            line=dict(color="#3b82f6"),
        ))
        fig2.add_trace(go.Scatter(
            x=r_recent["year"], y=r_recent["return_on_capital_employed_pct"],
            name="ROCE %", mode="lines+markers", yaxis="y2",
            line=dict(color="#f97316"),
        ))
        fig2.update_layout(
            height=400,
            margin=dict(t=30, b=10),
            yaxis=dict(title="ROE %", side="left"),
            yaxis2=dict(title="ROCE %", side="right", overlaying="y"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Not enough ratio history to plot ROE/ROCE trend.")

st.divider()

# --- Pros and cons ---
st.subheader("Pros & Cons")
pros_cons = get_pros_cons(ticker)
if pros_cons.empty:
    st.caption("No pros/cons data available for this company.")
else:
    for _, row in pros_cons.iterrows():
        if pd.notna(row["pros"]):
            st.success(f"✅ {row['pros']}")
        if pd.notna(row["cons"]):
            st.error(f"❌ {row['cons']}")