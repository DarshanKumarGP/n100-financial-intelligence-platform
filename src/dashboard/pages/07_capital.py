"""
N100 Financial Intelligence Platform
Sprint 4, Day 25: Capital Allocation Map
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "utils"))

import streamlit as st
import pandas as pd
import plotly.express as px
from db import _connect

st.title("Capital Allocation Map")

conn = _connect()
alloc = pd.read_csv("output/capital_allocation.csv")
companies_df = pd.read_sql("SELECT id, company_name FROM companies;", conn)
conn.close()

# Latest year per company, since capital_allocation.csv has one row per company-year
alloc_latest = alloc.sort_values("year").groupby("company_id").tail(1)
alloc_latest = alloc_latest.merge(companies_df, left_on="company_id", right_on="id")

pattern_counts = alloc_latest["pattern_label"].value_counts().reset_index()
pattern_counts.columns = ["pattern_label", "count"]

fig = px.treemap(
    alloc_latest, path=["pattern_label", "company_id"],
    title="Capital Allocation Patterns — Latest Year per Company",
)
fig.update_layout(height=600, margin=dict(t=40, b=10))
st.plotly_chart(fig, use_container_width=True)

st.divider()

st.subheader("Browse by Pattern")
selected_pattern = st.selectbox("Select a pattern to see the company list", pattern_counts["pattern_label"].tolist())
pattern_companies = alloc_latest[alloc_latest["pattern_label"] == selected_pattern][["company_id", "company_name", "cfo_sign", "cfi_sign", "cff_sign"]]
st.dataframe(pattern_companies, hide_index=True, use_container_width=True)