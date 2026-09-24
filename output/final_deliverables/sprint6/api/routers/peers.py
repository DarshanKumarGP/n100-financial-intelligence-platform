"""
N100 Financial Intelligence Platform
Sprint 6, Day 40: Peer Group Endpoints

Location: src/api/routers/peers.py

peer_groups: group_entry_id, peer_group_name, company_id, is_benchmark
peer_percentiles: company_id, peer_group_name, metric, value,
  percentile_rank, year
Confirmed 2026-09: 11 real peer groups (matches spec), 10 metrics per
company per group (matches spec's "10 metrics" for peer percentiles).

/companies/{ticker}/peers/compare returns 8 of those 10 metrics as
"radar data" per spec wording ("8 axis metric values") -- the 2
excluded here (free_cash_flow_cr, since it's an absolute Rs-crore
figure rather than a normalized ratio, and interest_coverage, which is
undefined/infinite for debt-free companies and doesn't plot cleanly on
a radar axis) are still available via /peers/{group_name} directly.
Flagged as a chosen subset, not silently picked.
"""

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()

RADAR_METRICS = [
    "return_on_equity_pct",
    "return_on_capital_employed_pct",
    "net_profit_margin_pct",
    "debt_to_equity",
    "revenue_cagr_5yr",
    "pat_cagr_5yr",
    "eps_cagr_5yr",
    "asset_turnover",
]


@router.get("/peers/{group_name}")
def get_peer_group(group_name: str, request: Request):
    """Return all companies in a peer group with their percentile rank for each tracked metric; 404 if the group is unknown."""
    conn = request.app.state.get_db_connection()
    try:
        exists = conn.execute(
            "SELECT 1 FROM peer_groups WHERE peer_group_name = ? LIMIT 1", (group_name,)
        ).fetchone()
        if exists is None:
            raise HTTPException(
                status_code=404, detail=f"Peer group '{group_name}' not found"
            )

        members = conn.execute(
            """
            SELECT company_id, is_benchmark FROM peer_groups
            WHERE peer_group_name = ? ORDER BY is_benchmark DESC, company_id
        """,
            (group_name,),
        ).fetchall()

        percentiles = conn.execute(
            """
            SELECT company_id, metric, value, percentile_rank, year
            FROM peer_percentiles WHERE peer_group_name = ?
        """,
            (group_name,),
        ).fetchall()
    finally:
        conn.close()

    by_company = {}
    for row in percentiles:
        d = dict(row)
        cid = d.pop("company_id")
        by_company.setdefault(cid, []).append(d)

    results = []
    for m in members:
        cid = m["company_id"]
        results.append(
            {
                "company_id": cid,
                "is_benchmark": bool(m["is_benchmark"]),
                "metrics": by_company.get(cid, []),
            }
        )

    return {"peer_group_name": group_name, "count": len(results), "results": results}


@router.get("/companies/{ticker}/peers/compare")
def compare_to_peers(ticker: str, request: Request):
    """Return radar-chart data comparing a company against its peer group average and a benchmark company."""
    conn = request.app.state.get_db_connection()
    try:
        company_group = conn.execute(
            "SELECT peer_group_name, is_benchmark FROM peer_groups WHERE company_id = ?",
            (ticker,),
        ).fetchone()
        if company_group is None:
            raise HTTPException(
                status_code=404,
                detail=f"'{ticker}' is not assigned to any peer group",
            )
        group_name = company_group["peer_group_name"]

        benchmark_row = conn.execute(
            "SELECT company_id FROM peer_groups WHERE peer_group_name = ? AND is_benchmark = 1",
            (group_name,),
        ).fetchone()
        benchmark_id = benchmark_row["company_id"] if benchmark_row else None

        placeholders = ",".join("?" * len(RADAR_METRICS))
        company_metrics = conn.execute(
            f"""
            SELECT metric, value, percentile_rank FROM peer_percentiles
            WHERE company_id = ? AND peer_group_name = ? AND metric IN ({placeholders})
        """,
            [ticker, group_name] + RADAR_METRICS,
        ).fetchall()

        group_avg = conn.execute(
            f"""
            SELECT metric, AVG(value) as avg_value FROM peer_percentiles
            WHERE peer_group_name = ? AND metric IN ({placeholders})
            GROUP BY metric
        """,
            [group_name] + RADAR_METRICS,
        ).fetchall()

        benchmark_metrics = []
        if benchmark_id:
            benchmark_metrics = conn.execute(
                f"""
                SELECT metric, value FROM peer_percentiles
                WHERE company_id = ? AND peer_group_name = ? AND metric IN ({placeholders})
            """,
                [benchmark_id, group_name] + RADAR_METRICS,
            ).fetchall()
    finally:
        conn.close()

    return {
        "company_id": ticker,
        "peer_group_name": group_name,
        "benchmark_company_id": benchmark_id,
        "company_values": {r["metric"]: r["value"] for r in company_metrics},
        "peer_group_average": {r["metric"]: r["avg_value"] for r in group_avg},
        "benchmark_values": {r["metric"]: r["value"] for r in benchmark_metrics},
    }
