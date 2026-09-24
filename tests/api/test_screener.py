"""
N100 Financial Intelligence Platform
Sprint 6, Day 42: Screener Endpoint API Tests

Location: tests/api/test_screener.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_min_roe_filter_returns_only_companies_above_threshold():
    response = client.get("/api/v1/screener", params={"min_roe": 15})
    assert response.status_code == 200

    data = response.json()
    assert data["count"] > 0
    for company in data["results"]:
        roe = company.get("return_on_equity_pct")
        if roe is not None:
            assert roe >= 15


def test_invalid_parameter_value_returns_400():
    """
    FastAPI's default response to a malformed query param is HTTP 422;
    confirmed 2026-09 (Day 40) main.py's RequestValidationError handler
    converts this to 400 to match the spec's explicit wording.
    """
    response = client.get("/api/v1/screener", params={"min_roe": "notanumber"})
    assert response.status_code == 400


def test_invalid_sector_returns_400():
    response = client.get("/api/v1/screener", params={"sector": "NotARealSector"})
    assert response.status_code == 400
    assert "invalid sector" in response.json()["detail"].lower()
