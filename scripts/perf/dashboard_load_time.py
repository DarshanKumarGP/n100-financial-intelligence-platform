"""
N100 Financial Intelligence Platform
Sprint 6, Day 43: Company Profile Dashboard Load Time

Location: scripts/perf/dashboard_load_time.py

Times the exact data-loading functions src/dashboard/pages/02_profile.py
calls for a Company Profile view: get_companies() (once, shared across
all tickers -- powers the search selectbox) plus get_ratios(),
get_ratios_history(), get_pl(), get_pros_cons() (per ticker).

These are called directly, COLD -- i.e. without Streamlit's
@st.cache_data actually being warm, since that requires a live
Streamlit script-run context that a standalone script doesn't have.
This measures the realistic worst case: a user's FIRST view of a given
ticker. Repeat views in the real app benefit from the 600s TTL cache
and would be near-instant -- that's a separate, better number, not
what's being measured here.

Does NOT measure actual Streamlit rendering/chart-draw time (plotly
figure construction, DOM paint) -- only the data-fetch layer, which is
where virtually all real latency lives for this app (SQLite reads are
the bottleneck, not drawing a few KPI tiles and charts).

Usage:
    python scripts/perf/dashboard_load_time.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src", "dashboard", "utils"))

from db import get_companies, get_ratios, get_ratios_history, get_pl, get_pros_cons

TICKERS = ["TCS", "HDFCBANK", "RELIANCE", "SUNPHARMA", "TATASTEEL"]

TARGET_SECONDS = 3.0


def time_call(label, fn, *args):
    start = time.perf_counter()
    try:
        result = fn(*args)
        ok = True
        note = ""
    except Exception as e:
        result = None
        ok = False
        note = f"{type(e).__name__}: {e}"
    elapsed = time.perf_counter() - start
    return {"label": label, "elapsed": elapsed, "ok": ok, "note": note, "result": result}


def main():
    print("=== Shared baseline: get_companies() ===")
    baseline = time_call("get_companies()", get_companies)
    print(f"  {baseline['elapsed']:.3f}s  ok={baseline['ok']}  {baseline['note']}")
    if not baseline["ok"]:
        print("get_companies() failed -- cannot proceed.")
        return

    print(f"\n=== Per-ticker Company Profile load ({len(TICKERS)} tickers) ===")
    per_ticker_totals = []

    for ticker in TICKERS:
        calls = [
            time_call("get_ratios", get_ratios, ticker),
            time_call("get_ratios_history", get_ratios_history, ticker),
            time_call("get_pl", get_pl, ticker),
            time_call("get_pros_cons", get_pros_cons, ticker),
        ]
        total = sum(c["elapsed"] for c in calls)
        per_ticker_totals.append((ticker, total))

        print(f"\n{ticker}: total data-fetch time = {total:.3f}s -- {'PASS' if total < TARGET_SECONDS else 'FAIL'} (target < {TARGET_SECONDS}s)")
        for c in calls:
            flag = "" if c["ok"] else f"  *** FAILED: {c['note']}"
            print(f"    {c['label']:<20} {c['elapsed']:.3f}s{flag}")

    print("\n=== Summary ===")
    for ticker, total in per_ticker_totals:
        status = "PASS" if total < TARGET_SECONDS else "FAIL"
        print(f"  {ticker:<12} {total:.3f}s  {status}")

    all_pass = all(t < TARGET_SECONDS for _, t in per_ticker_totals)
    print(f"\nOverall: {'ALL PASS' if all_pass else 'AT LEAST ONE FAIL'}")


if __name__ == "__main__":
    main()