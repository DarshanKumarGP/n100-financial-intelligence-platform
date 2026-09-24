"""
N100 Financial Intelligence Platform
Sprint 6, Day 40: Screener Endpoint

Location: src/api/routers/screener.py

Wraps src/screener/engine.py's run_screener() (Sprint 3) rather than
reimplementing filter logic -- same "reuse proven logic" approach used
for cashflow_kpis.py in Sprint 5. build_latest_snapshot() already joins
broad_sector directly, so sector filtering happens as a plain pandas
filter after run_screener() returns, not as an engine.py filter_key
(engine.py's filters dict is built around financial_ratios/market_cap/
profitandloss metric thresholds, not sector membership).

Query params map to engine.py's filters dict keys as:
  min_roe -> roe_min, max_de -> de_max, min_fcf -> fcf_min,
  min_rev_cagr_5yr -> revenue_cagr_5yr_min,
  min_pat_cagr_5yr -> pat_cagr_5yr_min, max_pe -> pe_max
sector is applied separately (not an engine.py filter key).

Type validation (negative thresholds where they don't make sense,
malformed values) is handled by FastAPI's Query() constraints, which
return HTTP 422 by default -- spec wants 400 specifically, so a
validation wrapper converts 422 -> 400 to match the literal spec ask.
"""

import os
import sys

from fastapi import APIRouter, HTTPException, Query, Request

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "screener")
)
from engine import run_screener

router = APIRouter()


@router.get("/screener")
def screener(
    request: Request,
    min_roe: float | None = Query(None),
    max_de: float | None = Query(None),
    min_fcf: float | None = Query(None),
    sector: str | None = Query(None),
    min_rev_cagr_5yr: float | None = Query(None),
    min_pat_cagr_5yr: float | None = Query(None),
    max_pe: float | None = Query(None),
):
    """Filter and rank companies by the given query parameters, wrapping engine.py's run_screener(); returns HTTP 400 for invalid parameter values."""
    filters = {}
    if min_roe is not None:
        filters["roe_min"] = min_roe
    if max_de is not None:
        filters["de_max"] = max_de
    if min_fcf is not None:
        filters["fcf_min"] = min_fcf
    if min_rev_cagr_5yr is not None:
        filters["revenue_cagr_5yr_min"] = min_rev_cagr_5yr
    if min_pat_cagr_5yr is not None:
        filters["pat_cagr_5yr_min"] = min_pat_cagr_5yr
    if max_pe is not None:
        filters["pe_max"] = max_pe

    if sector is not None:
        conn = request.app.state.get_db_connection()
        try:
            exists = conn.execute(
                "SELECT 1 FROM sectors WHERE broad_sector = ? LIMIT 1", (sector,)
            ).fetchone()
        finally:
            conn.close()
        if exists is None:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid sector '{sector}' -- not found in the sectors table",
            )

    try:
        results = run_screener(filters, apply_guard=True)
    except Exception as e:  # noqa: BLE001 -- intentional: any filter error becomes a 400, not a 500
        raise HTTPException(status_code=400, detail=f"Screener error: {e}")

    if sector is not None:
        results = results[results["broad_sector"] == sector]

    results = results.replace({float("nan"): None})
    cols = [
        "company_id",
        "broad_sector",
        "return_on_equity_pct",
        "debt_to_equity",
        "free_cash_flow_cr",
        "revenue_cagr_5yr",
        "pat_cagr_5yr",
        "pe_ratio",
        "composite_quality_score",
    ]
    cols = [c for c in cols if c in results.columns]

    return {
        "count": len(results),
        "filters_applied": {**filters, **({"sector": sector} if sector else {})},
        "results": results[cols].to_dict(orient="records"),
    }
