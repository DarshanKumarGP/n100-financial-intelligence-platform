"""
N100 Financial Intelligence Platform
Sprint 4, Day 22: Streamlit Dashboard — Main Entry Point
"""

import streamlit as st

st.set_page_config(
    page_title="Nifty 100 Analytics",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Nifty 100 Financial Intelligence Platform")
st.markdown("""
Use the sidebar to navigate between screens:
- **Home** — universe overview and summary KPIs
- **Company Profile** — deep-dive on any of the 92 companies
- **Screener** — filter companies by 10+ financial metrics
- **Peer Comparison** — benchmark a company against its peer group
- **Trend Analysis** — 10-year metric trends
- **Sector Analysis** — sector-level comparisons
- **Capital Allocation Map** — how companies deploy cash
- **Annual Reports** — links to source filings
""")

st.info("Select a screen from the sidebar (left) to get started.")