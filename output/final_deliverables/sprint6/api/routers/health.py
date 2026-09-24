"""
N100 Financial Intelligence Platform
Sprint 6, Day 38: Health Router

Location: src/api/routers/health.py

GET /api/v1/health -- status, real row counts for all 14 tables
(spec says 10; database actually has 14 -- see main.py module docstring
for the full explanation), uptime, version.
"""

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Request

router = APIRouter()

# Confirmed 2026-09 via sqlite_master query -- the real table list.
# Spec says "all 10 tables"; there are actually 14. Reporting all of
# them rather than picking a subset to match the spec's literal count.
ALL_TABLES = [
    "companies",
    "profitandloss",
    "balancesheet",
    "cashflow",
    "analysis",
    "documents",
    "prosandcons",
    "sectors",
    "stock_prices",
    "market_cap",
    "financial_ratios_source",
    "peer_groups",
    "financial_ratios",
    "peer_percentiles",
]


@router.get("/health")
def get_health(request: Request):
    """Return service status, row counts for every table in the database, uptime, and the API version."""
    conn = request.app.state.get_db_connection()
    row_counts = {}
    try:
        for table in ALL_TABLES:
            cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
            row_counts[table] = cur.fetchone()[0]
    finally:
        conn.close()

    uptime_seconds = time.monotonic() - request.app.state.start_time

    return {
        "status": "ok",
        "db_row_counts": row_counts,
        "db_table_count_note": (
            f"{len(ALL_TABLES)} tables reported (spec text says 10; "
            f"database schema actually has {len(ALL_TABLES)})"
        ),
        "uptime_seconds": round(uptime_seconds, 1),
        "version": request.app.state.version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
