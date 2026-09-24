"""
N100 Financial Intelligence Platform
Sprint 6, Day 39: Company Data Endpoints

Location: src/api/routers/companies.py

Real schemas confirmed 2026-09:
  companies: id, company_logo, company_name, chart_link, about_company,
    website, nse_profile, bse_profile, face_value, book_value,
    roce_percentage, roe_percentage
  sectors: company_id, broad_sector, sub_sector, index_weight_pct,
    market_cap_category

roe_pct/roce_pct on GET /companies use companies.roe_percentage /
companies.roce_percentage directly (the source-scraped fields), NOT
financial_ratios' computed values -- matches Day 45's acceptance gate
AC-06 ("ROE matches companies.roe_percentage within 5%"), which treats
companies.roe_percentage as the reference value. GET /companies/{ticker}
additionally includes our own computed latest-year KPIs from
financial_ratios, per spec: "all companies fields + latest year KPIs".

TTM rows excluded by default from /pl, /bs, /cashflow, /ratios history
arrays (not real fiscal years) -- same convention used throughout this
project. /ratios allows an explicit year=TTM request.

Numeric financial_ratios columns coerced with pd.to_numeric() before
use -- this project has hit SQLite dtype inconsistency twice already
(cfo_pat_ratio_5yr, fcf_cagr_5yr), applied defensively here too.

KNOWN DATA QUALITY ISSUE (confirmed 2026-09, NOT fixed here -- documented,
not silently normalized, same policy as the CIPLA operating_profit
question sitting open since Sprint 1/2):
  companies.roe_percentage for TCS = 0.52, while companies.roce_percentage
  for the same row = 64.3 (a plausible value). Every other spot-checked
  company (ABB, HDFCBANK, INFY, RELIANCE) has a normal-looking
  roe_percentage. 0.52 * 100 = 52%, within ~1pp of financial_ratios'
  independently-computed ROE for TCS (50.9%, verified repeatedly across
  Sprint 5 and this sprint) -- strongly suggests this one row was stored
  as a decimal fraction instead of a percentage. This endpoint reflects
  companies.roe_percentage exactly as stored (its job is to faithfully
  expose the source table), so GET /companies and GET /companies/TCS
  will both surface this bad value as-is. Flagged explicitly here and
  in the Sprint 6 retro so Day 45's AC-06 gate ("ROE matches
  companies.roe_percentage within 5%") doesn't fail confusingly on TCS
  without an explanation on hand.
"""

import os
import sqlite3

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse

router = APIRouter()

TEARSHEET_DIR = "reports/tearsheets"


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def _company_exists(conn, ticker: str) -> bool:
    row = conn.execute("SELECT 1 FROM companies WHERE id = ?", (ticker,)).fetchone()
    return row is not None


def _clean_numeric(df: pd.DataFrame, cols) -> pd.DataFrame:
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


@router.get("/companies")
def list_companies(
    request: Request,
    sector: str | None = Query(None, description="Filter by broad_sector"),
    market_cap_category: str | None = Query(None),
    search: str | None = Query(
        None, description="Partial match on company name or ticker"
    ),
):
    """List all companies, optionally filtered by sector, market cap category, or a partial name/ticker search."""
    conn = request.app.state.get_db_connection()
    try:
        query = """
            SELECT c.id, c.company_name, s.broad_sector, s.sub_sector,
                   c.roe_percentage AS roe_pct, c.roce_percentage AS roce_pct,
                   s.market_cap_category
            FROM companies c
            LEFT JOIN sectors s ON c.id = s.company_id
            WHERE 1=1
        """
        params = []

        if sector:
            query += " AND s.broad_sector = ?"
            params.append(sector)
        if market_cap_category:
            query += " AND s.market_cap_category = ?"
            params.append(market_cap_category)
        if search:
            query += " AND (c.company_name LIKE ? OR c.id LIKE ?)"
            like = f"%{search}%"
            params.extend([like, like])

        query += " ORDER BY c.id"
        rows = conn.execute(query, params).fetchall()
        return {"count": len(rows), "results": [_row_to_dict(r) for r in rows]}
    finally:
        conn.close()


@router.get("/companies/{ticker}")
def get_company_detail(ticker: str, request: Request):
    """Return a single company's full profile, including latest-year computed KPIs and sector data; 404 if the ticker is not found."""
    conn = request.app.state.get_db_connection()
    try:
        company = conn.execute(
            "SELECT * FROM companies WHERE id = ?", (ticker,)
        ).fetchone()
        if company is None:
            raise HTTPException(status_code=404, detail=f"Company '{ticker}' not found")

        sector = conn.execute(
            "SELECT broad_sector, sub_sector, index_weight_pct, market_cap_category "
            "FROM sectors WHERE company_id = ?",
            (ticker,),
        ).fetchone()

        latest_ratios = conn.execute(
            "SELECT * FROM financial_ratios WHERE company_id = ? AND year != 'TTM' "
            "ORDER BY year DESC LIMIT 1",
            (ticker,),
        ).fetchone()

        result = _row_to_dict(company)
        result["sector"] = _row_to_dict(sector) if sector else None
        result["latest_year_kpis"] = (
            _row_to_dict(latest_ratios) if latest_ratios else None
        )
        return result
    finally:
        conn.close()


def _history_endpoint(
    request: Request,
    ticker: str,
    table: str,
    from_year: str | None,
    to_year: str | None,
):
    conn = request.app.state.get_db_connection()
    try:
        if not _company_exists(conn, ticker):
            raise HTTPException(status_code=404, detail=f"Company '{ticker}' not found")

        query = f"SELECT * FROM {table} WHERE company_id = ? AND year != 'TTM'"
        params = [ticker]
        if from_year:
            query += " AND year >= ?"
            params.append(from_year)
        if to_year:
            query += " AND year <= ?"
            params.append(to_year)
        query += " ORDER BY year"

        rows = conn.execute(query, params).fetchall()
        return {
            "company_id": ticker,
            "count": len(rows),
            "results": [_row_to_dict(r) for r in rows],
        }
    finally:
        conn.close()


@router.get("/companies/{ticker}/pl")
def get_profit_and_loss(
    ticker: str,
    request: Request,
    from_year: str | None = Query(None, description="YYYY-MM"),
    to_year: str | None = Query(None, description="YYYY-MM"),
):
    """Return a company's P&L history, optionally filtered to a from_year/to_year range."""
    return _history_endpoint(request, ticker, "profitandloss", from_year, to_year)


@router.get("/companies/{ticker}/bs")
def get_balance_sheet(
    ticker: str,
    request: Request,
    from_year: str | None = Query(None, description="YYYY-MM"),
    to_year: str | None = Query(None, description="YYYY-MM"),
):
    """Return a company's balance sheet history, optionally filtered to a from_year/to_year range."""
    return _history_endpoint(request, ticker, "balancesheet", from_year, to_year)


@router.get("/companies/{ticker}/cashflow")
def get_cashflow(
    ticker: str,
    request: Request,
    from_year: str | None = Query(None, description="YYYY-MM"),
    to_year: str | None = Query(None, description="YYYY-MM"),
):
    """Return a company's cash flow history, optionally filtered to a from_year/to_year range."""
    return _history_endpoint(request, ticker, "cashflow", from_year, to_year)


@router.get("/companies/{ticker}/ratios")
def get_ratios(
    ticker: str,
    request: Request,
    year: str | None = Query(None, description="Single year e.g. '2024-03', or 'TTM'"),
):
    """Return a company's computed KPIs for every year, or a single year if the year query param is given."""
    conn = request.app.state.get_db_connection()
    try:
        if not _company_exists(conn, ticker):
            raise HTTPException(status_code=404, detail=f"Company '{ticker}' not found")

        if year:
            rows = conn.execute(
                "SELECT * FROM financial_ratios WHERE company_id = ? AND year = ?",
                (ticker, year),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM financial_ratios WHERE company_id = ? AND year != 'TTM' "
                "ORDER BY year",
                (ticker,),
            ).fetchall()

        return {
            "company_id": ticker,
            "count": len(rows),
            "results": [_row_to_dict(r) for r in rows],
        }
    finally:
        conn.close()


@router.get("/companies/{ticker}/tearsheet")
def get_tearsheet(ticker: str, request: Request):
    """Return the pre-generated tearsheet PDF for a company as a binary download; 404 if the ticker doesn't exist or has no generated tearsheet."""
    conn = request.app.state.get_db_connection()
    try:
        if not _company_exists(conn, ticker):
            raise HTTPException(status_code=404, detail=f"Company '{ticker}' not found")
    finally:
        conn.close()

    path = os.path.join(TEARSHEET_DIR, f"{ticker}_tearsheet.pdf")
    if not os.path.exists(path):
        # Known case: JIOFIN was skipped from batch generation (Sprint 5,
        # <3yr history) -- distinguished from an unknown-ticker 404 above.
        raise HTTPException(
            status_code=404,
            detail=f"Tearsheet not available for '{ticker}' (likely skipped due to insufficient history)",
        )

    return FileResponse(
        path, media_type="application/pdf", filename=f"{ticker}_tearsheet.pdf"
    )
