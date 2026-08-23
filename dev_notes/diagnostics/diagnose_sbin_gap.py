import sqlite3

conn = sqlite3.connect("data/nifty100.db")

print("=== SBIN across all tables ===")
for table in ["profitandloss", "balancesheet", "cashflow"]:
    count = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE company_id='SBIN';").fetchone()[0]
    print(f"{table}: {count} rows")

conn.close()

print("\n=== Now checking the RAW balancesheet.xlsx directly (before any loader filtering) ===")
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "etl"))
from validator import load_and_normalize, CORE_FILES

bs_raw = load_and_normalize(CORE_FILES["balancesheet"], "balancesheet")
sbin_raw = bs_raw[bs_raw["company_id"] == "SBIN"]
print(f"Raw balancesheet.xlsx rows for SBIN (after ticker normalization): {len(sbin_raw)}")
if len(sbin_raw) > 0:
    print(sbin_raw[["company_id", "year", "year_raw", "total_assets", "total_liabilities"]].to_string())
else:
    print("SBIN not found in raw balancesheet.xlsx at all after normalization.")
    # Check if it exists under a different-looking ticker
    similar = bs_raw[bs_raw["company_id"].str.contains("SBI", na=False)]
    print(f"\nTickers containing 'SBI' in raw balancesheet.xlsx: {similar['company_id'].unique()}")