"""
Day 3 — Schema & Data Quality Validator
Implements DQ-01 through DQ-16 (spec Section 14).
Each rule function returns a list of violation dicts:
    {table, company_id, year, field, issue, severity}
"""

import os
import sys
import pandas as pd
import requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normaliser import normalize_ticker, normalize_year

CORE_FILES = {
    "companies": "data/raw/companies.xlsx",
    "profitandloss": "data/raw/profitandloss.xlsx",
    "balancesheet": "data/raw/balancesheet.xlsx",
    "cashflow": "data/raw/cashflow.xlsx",
    "documents": "data/raw/documents.xlsx",
}

OUTPUT_PATH = "output/validation_failures.csv"


def _v(table, company_id, year, field, issue, severity):
    """Small helper so every violation record has the same shape."""
    return {
        "table": table,
        "company_id": company_id,
        "year": year,
        "field": field,
        "issue": issue,
        "severity": severity,
    }


def load_and_normalize(path, name):
    df = pd.read_excel(path, header=1)
    if "company_id" in df.columns:
        df["company_id"] = df["company_id"].apply(normalize_ticker)
    if "id" in df.columns and name == "companies":
        df["id"] = df["id"].apply(normalize_ticker)
    if "year" in df.columns:
        df["year_raw"] = df["year"]
        df["year"] = df["year"].apply(normalize_year)
    return df


# ---------- CRITICAL rules ----------

def dq01_company_pk_uniqueness(companies):
    violations = []
    dupes = companies[companies["id"].duplicated(keep=False)]
    for _, row in dupes.iterrows():
        violations.append(_v("companies", row["id"], None, "id",
                              "Duplicate company id — PK uniqueness violated", "CRITICAL"))
    return violations


def dq02_annual_pk_uniqueness(df, table_name):
    violations = []
    dupes = df[df.duplicated(subset=["company_id", "year"], keep=False)]
    for _, row in dupes.iterrows():
        violations.append(_v(table_name, row["company_id"], row["year"],
                              "company_id+year", "Duplicate (company_id, year) pair", "CRITICAL"))
    return violations


def dq03_fk_integrity(df, table_name, valid_ids):
    violations = []
    orphans = df[~df["company_id"].isin(valid_ids)]
    for _, row in orphans.iterrows():
        violations.append(_v(table_name, row["company_id"], row.get("year"),
                              "company_id", "Orphan row — no matching company", "CRITICAL"))
    return violations


def dq07_year_format(df, table_name):
    violations = []
    bad = df[df["year"] == "PARSE_ERROR"]
    for _, row in bad.iterrows():
        violations.append(_v(table_name, row["company_id"], row["year_raw"],
                              "year", f"Unparseable year value: {row['year_raw']!r}", "CRITICAL"))
    return violations


def dq08_ticker_format(df, table_name, id_col="company_id"):
    violations = []
    bad = df[(df[id_col].str.len() < 2) | (df[id_col].str.len() > 12) | df[id_col].isna()]
    for _, row in bad.iterrows():
        violations.append(_v(table_name, row[id_col], row.get("year"),
                              id_col, "Ticker length out of 2-12 char range", "CRITICAL"))
    return violations


# ---------- WARNING rules ----------

def dq04_balance_sheet_balance(bs):
    violations = []
    diff = (bs["total_assets"] - bs["total_liabilities"]).abs() / bs["total_assets"].replace(0, pd.NA)
    bad = bs[diff >= 0.01]
    for _, row in bad.iterrows():
        violations.append(_v("balancesheet", row["company_id"], row["year"],
                              "total_assets/total_liabilities",
                              "Assets and liabilities differ by >=1%", "WARNING"))
    return violations


def dq05_opm_cross_check(pl):
    violations = []
    computed_opm = (pl["operating_profit"] / pl["sales"].replace(0, pd.NA)) * 100
    diff = (pl["opm_percentage"] - computed_opm).abs()
    bad = pl[diff > 1.0]
    for _, row in bad.iterrows():
        violations.append(_v("profitandloss", row["company_id"], row["year"],
                              "opm_percentage", "OPM differs from computed value by >1%", "WARNING"))
    return violations


def dq06_positive_sales(pl):
    violations = []
    bad = pl[pl["sales"] <= 0]
    for _, row in bad.iterrows():
        violations.append(_v("profitandloss", row["company_id"], row["year"],
                              "sales", "Sales is zero or negative", "WARNING"))
    return violations


def dq09_net_cash_check(cf):
    violations = []
    computed = cf["operating_activity"] + cf["investing_activity"] + cf["financing_activity"]
    diff = (cf["net_cash_flow"] - computed).abs()
    bad = cf[diff > 10]
    for _, row in bad.iterrows():
        violations.append(_v("cashflow", row["company_id"], row["year"],
                              "net_cash_flow", "net_cash_flow does not match CFO+CFI+CFF (±10 Cr)", "WARNING"))
    return violations


def dq10_non_negative_fixed_assets(bs):
    violations = []
    bad = bs[bs["fixed_assets"] < 0]
    for _, row in bad.iterrows():
        violations.append(_v("balancesheet", row["company_id"], row["year"],
                              "fixed_assets", "Negative fixed_assets — coerced to 0", "WARNING"))
    return violations


def dq11_tax_rate_range(pl):
    violations = []
    bad = pl[(pl["tax_percentage"] < 0) | (pl["tax_percentage"] > 60)]
    for _, row in bad.iterrows():
        violations.append(_v("profitandloss", row["company_id"], row["year"],
                              "tax_percentage", "Tax rate outside 0-60% range", "WARNING"))
    return violations


def dq12_dividend_payout_cap(pl):
    violations = []
    bad = pl[pl["dividend_payout"] > 200]
    for _, row in bad.iterrows():
        violations.append(_v("profitandloss", row["company_id"], row["year"],
                              "dividend_payout", "Dividend payout exceeds 200%", "WARNING"))
    return violations


def dq13_url_validity(documents, sample_size=None):
    """
    Network check — slow (1,585 URLs). Set sample_size to test a subset
    while developing; run with sample_size=None for the real Day 5 full load.
    """
    violations = []
    rows = documents if sample_size is None else documents.sample(min(sample_size, len(documents)))
    for _, row in rows.iterrows():
        url = row.get("Annual_Report")
        if not isinstance(url, str) or not url.startswith("http"):
            continue
        try:
            resp = requests.head(url, timeout=5, allow_redirects=True)
            if resp.status_code != 200:
                violations.append(_v("documents", row["company_id"], row.get("Year"),
                                      "Annual_Report", f"URL returned {resp.status_code}", "WARNING"))
        except requests.RequestException as e:
            violations.append(_v("documents", row["company_id"], row.get("Year"),
                                  "Annual_Report", f"URL request failed: {e}", "WARNING"))
    return violations


def dq14_eps_sign_consistency(pl):
    violations = []
    bad = pl[(pl["net_profit"] > 0) & (pl["eps"] <= 0)]
    for _, row in bad.iterrows():
        violations.append(_v("profitandloss", row["company_id"], row["year"],
                              "eps", "net_profit positive but eps not positive", "WARNING"))
    return violations


def dq15_strict_balance_info(bs):
    mismatched = (bs["total_assets"] != bs["total_liabilities"]).sum()
    return [_v("balancesheet", None, None, "total_assets/total_liabilities",
                f"{mismatched} rows not strictly equal (informational only)", "INFO")]


def dq16_coverage_check(pl, bs, cf):
    violations = []
    years_per_company = {}
    for df, table in [(pl, "profitandloss"), (bs, "balancesheet"), (cf, "cashflow")]:
        counts = df.groupby("company_id")["year"].nunique()
        for cid, n in counts.items():
            years_per_company.setdefault(cid, {})[table] = n
    for cid, counts in years_per_company.items():
        max_years = max(counts.values())
        if max_years < 5:
            violations.append(_v("multiple", cid, None, "year_coverage",
                                  f"Only {max_years} years of history available", "WARNING"))
    return violations


# ---------- orchestration ----------

def run_all_rules(check_urls=False):
    companies = load_and_normalize(CORE_FILES["companies"], "companies")
    pl = load_and_normalize(CORE_FILES["profitandloss"], "profitandloss")
    bs = load_and_normalize(CORE_FILES["balancesheet"], "balancesheet")
    cf = load_and_normalize(CORE_FILES["cashflow"], "cashflow")
    documents = load_and_normalize(CORE_FILES["documents"], "documents")

    valid_ids = set(companies["id"])
    all_violations = []

    all_violations += dq01_company_pk_uniqueness(companies)
    for df, name in [(pl, "profitandloss"), (bs, "balancesheet"), (cf, "cashflow")]:
        all_violations += dq02_annual_pk_uniqueness(df, name)
        all_violations += dq03_fk_integrity(df, name, valid_ids)
        all_violations += dq07_year_format(df, name)
        all_violations += dq08_ticker_format(df, name)

    all_violations += dq04_balance_sheet_balance(bs)
    all_violations += dq05_opm_cross_check(pl)
    all_violations += dq06_positive_sales(pl)
    all_violations += dq09_net_cash_check(cf)
    all_violations += dq10_non_negative_fixed_assets(bs)
    all_violations += dq11_tax_rate_range(pl)
    all_violations += dq12_dividend_payout_cap(pl)
    if check_urls:
        all_violations += dq13_url_validity(documents, sample_size=50)  # sampled for speed
    all_violations += dq14_eps_sign_consistency(pl)
    all_violations += dq15_strict_balance_info(bs)
    all_violations += dq16_coverage_check(pl, bs, cf)

    return all_violations


def main():
    violations = run_all_rules(check_urls=False)  # flip to True once you're ready for the slow URL pass
    os.makedirs("output", exist_ok=True)
    out_df = pd.DataFrame(violations)
    out_df.to_csv(OUTPUT_PATH, index=False)

    print(f"\nValidation complete. {len(violations)} total findings written to {OUTPUT_PATH}\n")
    if not out_df.empty:
        print("By severity:")
        print(out_df["severity"].value_counts().to_string())
        critical = out_df[out_df["severity"] == "CRITICAL"]
        print(f"\nCRITICAL count: {len(critical)}  {'(load should HALT)' if len(critical) else '(clear to proceed)'}")


if __name__ == "__main__":
    main()