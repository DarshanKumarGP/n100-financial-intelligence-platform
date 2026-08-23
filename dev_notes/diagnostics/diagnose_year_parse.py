"""
Diagnostic: show every DISTINCT raw value in profitandloss.xlsx's year
column that normalize_year() couldn't parse, with counts -- not just
the first 10 (which were mostly repeats of the same value).

Run from the project root:
    python diagnose_year_parse.py
"""

import sys
from pathlib import Path
from collections import Counter

import pandas as pd

sys.path.insert(0, str(Path("src/etl")))
from normaliser import normalize_year

df = pd.read_excel("data/raw/profitandloss.xlsx", header=1)

failures = [val for val in df["year"] if normalize_year(val) == "PARSE_ERROR"]

print(f"Total failing rows: {len(failures)}")
print(f"\nDistinct failing values and their counts:")
for value, count in Counter(failures).most_common():
    print(f"  {value!r}: {count} rows")