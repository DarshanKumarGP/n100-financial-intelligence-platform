import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "etl"))
import pandas as pd
from validator import load_and_normalize, CORE_FILES

companies = load_and_normalize(CORE_FILES["companies"], "companies")
bs = load_and_normalize(CORE_FILES["balancesheet"], "balancesheet")

valid_ids = set(companies["id"])
orphan_ids = set(bs["company_id"]) - valid_ids

# Rows that are BOTH duplicates AND belong to an orphan company
dupe_mask = bs.duplicated(subset=["company_id", "year"], keep=False)
orphan_mask = bs["company_id"].isin(orphan_ids)

print(f"Total BS rows: {len(bs)}")
print(f"Rows flagged as duplicate (DQ-02 style, both copies counted): {dupe_mask.sum()}")
print(f"Rows flagged as orphan (DQ-03 style): {orphan_mask.sum()}")
print(f"Rows that are BOTH duplicate AND orphan: {(dupe_mask & orphan_mask).sum()}")
print(f"Rows that are duplicate but NOT orphan: {(dupe_mask & ~orphan_mask).sum()}")

# Simulate the loader's actual sequential logic and show its real removal counts
clean = bs[bs["year"] != "PARSE_ERROR"].copy()
before_dedup = len(clean)
clean_deduped = clean.drop_duplicates(subset=["company_id", "year"], keep="last")
dedup_removed = before_dedup - len(clean_deduped)

before_orphan = len(clean_deduped)
clean_final = clean_deduped[clean_deduped["company_id"].isin(valid_ids)]
orphan_removed = before_orphan - len(clean_final)

print(f"\nSequential (loader's actual order): dedup removed={dedup_removed}, orphan removed={orphan_removed}")
print(f"Final row count: {len(clean_final)}")