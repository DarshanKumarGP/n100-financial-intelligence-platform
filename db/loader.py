import sys
import os
import sqlite3
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "etl"))
from validator import load_and_normalize, CORE_FILES
from normaliser import normalize_ticker, normalize_year

DB_PATH = "data/nifty100.db"
SCHEMA_PATH = "db/schema.sql"


def build_schema(conn):
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())


def clean_for_load(df, id_col="company_id", key_cols=None):
    """Apply DQ-02 (dedupe keep last) and drop rows with PARSE_ERROR years."""
    df = df.copy()
    if "year" in df.columns:
        df = df[df["year"] != "PARSE_ERROR"]
    if key_cols:
        before = len(df)
        df = df.drop_duplicates(subset=key_cols, keep="last")
        removed = before - len(df)
        if removed:
            print(f"  Deduplicated {removed} rows on {key_cols}")
    return df


def filter_orphans(df, valid_ids, id_col="company_id"):
    """Apply DQ-03: drop rows whose company_id has no match in companies."""
    before = len(df)
    df = df[df[id_col].isin(valid_ids)]
    removed = before - len(df)
    if removed:
        print(f"  Rejected {removed} orphan rows (no matching company_id)")
    return df


# ---------- Core tables (companies + 3 time-series) ----------

def load_companies(conn):
    companies = load_and_normalize(CORE_FILES["companies"], "companies")
    cols = ["id", "company_logo", "company_name", "chart_link", "about_company",
            "website", "nse_profile", "bse_profile", "face_value", "book_value",
            "roce_percentage", "roe_percentage"]
    companies = companies[[c for c in cols if c in companies.columns]]
    companies.to_sql("companies", conn, if_exists="append", index=False)
    print(f"companies: {len(companies)} rows loaded")
    return set(companies["id"])


def load_timeseries_table(conn, name, table_name, cols, valid_ids):
    print(f"Loading {table_name}...")
    df = load_and_normalize(CORE_FILES[name], name)
    df = clean_for_load(df, key_cols=["company_id", "year"])
    df = filter_orphans(df, valid_ids)
    df = df[[c for c in cols if c in df.columns]]
    df.to_sql(table_name, conn, if_exists="append", index=False)
    print(f"{table_name}: {len(df)} rows loaded\n")


# ---------- Remaining 2 core tables + prosandcons ----------

def load_documents(conn, valid_ids):
    df = pd.read_excel("data/raw/documents.xlsx", header=1)
    df["company_id"] = df["company_id"].apply(normalize_ticker)
    df = df.rename(columns={"Year": "report_year", "Annual_Report": "annual_report"})
    df = filter_orphans(df, valid_ids)
    df = df[["company_id", "report_year", "annual_report"]]
    df.to_sql("documents", conn, if_exists="append", index=False)
    print(f"documents: {len(df)} rows loaded")


def load_analysis(conn, valid_ids):
    df = pd.read_excel("data/raw/analysis.xlsx", header=1)
    df["company_id"] = df["company_id"].apply(normalize_ticker)
    df = filter_orphans(df, valid_ids)
    df = df[["company_id", "compounded_sales_growth", "compounded_profit_growth",
             "stock_price_cagr", "roe"]]
    df.to_sql("analysis", conn, if_exists="append", index=False)
    print(f"analysis: {len(df)} rows loaded")


def load_prosandcons(conn, valid_ids):
    df = pd.read_excel("data/raw/prosandcons.xlsx", header=1)
    df["company_id"] = df["company_id"].apply(normalize_ticker)
    df = filter_orphans(df, valid_ids)
    df = df[["company_id", "pros", "cons"]]
    df.to_sql("prosandcons", conn, if_exists="append", index=False)
    print(f"prosandcons: {len(df)} rows loaded")


# ---------- Supplementary tables ----------

def load_sectors(conn, valid_ids):
    df = pd.read_excel("data/supporting/sectors.xlsx", header=0)
    df["company_id"] = df["company_id"].apply(normalize_ticker)
    df = filter_orphans(df, valid_ids)
    df = df[["company_id", "broad_sector", "sub_sector", "index_weight_pct", "market_cap_category"]]
    df.to_sql("sectors", conn, if_exists="append", index=False)
    print(f"sectors: {len(df)} rows loaded")


def load_stock_prices(conn, valid_ids):
    df = pd.read_excel("data/supporting/stock_prices.xlsx", header=0)
    df["company_id"] = df["company_id"].apply(normalize_ticker)
    df = filter_orphans(df, valid_ids)
    before = len(df)
    df = df.drop_duplicates(subset=["company_id", "date"], keep="last")
    if len(df) != before:
        print(f"  Deduplicated {before - len(df)} rows on ['company_id', 'date']")
    df = df.rename(columns={"date": "price_date"})
    df = df[["company_id", "price_date", "open_price", "high_price", "low_price",
             "close_price", "volume", "adjusted_close"]]
    df.to_sql("stock_prices", conn, if_exists="append", index=False)
    print(f"stock_prices: {len(df)} rows loaded")


def load_market_cap(conn, valid_ids):
    df = pd.read_excel("data/supporting/market_cap.xlsx", header=0)
    df["company_id"] = df["company_id"].apply(normalize_ticker)
    df = filter_orphans(df, valid_ids)
    before = len(df)
    df = df.drop_duplicates(subset=["company_id", "year"], keep="last")
    if len(df) != before:
        print(f"  Deduplicated {before - len(df)} rows on ['company_id', 'year']")
    df = df[["company_id", "year", "market_cap_crore", "enterprise_value_crore",
             "pe_ratio", "pb_ratio", "ev_ebitda", "dividend_yield_pct"]]
    df.to_sql("market_cap", conn, if_exists="append", index=False)
    print(f"market_cap: {len(df)} rows loaded")


def load_financial_ratios_source(conn, valid_ids):
    """
    Loads the SOURCE-provided financial_ratios.xlsx into financial_ratios_source.
    This is display/cross-check data only (spec Day 13) -- NOT the table our
    own Ratio Engine writes to. Sprint 2 populates a separate, freshly-computed
    'financial_ratios' table (see db/schema.sql), which is the authoritative
    one for all analytics per Sprint 1 Finding 4 (source OPM field unreliable).
    """
    df = pd.read_excel("data/supporting/financial_ratios.xlsx", header=0)
    df["company_id"] = df["company_id"].apply(normalize_ticker)
    df["year"] = df["year"].apply(normalize_year)
    df = df[df["year"] != "PARSE_ERROR"]
    df = filter_orphans(df, valid_ids)
    before = len(df)
    df = df.drop_duplicates(subset=["company_id", "year"], keep="last")
    if len(df) != before:
        print(f"  Deduplicated {before - len(df)} rows on ['company_id', 'year'] "
              f"(NOTE: source rows differed in value — kept last, see DQ review)")
    cols = ["company_id", "year", "net_profit_margin_pct", "operating_profit_margin_pct",
            "return_on_equity_pct", "debt_to_equity", "interest_coverage", "asset_turnover",
            "free_cash_flow_cr", "capex_cr", "earnings_per_share", "book_value_per_share",
            "dividend_payout_ratio_pct", "total_debt_cr", "cash_from_operations_cr"]
    df = df[cols]
    df.to_sql("financial_ratios_source", conn, if_exists="append", index=False)
    print(f"financial_ratios_source: {len(df)} rows loaded")


def load_peer_groups(conn, valid_ids):
    df = pd.read_excel("data/supporting/peer_groups.xlsx", header=0)
    df["company_id"] = df["company_id"].apply(normalize_ticker)
    df = filter_orphans(df, valid_ids)
    df = df[["peer_group_name", "company_id", "is_benchmark"]]
    df.to_sql("peer_groups", conn, if_exists="append", index=False)
    print(f"peer_groups: {len(df)} rows loaded")


# ---------- Audit ----------

def generate_load_audit(conn):
    tables = ["companies", "profitandloss", "balancesheet", "cashflow", "documents",
              "analysis", "prosandcons", "sectors", "stock_prices", "market_cap",
              "financial_ratios_source", "financial_ratios", "peer_groups"]
    rows = []
    for t in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {t};").fetchone()[0]
        rows.append({"table": t, "rows_loaded": count})
    out = pd.DataFrame(rows)
    os.makedirs("output", exist_ok=True)
    out.to_csv("output/load_audit.csv", index=False)
    print("\n=== load_audit.csv ===")
    print(out.to_string(index=False))


def main():
    os.makedirs("data", exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)  # rebuild clean each run — safe since source Excel is read-only

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    build_schema(conn)

    valid_ids = load_companies(conn)

    pl_cols = ["company_id", "year", "sales", "expenses", "operating_profit",
               "opm_percentage", "other_income", "interest", "depreciation",
               "profit_before_tax", "tax_percentage", "net_profit", "eps", "dividend_payout"]
    load_timeseries_table(conn, "profitandloss", "profitandloss", pl_cols, valid_ids)

    bs_cols = ["company_id", "year", "equity_capital", "reserves", "borrowings",
               "other_liabilities", "total_liabilities", "fixed_assets", "cwip",
               "investments", "other_asset", "total_assets"]
    load_timeseries_table(conn, "balancesheet", "balancesheet", bs_cols, valid_ids)

    cf_cols = ["company_id", "year", "operating_activity", "investing_activity",
               "financing_activity", "net_cash_flow"]
    load_timeseries_table(conn, "cashflow", "cashflow", cf_cols, valid_ids)

    load_documents(conn, valid_ids)
    load_analysis(conn, valid_ids)
    load_prosandcons(conn, valid_ids)
    load_sectors(conn, valid_ids)
    load_stock_prices(conn, valid_ids)
    load_market_cap(conn, valid_ids)
    load_financial_ratios_source(conn, valid_ids)
    load_peer_groups(conn, valid_ids)

    conn.commit()

    # Verification, right here, not left to hope
    fk_errors = conn.execute("PRAGMA foreign_key_check;").fetchall()
    company_count = conn.execute("SELECT COUNT(*) FROM companies;").fetchone()[0]

    print(f"\nSELECT COUNT(*) FROM companies -> {company_count}")
    print(f"PRAGMA foreign_key_check -> {len(fk_errors)} violations")
    if fk_errors:
        print("  DETAIL:", fk_errors[:5])

    generate_load_audit(conn)

    conn.close()
    print(f"\n{DB_PATH} built successfully." if not fk_errors and company_count == 92
          else "\nSomething is off — check counts above before proceeding.")


if __name__ == "__main__":
    main()