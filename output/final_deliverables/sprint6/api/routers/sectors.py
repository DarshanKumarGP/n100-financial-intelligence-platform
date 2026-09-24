"""
N100 Financial Intelligence Platform
Sprint 6, Day 40: Sector Endpoints

Location: src/api/routers/sectors.py

Spec says "return all 11 sectors" -- confirmed 2026-09 via direct query,
same as multiple prior sprints: sectors.xlsx / the sectors table
genuinely has only 10 distinct broad_sector values, not 11. This
endpoint returns the real 10, with a note field disclosing the count
mismatch -- same "verify against reality, document the deviation"
approach as everywhere else in this project (Sprints 1-5, Day 37/38).

2026-09 fix (Sprint 6, Day 44 ruff/QA pass): list_sectors() computed a
`latest` dataframe (each company's latest-year row via
groupby("company_id").tail(1)) but then never used it -- the summary
aggregation ran against the full multi-year `fr` dataframe instead.
Two real consequences, both silent because test_sectors.py only checks
the top-level sector count, never company_count or the median values:
  1. median_roe / median_de were medians across EVERY historical year
     for every company in a sector, not the latest year -- contradicting
     this endpoint's own docstring and every other "latest year only"
     rule used elsewhere in this project (financial_ratios, screener,
     dashboard, tearsheets).
  2. company_count counted company-YEARS, not distinct companies (e.g.
     10 companies x 6 years each would report company_count: 60).
Fixed by aggregating over `latest` instead of `fr`. Also added an
explicit ORDER BY company_id, year to the source query, since
groupby().tail(1) silently depended on SQLite's unordered row return
order to identify "the latest year" -- correct only by accident.
"""

import pandas as pd
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get("/sectors")
def list_sectors(request: Request):
    """Return all sectors with company count and median ROE/P-E/D-E; discloses the real sector count where it differs from the spec."""
    conn = request.app.state.get_db_connection()
    try:
        fr = pd.read_sql(
            """
            SELECT company_id, year, return_on_equity_pct, debt_to_equity
            FROM financial_ratios WHERE year != 'TTM'
            ORDER BY company_id, year
        """,
            conn,
        )
        fr["return_on_equity_pct"] = pd.to_numeric(
            fr["return_on_equity_pct"], errors="coerce"
        )
        fr["debt_to_equity"] = pd.to_numeric(fr["debt_to_equity"], errors="coerce")
        latest = fr.groupby("company_id").tail(1)

        sectors = pd.read_sql("SELECT company_id, broad_sector FROM sectors;", conn)
        mc = pd.read_sql(
            """
            SELECT company_id, pe_ratio, year FROM market_cap
            WHERE (company_id, year) IN (
                SELECT company_id, MAX(year) FROM market_cap GROUP BY company_id
            )
        """,
            conn,
        )
    finally:
        conn.close()

    merged = sectors.merge(latest, on="company_id", how="left").merge(
        mc, on="company_id", how="left"
    )

    summary = (
        merged.groupby("broad_sector")
        .agg(
            company_count=("company_id", "count"),
            median_roe=("return_on_equity_pct", "median"),
            median_pe=("pe_ratio", "median"),
            median_de=("debt_to_equity", "median"),
        )
        .reset_index()
    )

    return {
        "count": len(summary),
        "note": (
            f"{len(summary)} sectors reported (spec text says 11; the "
            f"sectors table genuinely has only {len(summary)} distinct "
            f"broad_sector values -- confirmed repeatedly since Sprint 1)"
        ),
        "results": summary.to_dict(orient="records"),
    }


@router.get("/sectors/{sector}/companies")
def get_sector_companies(sector: str, request: Request):
    """Return all companies in a sector with their latest-year KPIs; 404 if the sector is unknown."""
    conn = request.app.state.get_db_connection()
    try:
        exists = conn.execute(
            "SELECT 1 FROM sectors WHERE broad_sector = ? LIMIT 1", (sector,)
        ).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail=f"Sector '{sector}' not found")

        rows = conn.execute(
            """
            SELECT c.id, c.company_name, s.sub_sector,
                   c.roe_percentage AS roe_pct, c.roce_percentage AS roce_pct
            FROM companies c
            JOIN sectors s ON c.id = s.company_id
            WHERE s.broad_sector = ?
            ORDER BY c.id
        """,
            (sector,),
        ).fetchall()
    finally:
        conn.close()

    return {"sector": sector, "count": len(rows), "results": [dict(r) for r in rows]}