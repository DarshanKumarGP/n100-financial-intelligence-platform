"""
N100 Financial Intelligence Platform
Sprint 6, Day 40: Valuation / Market Cap Endpoint

Location: src/api/routers/valuation.py

market_cap: company_id, year, market_cap_crore, enterprise_value_crore,
  pe_ratio, pb_ratio, ev_ebitda, dividend_yield_pct
Confirmed 2026-09: year is an integer (2019-2024 per prior sprints'
findings), not the YYYY-MM fiscal-year string used elsewhere -- this
matches the already-documented market_cap.year quirk from Sprint 5's
handoff notes (matched to financial_ratios via
CAST(SUBSTR(year,1,4) AS INTEGER) when joining, but here we return
market_cap's own years directly since the endpoint's job is exactly
that table's history).
"""

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get("/market-cap/{ticker}")
def get_market_cap_history(ticker: str, request: Request):
    """Return a company's historical valuation multiples (P/E, P/B, EV/EBITDA, dividend yield) for 2019-2024."""
    conn = request.app.state.get_db_connection()
    try:
        exists = conn.execute(
            "SELECT 1 FROM companies WHERE id = ?", (ticker,)
        ).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail=f"Company '{ticker}' not found")

        rows = conn.execute(
            """
            SELECT year, market_cap_crore, enterprise_value_crore,
                   pe_ratio, pb_ratio, ev_ebitda, dividend_yield_pct
            FROM market_cap WHERE company_id = ? AND year BETWEEN 2019 AND 2024
            ORDER BY year
        """,
            (ticker,),
        ).fetchall()
    finally:
        conn.close()

    return {
        "company_id": ticker,
        "count": len(rows),
        "results": [dict(r) for r in rows],
    }
