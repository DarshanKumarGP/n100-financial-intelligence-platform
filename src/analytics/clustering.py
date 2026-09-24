"""
N100 Financial Intelligence Platform
Sprint 6, Day 36: KMeans Clustering

Location: src/analytics/clustering.py

Assigns all 92 companies to one of 5 clusters based on:
  return_on_equity_pct, debt_to_equity, revenue_cagr_5yr,
  fcf_cagr_5yr, operating_profit_margin_pct (latest non-TTM year)

Imputation: missing values filled with the sector median for that
feature. Confirmed 2026-09: 3 single-feature nulls are the already-known
quirks (JIOFIN: revenue_cagr_5yr undefined, only 2yr history; PNB:
operating_profit_margin_pct undefined, operating_profit is None for all
12 years; SBIN: ROE/D-E undefined, zero balancesheet rows). fcf_cagr_5yr
is null for 43/92 companies -- fully explained by real CAGR edge-case
flags (BOTH_NEGATIVE 17, TURNAROUND 16, DECLINE_TO_LOSS 9,
INSUFFICIENT 1 -- sums to exactly 43), not a data gap.

Sector-median fallback: Communication Services has only 2 companies,
and BOTH are null on fcf_cagr_5yr -- so that sector's median for that
feature is itself undefined. Falls back to the GLOBAL median across all
companies whenever a sector median can't be computed, rather than
leaving a NaN that would break StandardScaler.

dtype fix (2026-09): fcf_cagr_5yr comes back from SQLite as a str-dtype
column (the other 4 features are clean float64) -- same root cause as
cfo_pat_ratio_5yr in Sprint 5 (SQLite dynamic typing + some rows
written inconsistently). Confirmed via direct dtype check before
patching. All 5 features are coerced with pd.to_numeric() defensively,
not just the one that broke, since this pattern has now recurred once
already on a different column.

KMeans: n_clusters=5, random_state=42 (fixed per spec, not tuned).
Elbow plot (k=2..10) generated to confirm k=5 is a reasonable choice,
per spec instruction -- not used to override n_clusters, just to verify.

Outputs:
  - reports/elbow_plot.png
  - output/cluster_labels.csv (company_id, cluster_id, cluster_name,
    distance_from_centroid)
"""

import os
import sqlite3

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

DB_PATH = "data/nifty100.db"
FEATURES = [
    "return_on_equity_pct",
    "debt_to_equity",
    "revenue_cagr_5yr",
    "fcf_cagr_5yr",
    "operating_profit_margin_pct",
]
N_CLUSTERS = 5
RANDOM_STATE = 42

# Placeholder names -- Day 37 profiles each cluster's real financial
# characteristics and assigns descriptive names reviewed with the team
# lead. Using neutral Cluster_0..4 here deliberately rather than
# guessing descriptive names before the profiling data exists.
CLUSTER_NAME_PLACEHOLDER = "Cluster_{}"


def load_latest_features(conn):
    """Load each company's latest-year clustering features, imputing missing values with the sector median (falling back to the global median where a sector median is itself undefined)."""
    fr = pd.read_sql(
        f"""
        SELECT company_id, year, {", ".join(FEATURES)}
        FROM financial_ratios WHERE year != 'TTM'
        ORDER BY company_id, year
    """,
        conn,
    )
    sectors = pd.read_sql("SELECT company_id, broad_sector FROM sectors;", conn)

    # SQLite can return numeric columns as object/string dtype (Arrow
    # backend string inference on mixed-type storage) -- confirmed
    # 2026-09: fcf_cagr_5yr came back as str while the other 4 features
    # were clean float64. Same root cause as cfo_pat_ratio_5yr in
    # Sprint 5. Coerce all 5 features to numeric defensively before any
    # median/imputation logic touches them, rather than only fixing
    # whichever column broke this run.
    for col in FEATURES:
        fr[col] = pd.to_numeric(fr[col], errors="coerce")

    latest = fr.sort_values("year").groupby("company_id").tail(1).reset_index(drop=True)
    latest = latest.merge(sectors, on="company_id", how="left")
    return latest


def impute_with_sector_median(df):
    """
    Fills nulls in FEATURES with the sector median. Falls back to the
    global median for any (sector, feature) combination where the
    sector median is itself undefined -- confirmed 2026-09: this
    applies to Communication Services / fcf_cagr_5yr (both of that
    sector's 2 companies are null on that feature).
    """
    df = df.copy()
    global_medians = df[FEATURES].median()

    fallback_used = []

    for col in FEATURES:
        sector_medians = df.groupby("broad_sector")[col].transform("median")
        still_null_after_sector = df[col].isna() & sector_medians.isna()
        if still_null_after_sector.any():
            affected = df.loc[still_null_after_sector, ["company_id", "broad_sector"]]
            for _, row in affected.iterrows():
                fallback_used.append((row["company_id"], row["broad_sector"], col))

        df[col] = df[col].fillna(sector_medians)
        df[col] = df[col].fillna(global_medians[col])  # global fallback

    if fallback_used:
        print("Sector median undefined -- fell back to GLOBAL median for:")
        for company_id, sector, col in fallback_used:
            print(f"  {company_id} ({sector}) / {col}")

    return df


def generate_elbow_plot(X_scaled, output_path="reports/elbow_plot.png"):
    """Fit KMeans for k=2..10 and save an inertia-vs-k elbow plot to reports/elbow_plot.png."""
    inertias = []
    k_range = range(2, 11)
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
        km.fit(X_scaled)
        inertias.append(km.inertia_)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 5), dpi=150)
    ax.plot(list(k_range), inertias, marker="o")
    ax.axvline(
        x=N_CLUSTERS,
        color="red",
        linestyle="--",
        alpha=0.6,
        label=f"k={N_CLUSTERS} (used)",
    )
    ax.set_xlabel("Number of clusters (k)")
    ax.set_ylabel("Inertia")
    ax.set_title("Elbow Plot -- Inertia vs k")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)

    return dict(zip(k_range, inertias))


def main():
    """CLI entry point: run KMeans clustering (n_clusters=5, random_state=42) and write output/cluster_labels.csv."""
    conn = sqlite3.connect(DB_PATH)
    latest = load_latest_features(conn)
    conn.close()

    print(f"Companies loaded: {len(latest)}")
    print(f"Null counts before imputation:\n{latest[FEATURES].isna().sum()}\n")

    imputed = impute_with_sector_median(latest)

    remaining_nulls = imputed[FEATURES].isna().sum().sum()
    print(f"\nNull count after imputation (should be 0): {remaining_nulls}")
    if remaining_nulls > 0:
        raise ValueError(
            "Imputation left nulls behind -- global median fallback should "
            "have caught everything. Investigate before proceeding."
        )

    X = imputed[FEATURES].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    inertias = generate_elbow_plot(X_scaled)
    print(f"\nInertia by k: {inertias}")
    print("reports/elbow_plot.png written")

    kmeans = KMeans(n_clusters=N_CLUSTERS, random_state=RANDOM_STATE, n_init=10)
    cluster_ids = kmeans.fit_predict(X_scaled)

    # Distance from each point to its assigned cluster's centroid
    distances = np.linalg.norm(X_scaled - kmeans.cluster_centers_[cluster_ids], axis=1)

    result = pd.DataFrame(
        {
            "company_id": imputed["company_id"],
            "cluster_id": cluster_ids,
            "cluster_name": [
                CLUSTER_NAME_PLACEHOLDER.format(cid) for cid in cluster_ids
            ],
            "distance_from_centroid": distances,
        }
    )

    os.makedirs("output", exist_ok=True)
    result.to_csv("output/cluster_labels.csv", index=False)

    print(f"\noutput/cluster_labels.csv written: {len(result)} rows")
    print("\nCluster size distribution:")
    print(result["cluster_id"].value_counts().sort_index())

    return result, imputed, kmeans, scaler


if __name__ == "__main__":
    main()
