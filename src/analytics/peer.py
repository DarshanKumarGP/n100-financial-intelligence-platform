"""
N100 Financial Intelligence Platform
Sprint 3, Day 18: Peer Percentile Rankings

Computes PERCENT_RANK for 10 metrics within each of 11 peer groups.
D/E is inverted (1 - percentile) since lower D/E is better -- every
other metric here follows "higher is better" naturally.

Companies not in any peer group return a 'No peer group assigned'
message rather than raising an error, per spec.
"""

import sqlite3
import pandas as pd

DB_PATH = "data/nifty100.db"

METRICS = [
    "return_on_equity_pct",
    "return_on_capital_employed_pct",
    "net_profit_margin_pct",
    "debt_to_equity",              # inverted -- lower is better
    "free_cash_flow_cr",
    "pat_cagr_5yr",
    "revenue_cagr_5yr",
    "eps_cagr_5yr",
    "interest_coverage",
    "asset_turnover",
]


def build_latest_ratios_with_groups(conn):
    """One row per company: latest fiscal year's financial_ratios, joined
    with peer_groups (may be NULL -- that's expected, not an error)."""
    query = """
        SELECT fr.company_id, fr.year,
               fr.return_on_equity_pct, fr.return_on_capital_employed_pct,
               fr.net_profit_margin_pct, fr.debt_to_equity,
               fr.free_cash_flow_cr, fr.pat_cagr_5yr, fr.revenue_cagr_5yr,
               fr.eps_cagr_5yr, fr.interest_coverage, fr.asset_turnover,
               fr.icr_label,
               pg.peer_group_name
        FROM financial_ratios fr
        LEFT JOIN peer_groups pg ON fr.company_id = pg.company_id
        WHERE fr.year = (
            SELECT MAX(fr2.year) FROM financial_ratios fr2
            WHERE fr2.company_id = fr.company_id
        )
    """
    return pd.read_sql(query, conn)


def compute_percentiles_for_group(group_df, metric):
    """
    Returns a Series of percentile ranks (0-1) for one metric within one
    peer group. D/E is inverted so lower values get HIGHER percentiles.
    ICR uses icr_label='Debt Free' as the best possible value (treated
    as the max, same "infinity" logic used in Days 15 and 17).
    """
    values = group_df[metric].copy()

    if metric == "interest_coverage":
        # Debt Free companies get the max real ICR value + 1, so they
        # always rank at or above every finite ICR in the group.
        finite_max = values.dropna().max() if values.notna().any() else 0
        values = group_df.apply(
            lambda r: (finite_max + 1) if r.get("icr_label") == "Debt Free" else r[metric],
            axis=1
        )

    ranks = values.rank(pct=True, na_option="keep")

    if metric == "debt_to_equity":
        ranks = 1 - ranks

    return ranks


def compute_peer_percentiles(conn):
    """
    Returns a long-format DataFrame: company_id, peer_group_name, metric,
    value, percentile_rank, year -- ready to write to peer_percentiles table.
    Companies with no peer group are captured separately with a clear
    'No peer group assigned' status, not silently dropped or errored.
    """
    df = build_latest_ratios_with_groups(conn)

    grouped = df[df["peer_group_name"].notna()]
    ungrouped = df[df["peer_group_name"].isna()]

    print(f"{len(grouped)} companies have a peer group; {len(ungrouped)} do not.")
    if len(ungrouped) > 0:
        print("Companies with no peer group assigned:", sorted(ungrouped["company_id"].tolist()))

    results = []
    for group_name, group_df in grouped.groupby("peer_group_name"):
        for metric in METRICS:
            percentiles = compute_percentiles_for_group(group_df, metric)
            for idx, pct in percentiles.items():
                row = group_df.loc[idx]
                results.append({
                    "company_id": row["company_id"],
                    "peer_group_name": group_name,
                    "metric": metric,
                    "value": row[metric],
                    "percentile_rank": pct,
                    "year": row["year"],
                })

    percentiles_df = pd.DataFrame(results)

    # Ungrouped companies: explicit status rows, not silently omitted
    no_group_rows = [{
        "company_id": row["company_id"], "peer_group_name": None,
        "metric": None, "value": None, "percentile_rank": None,
        "year": row["year"], "status": "No peer group assigned",
    } for _, row in ungrouped.iterrows()]

    return percentiles_df, pd.DataFrame(no_group_rows)


def write_to_db(conn, percentiles_df):
    conn.execute("DROP TABLE IF EXISTS peer_percentiles;")
    conn.execute("""
        CREATE TABLE peer_percentiles (
            company_id TEXT NOT NULL,
            peer_group_name TEXT NOT NULL,
            metric TEXT NOT NULL,
            value REAL,
            percentile_rank REAL,
            year TEXT NOT NULL,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        );
    """)
    percentiles_df.to_sql("peer_percentiles", conn, if_exists="append", index=False)
    conn.commit()


def main():
    conn = sqlite3.connect(DB_PATH)
    percentiles_df, no_group_df = compute_peer_percentiles(conn)
    write_to_db(conn, percentiles_df)

    count = conn.execute("SELECT COUNT(*) FROM peer_percentiles;").fetchone()[0]
    distinct_companies = conn.execute("SELECT COUNT(DISTINCT company_id) FROM peer_percentiles;").fetchone()[0]
    distinct_groups = conn.execute("SELECT COUNT(DISTINCT peer_group_name) FROM peer_percentiles;").fetchone()[0]

    print(f"\npeer_percentiles table: {count} rows")
    print(f"Distinct companies ranked: {distinct_companies}")
    print(f"Distinct peer groups covered: {distinct_groups}")

    conn.close()
    return no_group_df


if __name__ == "__main__":
    main()