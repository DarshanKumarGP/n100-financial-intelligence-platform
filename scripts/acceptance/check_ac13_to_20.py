"""
N100 Financial Intelligence Platform
Sprint 6, Day 45: Acceptance Gates AC-13 to AC-20

Location: scripts/acceptance/check_ac13_to_20.py

AC-13 compares against the Quality Compounder preset specifically,
since its filters (roe_min=15, de_max=1.0, fcf_min=0.01,
revenue_cagr_min=10) are the only preset whose filters map cleanly
onto the 6 query params the /screener API endpoint actually exposes
(a scope gap documented since Day 42). This is a genuine independent
check: the Excel file comes from export_screener_output.py/presets.py,
the API result comes from a live HTTP call.

AC-18 shells out to pytest itself and parses its own output rather
than hardcoding an expected count, so this gate reflects the real
suite state at the moment it's run.

Requires uvicorn running on port 8000 for AC-13.

Usage:
    uvicorn src.api.main:app --port 8000   (separate terminal)
    python scripts/acceptance/check_ac13_to_20.py
"""

import re
import sqlite3
import subprocess
import sys

import pandas as pd
import requests
from pypdf import PdfReader

DB_PATH = "data/nifty100.db"
SCREENER_OUTPUT_PATH = "output/screener_output.xlsx"
CLUSTER_LABELS_PATH = "output/cluster_labels.csv"
PROS_CONS_PATH = "output/pros_cons_generated.csv"
VALIDATION_FAILURES_PATH = "output/validation_failures.csv"
ANALYST_GUIDE_PATH = "docs/analyst_guide.pdf"
TEARSHEETS_DIR = "reports/tearsheets"
API_BASE = "http://127.0.0.1:8000/api/v1"


def gate(label, passed, evidence):
    status = "PASS" if passed else "FAIL"
    print(f"\n[{status}] {label}")
    for line in evidence:
        print(f"    {line}")
    return passed


def main():
    import os

    results = {}

    # --- AC-13: API screener results match screener_output.xlsx (Quality Compounder) ---
    try:
        xl = pd.ExcelFile(SCREENER_OUTPUT_PATH)
        match = [s for s in xl.sheet_names if "quality" in s.lower()]
        excel_ids = set()
        if match:
            df = xl.parse(match[0])
            id_col = [c for c in df.columns if c.lower() in ("company_id", "id")]
            if id_col:
                excel_ids = set(df[id_col[0]].tolist())

        resp = requests.get(
            f"{API_BASE}/screener",
            params={"min_roe": 15, "max_de": 1.0, "min_fcf": 0.01, "min_rev_cagr_5yr": 10},
            timeout=10,
        )
        api_ids = set()
        if resp.status_code == 200:
            body = resp.json()
            api_ids = {r["company_id"] for r in body.get("results", [])}

        match_ok = excel_ids == api_ids and len(excel_ids) > 0
        results["AC-13"] = gate(
            "AC-13: API screener results match screener_output.xlsx (Quality Compounder)",
            match_ok,
            [
                f"Excel sheet '{match[0] if match else '???'}': {len(excel_ids)} companies",
                f"API (equivalent filters): {len(api_ids)} companies",
                f"Excel-only: {sorted(excel_ids - api_ids)}",
                f"API-only: {sorted(api_ids - excel_ids)}",
            ],
        )
    except Exception as e:
        results["AC-13"] = gate(
            "AC-13: API screener results match screener_output.xlsx (Quality Compounder)",
            False,
            [f"Error: {e} -- is uvicorn running on port 8000?"],
        )

    # --- AC-14: peer_percentiles table has data for all 11 peer groups ---
    try:
        conn = sqlite3.connect(DB_PATH)
        groups = conn.execute(
            "SELECT DISTINCT peer_group FROM peer_percentiles"
        ).fetchall()
        conn.close()
        group_count = len(groups)
        results["AC-14"] = gate(
            "AC-14: peer_percentiles has data for all 11 peer groups",
            group_count == 11,
            [f"Distinct peer_group values in peer_percentiles: {group_count}", f"Groups: {sorted(g[0] for g in groups)}"],
        )
    except Exception as e:
        results["AC-14"] = gate(
            "AC-14: peer_percentiles has data for all 11 peer groups", False, [f"Error: {e}"]
        )

    # --- AC-15: All 92 companies have a cluster_id assigned ---
    try:
        df = pd.read_csv(CLUSTER_LABELS_PATH)
        total = len(df)
        assigned = df["cluster_id"].notna().sum()
        results["AC-15"] = gate(
            "AC-15: All 92 companies have a cluster_id assigned",
            total == 92 and assigned == 92,
            [f"cluster_labels.csv: {total} rows, {assigned} with non-null cluster_id"],
        )
    except Exception as e:
        results["AC-15"] = gate(
            "AC-15: All 92 companies have a cluster_id assigned", False, [f"Error: {e}"]
        )

    # --- AC-16: All 92 companies have at least 1 pro and 1 con ---
    try:
        df = pd.read_csv(PROS_CONS_PATH)
        conn = sqlite3.connect(DB_PATH)
        all_companies = {r[0] for r in conn.execute("SELECT id FROM companies").fetchall()}
        conn.close()

        pros_by_company = set(df[df["type"] == "pro"]["company_id"])
        cons_by_company = set(df[df["type"] == "con"]["company_id"])

        missing_pro = all_companies - pros_by_company
        missing_con = all_companies - cons_by_company

        results["AC-16"] = gate(
            "AC-16: All 92 companies have at least 1 pro and 1 con",
            len(missing_pro) == 0 and len(missing_con) == 0,
            [
                f"Companies missing a pro: {len(missing_pro)} {sorted(missing_pro) if missing_pro else ''}",
                f"Companies missing a con: {len(missing_con)} {sorted(missing_con) if missing_con else ''}",
            ],
        )
    except Exception as e:
        results["AC-16"] = gate(
            "AC-16: All 92 companies have at least 1 pro and 1 con", False, [f"Error: {e}"]
        )

    # --- AC-17: 92 tearsheet PDFs exist, each >= 30 KB ---
    try:
        files = [f for f in os.listdir(TEARSHEETS_DIR) if f.endswith(".pdf")]
        undersized = []
        for f in files:
            size_kb = os.path.getsize(os.path.join(TEARSHEETS_DIR, f)) / 1024
            if size_kb < 30:
                undersized.append((f, round(size_kb, 1)))

        results["AC-17"] = gate(
            "AC-17: 92 tearsheet PDFs exist, each >=30 KB",
            len(files) == 92 and len(undersized) == 0,
            [
                f"Files found: {len(files)} (expected 92)",
                f"Undersized (<30KB): {undersized}",
                "Known: JIOFIN is intentionally skipped (2 years of history, "
                "below the 3-year minimum) -- 91 of 92 is expected, documented "
                "behavior, not a bug." if len(files) == 91 else "",
            ],
        )
    except Exception as e:
        results["AC-17"] = gate(
            "AC-17: 92 tearsheet PDFs exist, each >=30 KB", False, [f"Error: {e}"]
        )

    # --- AC-18: pytest shows 60+ tests collected, 0 failures ---
    try:
        proc = subprocess.run(
            ["pytest", "tests/", "-q"], capture_output=True, text=True, timeout=120
        )
        output = proc.stdout + proc.stderr
        m = re.search(r"(\d+) passed", output)
        f = re.search(r"(\d+) failed", output)
        passed = int(m.group(1)) if m else 0
        failed = int(f.group(1)) if f else 0
        results["AC-18"] = gate(
            "AC-18: pytest shows 60+ tests collected, 0 failures",
            passed >= 60 and failed == 0,
            [f"{passed} passed, {failed} failed"],
        )
    except Exception as e:
        results["AC-18"] = gate(
            "AC-18: pytest shows 60+ tests collected, 0 failures", False, [f"Error: {e}"]
        )

    # --- AC-19: validation_failures.csv exists with required columns ---
    try:
        df = pd.read_csv(VALIDATION_FAILURES_PATH)
        required_cols = {"company_id", "field", "issue", "severity"}
        actual_cols = set(df.columns)
        has_all = required_cols.issubset(actual_cols)
        results["AC-19"] = gate(
            "AC-19: validation_failures.csv exists with required columns",
            has_all,
            [f"Columns present: {sorted(actual_cols)}", f"Required: {sorted(required_cols)}", f"Rows: {len(df)}"],
        )
    except Exception as e:
        results["AC-19"] = gate(
            "AC-19: validation_failures.csv exists with required columns", False, [f"Error: {e}"]
        )

    # --- AC-20: analyst_guide.pdf is at least 10 pages ---
    try:
        reader = PdfReader(ANALYST_GUIDE_PATH)
        page_count = len(reader.pages)
        results["AC-20"] = gate(
            "AC-20: analyst_guide.pdf is at least 10 pages",
            page_count >= 10,
            [f"Page count: {page_count}"],
        )
    except Exception as e:
        results["AC-20"] = gate(
            "AC-20: analyst_guide.pdf is at least 10 pages", False, [f"Error: {e}"]
        )

    print("\n" + "=" * 60)
    print("SUMMARY (AC-13 to AC-20)")
    print("=" * 60)
    for gate_id, passed in results.items():
        print(f"  {gate_id}: {'PASS' if passed else 'FAIL'}")


if __name__ == "__main__":
    main()