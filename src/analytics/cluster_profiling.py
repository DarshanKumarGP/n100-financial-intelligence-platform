"""
N100 Financial Intelligence Platform
Sprint 6, Day 37: Cluster Profiling & Statistics

Location: src/analytics/cluster_profiling.py

Four outputs:
  1. Cluster profile (mean/median of the 5 clustering features per
     cluster) + a PROPOSED descriptive name per cluster -- printed for
     team lead review, per the spec's own instruction. Naming logic
     (2026-09, after reviewing real per-cluster data):
       - Cluster 2 (BEL, HAL) and Cluster 3 (CIPLA): known
         outlier-driven clusters from Day 36 (extreme ROE / extreme
         FCF CAGR), named explicitly as statistical outliers rather
         than forced into a spec archetype name.
       - Cluster 1 (15 companies): confirmed ALL Financials
         (banks/NBFCs). High mean D/E (7.23) reflects the sector's
         business model, not distress -- named "Leveraged Financials"
         via a sector-dominance override rather than the generic
         leverage-based quadrant rule, which would have mislabeled it
         (same mistake already caught once in Sprint 5, applying
         industrial ICR/ROCE thresholds to HDFCBANK).
       - Cluster 4 (14 companies): median ROE (14.7%) is ordinary, but
         mean ROE (78.2%) is skewed by INDIGO alone (892.6% ROE, ~20x
         the next-highest member, COALINDIA at 45.2%) -- confirmed via
         per-company breakdown. Named to disclose the skew rather than
         imply the whole cluster behaves like INDIGO.
       - Generic quadrant rule (clusters without a special case) now
         uses MEDIAN, not mean, for robustness -- mean was proven
         unreliable by cluster 4's own skew.
     This script updates output/cluster_labels.csv's cluster_name
     column with these PROPOSED names; treat as a first-pass pending
     team lead review, not final.
  2. reports/correlation_heatmap.png -- Pearson correlation of 10 KPIs
     (list not specified by spec; chosen as the most-used ratios
     throughout this project -- see KPI_10 below) across all 92
     companies, latest year.
  3. output/outlier_report.csv -- per-sector Z-score outlier flags
     (|Z| > 3) on the same 10 KPIs. Z-scores computed WITHIN each
     broad_sector (not globally), per spec wording "Z-score for each
     metric per broad_sector".
  4. output/portfolio_stats.csv -- P10/P25/P50/P75/P90/Mean/Std for
     the same 10 KPIs across all 92 companies.

All 10 KPI columns are coerced with pd.to_numeric() defensively before
any computation -- this project has now hit SQLite dtype inconsistency
twice (cfo_pat_ratio_5yr in Sprint 5, fcf_cagr_5yr in Day 36), so every
new script touching financial_ratios columns applies this defensively
rather than waiting to hit it a third time.
"""

import os
import sqlite3

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

DB_PATH = "data/nifty100.db"
CLUSTER_LABELS_PATH = "output/cluster_labels.csv"

# The 5 features Day 36's clustering actually used -- profiling reuses
# these, per spec: "compute mean and median of all 5 input features"
CLUSTERING_FEATURES = [
    "return_on_equity_pct",
    "debt_to_equity",
    "revenue_cagr_5yr",
    "fcf_cagr_5yr",
    "operating_profit_margin_pct",
]

# The 10 KPIs used for correlation heatmap, outlier detection, and
# portfolio stats -- spec doesn't name them; chosen as the most-used
# ratios elsewhere in this project. Flagged as an assumption.
KPI_10 = [
    "return_on_equity_pct",
    "return_on_capital_employed_pct",
    "return_on_assets_pct",
    "debt_to_equity",
    "revenue_cagr_5yr",
    "pat_cagr_5yr",
    "eps_cagr_5yr",
    "operating_profit_margin_pct",
    "net_profit_margin_pct",
    "dividend_payout_ratio_pct",
]

ALL_NEEDED_COLS = sorted(set(CLUSTERING_FEATURES) | set(KPI_10))

# Known outlier clusters from Day 36 -- confirmed root causes:
#   Cluster 2: BEL, HAL -- extreme ROE (small-equity-base artifact,
#     same root cause flagged since Sprint 2)
#   Cluster 3: CIPLA -- extreme fcf_cagr_5yr (228.75%, dataset max by
#     a wide margin), compounded by the still-unresolved
#     operating_profit reliability flag from Sprint 1/2
KNOWN_OUTLIER_CLUSTER_COMPANIES = {
    frozenset(
        {"BEL", "HAL"}
    ): "Statistical Outliers (Extreme ROE -- small equity base)",
    frozenset({"CIPLA"}): "Statistical Outlier (Extreme FCF CAGR)",
}

# Cluster 1's 15 members are ALL Financials (banks/NBFCs) -- confirmed
# 2026-09. High mean D/E (7.23) reflects the sector's business model,
# not distress -- same mistake already caught once in Sprint 5
# (applying industrial ICR/ROCE thresholds to HDFCBANK). A
# sector-composition check overrides the generic quadrant rule.
SECTOR_DOMINATED_OVERRIDE_NAME = "Leveraged Financials"
SECTOR_DOMINATED_THRESHOLD = 0.9  # >=90% of cluster from one sector

# Cluster 4: median ROE (14.7%) is ordinary, but INDIGO's 892.6% ROE
# (confirmed 2026-09 -- ~20x the next-highest member, COALINDIA at
# 45.2%) drags the mean to 78.2%, misleadingly high. Named to disclose
# the skew rather than imply the whole cluster behaves like INDIGO.
KNOWN_SKEWED_CLUSTER_NAMES = {
    "INDIGO": "Diversified / Growth (INDIGO ROE outlier present)",
}


def load_latest_ratios(conn):
    """Load each company's latest-year value for every profiling KPI from financial_ratios."""
    fr = pd.read_sql(
        f"""
        SELECT company_id, year, {", ".join(ALL_NEEDED_COLS)}
        FROM financial_ratios WHERE year != 'TTM'
        ORDER BY company_id, year
    """,
        conn,
    )
    for col in ALL_NEEDED_COLS:
        fr[col] = pd.to_numeric(fr[col], errors="coerce")

    sectors = pd.read_sql("SELECT company_id, broad_sector FROM sectors;", conn)
    latest = fr.sort_values("year").groupby("company_id").tail(1).reset_index(drop=True)
    latest = latest.merge(sectors, on="company_id", how="left")
    return latest


def propose_cluster_name(cluster_id, companies, profile_row, sectors_lookup):
    """
    Rule-based name proposal, in priority order:
      1. Exact match against a known outlier cluster (BEL+HAL, CIPLA)
      2. Sector-dominated override (e.g. an all-Financials cluster
         shouldn't get a generic leverage-based name)
      3. Known-skew disclosure (a cluster whose mean is distorted by
         one flagged extreme member)
      4. Generic quadrant rule over ROE / D/E / revenue CAGR (uses
         MEDIAN, not mean -- mean proven unreliable by cluster 4)
    THIS IS A PROPOSAL ONLY -- spec explicitly asks for team lead
    review before treating any name as final.
    """
    company_set = frozenset(companies)
    if company_set in KNOWN_OUTLIER_CLUSTER_COMPANIES:
        return KNOWN_OUTLIER_CLUSTER_COMPANIES[company_set]

    # Sector-dominated check
    cluster_sectors = [sectors_lookup.get(c) for c in companies]
    if cluster_sectors:
        top_sector = max(set(cluster_sectors), key=cluster_sectors.count)
        top_sector_share = cluster_sectors.count(top_sector) / len(cluster_sectors)
        if (
            top_sector_share >= SECTOR_DOMINATED_THRESHOLD
            and top_sector == "Financials"
        ):
            return SECTOR_DOMINATED_OVERRIDE_NAME

    # Known-skew disclosure
    for flagged_company, name in KNOWN_SKEWED_CLUSTER_NAMES.items():
        if flagged_company in companies:
            return name

    roe = profile_row[
        "return_on_equity_pct_median"
    ]  # median, not mean -- less skew-sensitive
    de = profile_row["debt_to_equity_median"]
    rev_cagr = profile_row["revenue_cagr_5yr_median"]

    if roe > 20 and de < 1.0:
        return "High-Quality Compounders"
    if roe < 10 and de < 1.0:
        return "Defensive Dividend Payers"
    if de > 2.0 and roe < 10:
        return "Distressed or Turnaround"
    if rev_cagr > 20:
        return "Emerging Growth"
    return "Core / Broad Market"


def build_cluster_profile(labels_df, ratios_df):
    """Compute mean and median of the clustering features per cluster and assign a descriptive cluster name."""
    merged = labels_df.merge(ratios_df, on="company_id", how="left")
    sectors_lookup = dict(zip(merged["company_id"], merged["broad_sector"]))

    agg = merged.groupby("cluster_id")[CLUSTERING_FEATURES].agg(["mean", "median"])
    agg.columns = ["_".join(c) for c in agg.columns]
    agg = agg.reset_index()

    proposed_names = []
    for _, row in agg.iterrows():
        cid = row["cluster_id"]
        companies = merged[merged["cluster_id"] == cid]["company_id"].tolist()
        name = propose_cluster_name(cid, companies, row, sectors_lookup)
        proposed_names.append(name)
    agg["proposed_name"] = proposed_names
    agg["company_count"] = agg["cluster_id"].map(merged.groupby("cluster_id").size())

    return agg


def build_correlation_heatmap(ratios_df, output_path="reports/correlation_heatmap.png"):
    """Compute the Pearson correlation matrix of the 10 profiling KPIs and save it as an annotated seaborn heatmap to reports/correlation_heatmap.png."""
    corr = ratios_df[KPI_10].corr(method="pearson")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig, ax = plt.subplots(figsize=(11, 9), dpi=150)
    sns.heatmap(
        corr,
        annot=True,
        fmt=".2f",
        cmap="coolwarm",
        center=0,
        square=True,
        linewidths=0.5,
        ax=ax,
        cbar_kws={"shrink": 0.8},
    )
    ax.set_title("Pearson Correlation -- 10 KPIs, latest year (92 companies)")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)

    return corr


def build_outlier_report(ratios_df):
    """
    Z-score computed WITHIN each broad_sector, per metric. A company
    is flagged if |Z| > 3 on ANY of the 10 KPIs. NaN inputs (already-
    known missing values -- SBIN, PNB, JIOFIN, and the 43 fcf_cagr_5yr
    edge cases) produce NaN Z-scores, which are correctly excluded
    from flagging rather than treated as outliers.
    """
    df = ratios_df.copy()
    records = []

    for sector, group in df.groupby("broad_sector"):
        for col in KPI_10:
            vals = group[col]
            std = vals.std()
            mean = vals.mean()
            if pd.isna(std) or std == 0:
                continue  # can't compute a meaningful Z-score
            z = (vals - mean) / std
            flagged = group[z.abs() > 3]
            for _, row in flagged.iterrows():
                records.append(
                    {
                        "company_id": row["company_id"],
                        "broad_sector": sector,
                        "metric": col,
                        "value": row[col],
                        "sector_mean": mean,
                        "sector_std": std,
                        "z_score": z[row.name],
                    }
                )

    result = pd.DataFrame(records)
    os.makedirs("output", exist_ok=True)
    result.to_csv("output/outlier_report.csv", index=False)
    return result


def build_portfolio_stats(ratios_df):
    """Compute P10-P90, mean, and standard deviation for each KPI across all companies."""
    stats = ratios_df[KPI_10].describe(percentiles=[0.10, 0.25, 0.50, 0.75, 0.90]).T
    stats = stats.rename(
        columns={
            "10%": "P10",
            "25%": "P25",
            "50%": "P50",
            "75%": "P75",
            "90%": "P90",
            "mean": "Mean",
            "std": "Std",
        }
    )
    stats = stats[["P10", "P25", "P50", "P75", "P90", "Mean", "Std"]]
    stats.index.name = "kpi"
    stats = stats.reset_index()

    os.makedirs("output", exist_ok=True)
    stats.to_csv("output/portfolio_stats.csv", index=False)
    return stats


def main():
    """CLI entry point: profile clusters, run per-sector outlier detection, and write outlier_report.csv and portfolio_stats.csv."""
    conn = sqlite3.connect(DB_PATH)
    ratios = load_latest_ratios(conn)
    conn.close()

    labels = pd.read_csv(CLUSTER_LABELS_PATH)

    # --- 1. Cluster profile + proposed names ---
    profile = build_cluster_profile(labels, ratios)
    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 20)
    print("=== Cluster Profile (mean/median of the 5 clustering features) ===")
    print(profile.to_string(index=False))
    print()
    print("Proposed names are RULE-BASED FIRST-PASS SUGGESTIONS.")
    print("Per spec: review with team lead before treating as final.\n")

    # Write proposed names back into cluster_labels.csv
    name_map = dict(zip(profile["cluster_id"], profile["proposed_name"]))
    labels["cluster_name"] = labels["cluster_id"].map(name_map)
    labels.to_csv(CLUSTER_LABELS_PATH, index=False)
    print(f"{CLUSTER_LABELS_PATH} updated with proposed cluster_name values.\n")

    # --- 2. Correlation heatmap ---
    corr = build_correlation_heatmap(ratios)
    print("reports/correlation_heatmap.png written")
    # Flag any unexpectedly strong correlations worth a second look
    strong = corr.where(~np.eye(len(corr), dtype=bool)).abs().stack()
    strong = strong[strong > 0.8].sort_values(ascending=False)
    if len(strong):
        print("\nKPI pairs with |correlation| > 0.8 (worth a sanity check):")
        seen = set()
        for (a, b), v in strong.items():
            if (b, a) in seen:
                continue
            seen.add((a, b))
            print(f"  {a} <-> {b}: {v:.2f}")

    # --- 3. Outlier report ---
    outliers = build_outlier_report(ratios)
    print(f"\noutput/outlier_report.csv written: {len(outliers)} flagged rows")
    if len(outliers):
        print("Flagged companies:", sorted(outliers["company_id"].unique().tolist()))

    # --- 4. Portfolio stats ---
    stats = build_portfolio_stats(ratios)
    print(f"\noutput/portfolio_stats.csv written: {len(stats)} KPIs")
    print(stats.to_string(index=False))

    return profile, corr, outliers, stats


if __name__ == "__main__":
    main()
