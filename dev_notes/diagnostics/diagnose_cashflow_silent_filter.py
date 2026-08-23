import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "etl"))
from validator import load_and_normalize, CORE_FILES

cf = load_and_normalize(CORE_FILES["cashflow"], "cashflow")
companies = load_and_normalize(CORE_FILES["companies"], "companies")
valid_ids = set(companies["id"])

print(f"Step 0 — raw loaded: {len(cf)}")

# Reproduce the loader's exact sequence, with explicit prints at every stage
before_dedup = len(cf)
cf_deduped = cf.drop_duplicates(subset=["company_id", "year"], keep="last")
print(f"Step 1 — after dedup: {len(cf_deduped)}  (removed {before_dedup - len(cf_deduped)})")

before_orphan = len(cf_deduped)
cf_final = cf_deduped[cf_deduped["company_id"].isin(valid_ids)]
print(f"Step 2 — after orphan filter: {len(cf_final)}  (removed {before_orphan - len(cf_final)})")

# Now the AGTL / ATGL question specifically
print(f"\nAGTL rows in raw cashflow: {(cf['company_id'] == 'AGTL').sum()}")
print(f"ATGL rows in raw cashflow: {(cf['company_id'] == 'ATGL').sum()}")
print(f"Is 'ATGL' in companies.id?  {'ATGL' in valid_ids}")
print(f"Is 'AGTL' in companies.id?  {'AGTL' in valid_ids}")

# Check whether AGTL and ATGL appear in the OTHER core files too, or if it's cashflow-specific
for name in ["profitandloss", "balancesheet"]:
    df = load_and_normalize(CORE_FILES[name], name)
    print(f"{name}: AGTL rows={( df['company_id']=='AGTL').sum()}, ATGL rows={(df['company_id']=='ATGL').sum()}")