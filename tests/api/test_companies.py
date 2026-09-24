"""
N100 Financial Intelligence Platform
Sprint 6, Day 42: Company Endpoints API Tests

Location: tests/api/test_companies.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_list_companies_returns_92_records():
    response = client.get("/api/v1/companies")
    assert response.status_code == 200

    data = response.json()
    assert data["count"] == 92
    assert len(data["results"]) == 92


def test_get_tcs_returns_correct_data():
    response = client.get("/api/v1/companies/TCS")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == "TCS"
    assert data["company_name"] == "Tata Consultancy Services Ltd"
    assert data["sector"]["broad_sector"] == "Information Technology"
    assert data["latest_year_kpis"] is not None


def test_get_invalid_ticker_returns_404():
    response = client.get("/api/v1/companies/INVALID")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_search_by_partial_name_returns_tcs():
    response = client.get("/api/v1/companies", params={"search": "TCS"})
    assert response.status_code == 200

    data = response.json()
    assert data["count"] == 1
    assert data["results"][0]["id"] == "TCS"


def test_filter_by_sector_returns_only_that_sector():
    response = client.get(
        "/api/v1/companies", params={"sector": "Information Technology"}
    )
    assert response.status_code == 200

    data = response.json()
    assert data["count"] > 0
    for company in data["results"]:
        assert company["broad_sector"] == "Information Technology"
