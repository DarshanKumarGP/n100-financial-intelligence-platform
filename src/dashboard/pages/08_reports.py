"""
N100 Financial Intelligence Platform
Sprint 4, Day 25: Annual Reports Screen
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "utils"))

import streamlit as st
from db import get_companies, get_documents

st.title("Annual Reports")

companies_df = get_companies()
search_options = [f"{row['id']} — {row['company_name']}" for _, row in companies_df.iterrows()]
selected = st.selectbox("Search company", options=[""] + search_options)

if not selected:
    st.info("Select a company to see its annual report links.")
    st.stop()

ticker = selected.split(" — ")[0]
docs = get_documents(ticker)

if docs.empty:
    st.warning("No annual report records found for this company.")
    st.stop()

st.write(f"**{len(docs)} annual report(s) on file:**")

for _, row in docs.iterrows():
    year = row["report_year"]
    url = row["annual_report"]
    if url and isinstance(url, str) and url.startswith("http"):
        st.markdown(f"📄 [{year} Annual Report]({url})")
    else:
        st.markdown(f"📄 {year} — <span style='color:red'>Report unavailable</span>", unsafe_allow_html=True)