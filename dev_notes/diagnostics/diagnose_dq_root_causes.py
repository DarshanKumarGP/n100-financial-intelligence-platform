import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "etl"))

import pandas as pd
from validator import load_and_normalize, CORE_FILES

companies = load_and_normalize(CORE_FILES["companies"], "companies")
pl = load_and_normalize(CORE_FILES["profitandloss"], "profitandloss")

# --- Problem 1: orphan tickers ---
orphans = ['ULTRACEMCO', 'UNIONBANK', 'UNITDSPR', 'VBL', 'VEDL', 'WIPRO', 'ZOMATO', 'ZYDUSLIFE']
print("=== Checking each orphan against companies.id (repr to catch hidden chars) ===")
for tick in orphans:
    matches = companies[companies["id"].str.contains(tick, case=False, na=False)]
    if matches.empty:
        print(f"{tick}: NO similar match found in companies.xlsx at all")
    else:
        for _, row in matches.iterrows():
            print(f"{tick}: found companies.id={row['id']!r} (len={len(row['id'])})")

print("\n=== Full companies.id list (repr) for manual scan ===")
for i in sorted(companies["id"]):
    print(repr(i))

# --- Problem 2: duplicate rows — are they identical or different values? ---
print("\n=== ADANIPORTS 2013-03 rows — full column comparison ===")
subset = pl[(pl["company_id"] == "ADANIPORTS") & (pl["year"] == "2013-03")]
print(subset.T.to_string())  # transposed so we can compare column-by-column