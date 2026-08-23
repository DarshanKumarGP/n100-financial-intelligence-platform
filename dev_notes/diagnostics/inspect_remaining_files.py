import pandas as pd

CORE_REMAINING = {
    "documents": "data/raw/documents.xlsx",
    "analysis": "data/raw/analysis.xlsx",
    "prosandcons": "data/raw/prosandcons.xlsx",
}

SUPPLEMENTARY = {
    "sectors": "data/supporting/sectors.xlsx",
    "stock_prices": "data/supporting/stock_prices.xlsx",
    "market_cap": "data/supporting/market_cap.xlsx",
    "financial_ratios": "data/supporting/financial_ratios.xlsx",
    "peer_groups": "data/supporting/peer_groups.xlsx",
}

print("=" * 70)
print("CORE FILES (header=1)")
print("=" * 70)
for name, path in CORE_REMAINING.items():
    df = pd.read_excel(path, header=1)
    print(f"\n--- {name} ({path}) ---")
    print(f"Shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")
    print(df.head(3).to_string())

print("\n" + "=" * 70)
print("SUPPLEMENTARY FILES (header=0)")
print("=" * 70)
for name, path in SUPPLEMENTARY.items():
    df = pd.read_excel(path, header=0)
    print(f"\n--- {name} ({path}) ---")
    print(f"Shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")
    print(df.head(3).to_string())