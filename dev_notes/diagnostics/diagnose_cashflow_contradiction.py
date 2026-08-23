import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "etl"))
from validator import load_and_normalize, CORE_FILES

cf = load_and_normalize(CORE_FILES["cashflow"], "cashflow")

print(f"Total cashflow rows after load_and_normalize: {len(cf)}")
print(f"Columns: {list(cf.columns)}")

# Re-check duplicates fresh, right now
dupe_mask = cf.duplicated(subset=["company_id", "year"], keep=False)
print(f"\nDuplicate (company_id, year) rows found: {dupe_mask.sum()}")

# Re-check orphans fresh, right now
companies = load_and_normalize(CORE_FILES["companies"], "companies")
valid_ids = set(companies["id"])
orphan_mask = ~cf["company_id"].isin(valid_ids)
print(f"Orphan rows found: {orphan_mask.sum()}")
if orphan_mask.sum() > 0:
    print("Sample orphan company_ids:", sorted(cf[orphan_mask]["company_id"].unique())[:10])

# Sanity check: does this match what the loader actually inserted?
import sqlite3
conn = sqlite3.connect("data/nifty100.db")
db_count = conn.execute("SELECT COUNT(*) FROM cashflow;").fetchone()[0]
db_company_ids = set(row[0] for row in conn.execute("SELECT DISTINCT company_id FROM cashflow;").fetchall())
print(f"\nRows actually in nifty100.db cashflow table: {db_count}")
print(f"Distinct companies in DB cashflow table: {len(db_company_ids)}")
missing_from_db = valid_ids - db_company_ids
print(f"Valid companies with NO cashflow rows in DB at all: {sorted(missing_from_db)}")
conn.close()