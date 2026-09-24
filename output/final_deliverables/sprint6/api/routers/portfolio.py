"""
N100 Financial Intelligence Platform
Sprint 6, Day 40: Portfolio Stats Endpoint

Location: src/api/routers/portfolio.py

Reads output/portfolio_stats.csv (Day 37) rather than recomputing --
same "reuse what's already verified" approach used throughout this
project (e.g. cashflow_intelligence.py reading capital_allocation.csv
in Sprint 5 instead of re-deriving it).
"""

import os

import pandas as pd
from fastapi import APIRouter, HTTPException

router = APIRouter()

PORTFOLIO_STATS_PATH = "output/portfolio_stats.csv"


@router.get("/portfolio/stats")
def get_portfolio_stats():
    """Return the pre-computed P10-P90 percentile table for core KPIs across all companies."""
    if not os.path.exists(PORTFOLIO_STATS_PATH):
        raise HTTPException(
            status_code=404,
            detail="portfolio_stats.csv not found -- run src/analytics/cluster_profiling.py first",
        )
    df = pd.read_csv(PORTFOLIO_STATS_PATH)
    return {"count": len(df), "results": df.to_dict(orient="records")}
