"""
N100 Financial Intelligence Platform
Sprint 4, Day 24: Screener Screen

Reuses src/screener/engine.py and presets.py directly -- all filter
logic, sector exemptions, and the outlier guard are already built and
tested in Sprint 3. This screen is UI wiring, not new analytics.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "screener"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "utils"))

import streamlit as st
import pandas as pd
from engine import build_latest_snapshot, apply_outlier_guard, load_config, apply_single_filter
import sqlite3

st.title("Screener")

DB_PATH = "data/nifty100.db"


@st.cache_data(ttl=600)
def get_snapshot():
    conn = sqlite3.connect(DB_PATH)
    config = load_config()
    snapshot = build_latest_snapshot(conn)
    conn.close()
    snapshot = apply_outlier_guard(snapshot, config)
    return snapshot, config


snapshot, config = get_snapshot()

# --- Preset buttons: pre-fill session_state BEFORE sliders are created ---
PRESET_DEFAULTS = {
    "Quality Compounder": {"roe_min": 15, "de_max": 1.0, "fcf_min": 0.01, "revenue_cagr_min": 10},
    "Value Pick": {"pe_max": 20, "pb_max": 3.0, "de_max": 2.0, "dividend_yield_min": 1},
    "Growth Accelerator": {"pat_cagr_min": 20, "revenue_cagr_min": 15, "de_max": 2.0},
    "Dividend Champion": {"dividend_yield_min": 2, "fcf_min": 0.01},
    "Debt-Free Blue Chip": {"de_max": 0.01, "roe_min": 12},
    "Turnaround Watch": {"revenue_cagr_min": 10, "fcf_min": 0.01},
}

SLIDER_BOUNDS = {
    "roe_min": (-50.0, 100.0, -50.0),
    "de_max": (0.0, 15.0, 15.0),
    "fcf_min": (-5000.0, 20000.0, -5000.0),
    "revenue_cagr_min": (-50.0, 100.0, -50.0),
    "pat_cagr_min": (-50.0, 100.0, -50.0),
    "opm_min": (-50.0, 100.0, -50.0),
    "pe_max": (0.0, 100.0, 100.0),
    "pb_max": (0.0, 20.0, 20.0),
    "dividend_yield_min": (0.0, 10.0, 0.0),
    "icr_min": (-5.0, 20.0, -5.0),
}

st.subheader("Quick Presets")
preset_cols = st.columns(6)
for i, (preset_name, values) in enumerate(PRESET_DEFAULTS.items()):
    if preset_cols[i].button(preset_name, use_container_width=True):
        for key, val in values.items():
            st.session_state[f"slider_{key}"] = float(val)
        st.rerun()

st.divider()

# --- 10 sliders in sidebar ---
st.sidebar.subheader("Filters")
filters = {}

label_map = {
    "roe_min": "ROE min (%)", "de_max": "D/E max", "fcf_min": "FCF min (Cr)",
    "revenue_cagr_min": "Revenue CAGR 5yr min (%)", "pat_cagr_min": "PAT CAGR 5yr min (%)",
    "opm_min": "OPM min (%)", "pe_max": "P/E max", "pb_max": "P/B max",
    "dividend_yield_min": "Dividend Yield min (%)", "icr_min": "ICR min",
}

for key, (lo, hi, default_off) in SLIDER_BOUNDS.items():
    value = st.sidebar.slider(
        label_map[key], min_value=lo, max_value=hi,
        value=st.session_state.get(f"slider_{key}", default_off),
        key=f"slider_{key}",
    )
    if value != default_off:
        filters[key] = value

if st.sidebar.button("Reset all filters"):
    for key in SLIDER_BOUNDS:
        st.session_state.pop(f"slider_{key}", None)
    st.rerun()

# --- Apply filters using engine.py's tested single-filter logic ---
result = snapshot.copy()
engine_metric_map = {
    "roe_min": "roe_min", "de_max": "de_max", "fcf_min": "fcf_min",
    "revenue_cagr_min": "revenue_cagr_5yr_min", "pat_cagr_min": "pat_cagr_5yr_min",
    "opm_min": "opm_min", "pe_max": "pe_max", "pb_max": "pb_max",
    "dividend_yield_min": "dividend_yield_min", "icr_min": "icr_min",
}
for ui_key, threshold in filters.items():
    engine_key = engine_metric_map[ui_key]
    result = apply_single_filter(result, engine_key, threshold, config)

result = result.sort_values("composite_quality_score", ascending=False, na_position="last")

st.subheader(f"{len(result)} companies match your filters")

display_cols = ["company_id", "company_name", "broad_sector", "composite_quality_score",
                 "return_on_equity_pct", "debt_to_equity", "free_cash_flow_cr",
                 "revenue_cagr_5yr", "pat_cagr_5yr", "pe_ratio", "pb_ratio", "dividend_yield_pct"]
display_cols = [c for c in display_cols if c in result.columns]

st.dataframe(result[display_cols], hide_index=True, use_container_width=True)

# --- CSV download ---
csv_data = result[display_cols].to_csv(index=False).encode("utf-8")
st.download_button(
    "Download results as CSV", data=csv_data,
    file_name="screener_results.csv", mime="text/csv",
)