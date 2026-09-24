"""
N100 Financial Intelligence Platform
Sprint 6, Day 42: Sector Endpoints API Tests

Location: tests/api/test_sectors.py

Spec says "verify /sectors returns exactly 11 sectors" -- confirmed
repeatedly since Sprint 1 (and reconfirmed 2026-09 in the API layer
itself, Day 40) that the sectors table genuinely has only 10 distinct
broad_sector values, not 11. This test checks the real, correct count
(10) rather than asserting 11, which would fail against our own
already-verified-correct behavior. The endpoint's own response also
carries a "note" field disclosing this exact discrepancy.

2026-09 addition (Day 44 QA pass): test_company_count_matches_distinct_companies_per_sector
guards against a real bug found during ruff cleanup -- list_sectors()
was aggregating over the full multi-year financial_ratios dataframe
instead of a latest-year-only one, so company_count was counting
company-YEARS, not distinct companies. Fixed in sectors.py; this test
checks company_count against an independent COUNT(DISTINCT company_id)
query so a similar regression can't slip past silently again.
"""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)

DB_PATH = "data/nifty100.db"


def test_list_sectors_returns_10_real_sectors():
    response = client.get("/api/v1/sectors")
    assert response.status_code == 200

    data = response.json()
    assert data["count"] == 10
    assert "note" in data  # discloses the 10-vs-spec's-11 discrepancy


def test_company_count_matches_distinct_companies_per_sector():
    response = client.get("/api/v1/sectors")
    assert response.status_code == 200
    results = {row["broad_sector"]: row["company_count"] for row in response.json()["results"]}

    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT broad_sector, COUNT(DISTINCT company_id) FROM sectors GROUP BY broad_sector"
        ).fetchall()
    finally:
        conn.close()

    for sector, expected_count in rows:
        assert results[sector] == expected_count, (
            f"{sector}: API reported company_count={results[sector]}, "
            f"but {expected_count} distinct companies actually exist in that sector "
            f"(a company_count that counts company-YEARS instead of companies was a "
            f"real bug found and fixed 2026-09 -- this guards against it recurring)"
        )


def test_sector_companies_returns_only_it_sector():
    response = client.get("/api/v1/sectors/Information Technology/companies")
    assert response.status_code == 200

    data = response.json()
    assert data["count"] > 0
    ids = [c["id"] for c in data["results"]]
    assert "TCS" in ids


def test_unknown_sector_returns_404():
    response = client.get("/api/v1/sectors/NotReal/companies")
    assert response.status_code == 404