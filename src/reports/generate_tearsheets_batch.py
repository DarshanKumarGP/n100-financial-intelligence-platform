"""
N100 Financial Intelligence Platform
Sprint 5, Day 34: Batch Tearsheet Generation

Location: src/reports/generate_tearsheets_batch.py

Runs generate_tearsheet() (Day 33, src/reports/tearsheet.py) across all
92 companies. Companies with fewer than 3 years of financial_ratios
history are skipped -- confirmed 2026-09: only JIOFIN (2 years) meets
this condition, consistent with its known thin-history status
throughout the project.

Produces:
  - reports/tearsheets/<TICKER>_tearsheet.pdf for every company with
    >= 3 years of history
  - output/skipped_tearsheets.csv: logs any skipped tickers with reason
"""

import os
import sqlite3
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tearsheet import generate_tearsheet

DB_PATH = "data/nifty100.db"
TEARSHEET_DIR = "reports/tearsheets"


def main():
    """CLI entry point: batch-generate tearsheet PDFs for all companies with at least 3 years of data, logging skipped tickers to output/skipped_tearsheets.csv."""
    conn = sqlite3.connect(DB_PATH)
    companies = pd.read_sql("SELECT id FROM companies ORDER BY id;", conn)[
        "id"
    ].tolist()
    conn.close()

    os.makedirs(TEARSHEET_DIR, exist_ok=True)

    generated = []
    skipped = []

    for company_id in companies:
        output_path = f"{TEARSHEET_DIR}/{company_id}_tearsheet.pdf"
        try:
            ok, msg = generate_tearsheet(company_id, output_path)
            if ok:
                size_kb = os.path.getsize(output_path) / 1024
                generated.append(
                    {"company_id": company_id, "size_kb": round(size_kb, 1)}
                )
            else:
                skipped.append({"company_id": company_id, "reason": msg})
        except Exception as e:  # noqa: BLE001 -- intentional: one company's failure must not abort the batch
            skipped.append({"company_id": company_id, "reason": f"EXCEPTION: {e}"})

    print(f"Generated: {len(generated)} tearsheets")
    print(f"Skipped: {len(skipped)}")
    if skipped:
        print("Skipped companies:")
        for s in skipped:
            print(f"  {s['company_id']}: {s['reason']}")

    os.makedirs("output", exist_ok=True)
    skipped_df = pd.DataFrame(skipped)
    skipped_df.to_csv("output/skipped_tearsheets.csv", index=False)
    print(f"\noutput/skipped_tearsheets.csv written: {len(skipped_df)} rows")

    # Verify file sizes all clear the 30 KB exit-criterion floor
    generated_df = pd.DataFrame(generated)
    if len(generated_df):
        under_30kb = generated_df[generated_df["size_kb"] < 30]
        print(
            f"\nGenerated files under 30 KB (exit criterion check): {len(under_30kb)}"
        )
        if len(under_30kb):
            print(under_30kb.to_string(index=False))
        print(
            f"Size range: {generated_df['size_kb'].min():.1f} KB - {generated_df['size_kb'].max():.1f} KB"
        )

    return generated_df, skipped_df


if __name__ == "__main__":
    main()
