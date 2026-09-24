"""
N100 Financial Intelligence Platform
Sprint 6, Day 43: Screener API Load Test

Location: scripts/perf/load_test_screener.py

Fires 10 concurrent requests at the live /api/v1/screener endpoint
using a ThreadPoolExecutor (real HTTP calls over the network stack,
not FastAPI's in-process TestClient).

Confirmed 2026-09:
- The real broad_sector value for the IT sector is "Information
  Technology", not "IT" -- the first run's 400 on sector=IT was a
  bad test parameter, not an API bug.
- /api/v1/screener returns {"count": int, "filters_applied": {...},
  "results": [...]}, not a bare array -- the first run's row_count
  used len(resp.json()), which counted the 3 top-level dict keys
  every time instead of actual result rows. Fixed to read
  response["count"] directly.

Requires the API server already running separately:
    uvicorn src.api.main:app --port 8000

Usage:
    python scripts/perf/load_test_screener.py
"""

import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "http://127.0.0.1:8000/api/v1/screener"

REQUESTS = [
    {"min_roe": 15},
    {"max_de": 1.0},
    {"min_roe": 10, "max_de": 2.0},
    {"sector": "Information Technology"},
    {"min_rev_cagr_5yr": 10},
    {"min_pat_cagr_5yr": 15},
    {"max_pe": 30},
    {"min_roe": 20, "min_fcf": 0},
    {"sector": "Financials", "max_de": 5.0},
    {"min_roe": 5},
]


def fire_one(params):
    start = time.perf_counter()
    resp = requests.get(BASE_URL, params=params, timeout=15)
    elapsed = time.perf_counter() - start
    row_count = None
    if resp.status_code == 200:
        body = resp.json()
        row_count = body.get("count", len(body.get("results", [])))
    return {
        "params": params,
        "status": resp.status_code,
        "elapsed_sec": round(elapsed, 3),
        "row_count": row_count,
    }


def main():
    print(f"Firing {len(REQUESTS)} concurrent requests to {BASE_URL} ...")
    overall_start = time.perf_counter()

    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fire_one, p) for p in REQUESTS]
        for f in as_completed(futures):
            results.append(f.result())

    overall_elapsed = time.perf_counter() - overall_start

    results.sort(key=lambda r: r["elapsed_sec"])
    print("\nPer-request results:")
    for r in results:
        print(f"  {r['elapsed_sec']:>6.3f}s  status={r['status']}  rows={r['row_count']}  params={r['params']}")

    print(f"\nTotal wall time for all 10 concurrent requests: {overall_elapsed:.3f}s")
    print(f"Target: under 10.0s -- {'PASS' if overall_elapsed < 10.0 else 'FAIL'}")

    failures = [r for r in results if r["status"] != 200]
    if failures:
        print(f"\nWARNING: {len(failures)} request(s) did not return HTTP 200:")
        for r in failures:
            print(f"  {r}")


if __name__ == "__main__":
    main()