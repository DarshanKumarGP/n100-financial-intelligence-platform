import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "etl"))

import pandas as pd
from validator import load_and_normalize, CORE_FILES

companies = load_and_normalize(CORE_FILES["companies"], "companies")
pl = load_and_normalize(CORE_FILES["profitandloss"], "profitandloss")

valid_ids = set(companies["id"])
pl_ids = set(pl["company_id"])
orphan_ids = pl_ids - valid_ids

print(f"Companies loaded: {len(valid_ids)}")
print(f"Orphan company_ids found in P&L but not in companies.id: {len(orphan_ids)}")
print(sorted(orphan_ids)[:20])
print()
print("Sample of companies.id values:", sorted(valid_ids)[:10])
print()

# Now look at the duplicate pairs specifically
dupes = pl[pl.duplicated(subset=["company_id", "year"], keep=False)]
print(f"Duplicate (company_id, year) rows in P&L: {len(dupes)}")
print(dupes[["company_id", "year", "year_raw"]].sort_values(["company_id", "year"]).head(20).to_string())