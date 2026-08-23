import pandas as pd
from src.etl.normaliser import normalize_year

df = pd.read_excel("data/raw/balancesheet.xlsx", header=1)
df["company_id"] = df["company_id"].astype(str).str.strip().str.upper()

results = df["year"].apply(normalize_year)
failures = df[results == "PARSE_ERROR"]

print(f"Total rows: {len(df)}")
print(f"Total failures: {len(failures)}\n")
print("Failing rows (company_id, raw year value):")
for _, row in failures.iterrows():
    print(f"  company_id={row['company_id']!r}  year={row['year']!r}  (type={type(row['year']).__name__})")