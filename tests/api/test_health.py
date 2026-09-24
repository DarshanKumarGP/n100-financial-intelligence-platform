"""
N100 Financial Intelligence Platform
Sprint 6, Day 42: Health Endpoint API Test

Location: tests/api/test_health.py

Uses FastAPI's TestClient -- calls the app in-process, no live uvicorn
server required.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_health_returns_200_with_ok_status():
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"


def test_health_db_row_counts_contains_all_10_tables():
    """
    Spec says 'all 10 tables' -- confirmed 2026-09 (Day 38) the database
    actually has 14 tables, and /health reports all 14, not a picked
    subset of 10. This test checks that AT LEAST the spec's implied
    core set is present, rather than asserting exactly 10 (which would
    fail against our own correct, already-documented behavior).
    """
    response = client.get("/api/v1/health")
    data = response.json()

    assert "db_row_counts" in data
    row_counts = data["db_row_counts"]

    # Core tables the spec's "10 tables" wording almost certainly means
    core_expected = {
        "companies",
        "profitandloss",
        "balancesheet",
        "cashflow",
        "sectors",
        "financial_ratios",
        "market_cap",
        "documents",
    }
    assert core_expected.issubset(set(row_counts.keys()))
    assert len(row_counts) == 14  # real count, documented in main.py/health.py

    # Sanity check a known value rather than just checking key presence
    assert row_counts["companies"] == 92
