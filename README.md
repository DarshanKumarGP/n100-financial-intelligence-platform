# N100 Financial Intelligence Platform — Sprint 1: Data Foundation

**Status:** Sprint 1 complete · **Sprint:** Days 1–7 of 45
**Author:** Darshan Kumar · Bluestock Fintech Internship

## Overview

This project builds a unified SQLite data warehouse (`nifty100.db`) from
12 raw Excel files covering 92 Nifty 100 companies' financial statements,
sector mappings, and market data. Sprint 1 covers ingestion, validation,
and loading — the foundation every later analytics module (Ratio Engine,
Screener, Dashboard, API) will build on.

## Quick Start

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd n100_financial_intelligence

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash
# or: source .venv/bin/activate    # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.template .env
# edit .env if needed (default paths should work as-is)

# 5. Place source data
# Copy the 7 core .xlsx files into data/raw/
# Copy the 5 supplementary .xlsx files into data/supporting/

# 6. Run the full pipeline
python db/loader.py

# 7. Run the test suite
pytest tests/ --html=reports/pytest_report.html --self-contained-html -v
```

Expected result: `data/nifty100.db` built with 12 tables, `PRAGMA
foreign_key_check` returns 0 violations, 48/48 tests pass.

## Project Structure

n100_financial_intelligence/
├── data/
│ ├── raw/ 7 core Excel files (read-only source data)
│ ├── supporting/ 5 supplementary Excel files
│ └── nifty100.db Generated SQLite database (not committed)
├── db/
│ ├── schema.sql 12-table schema, PK/FK constraints
│ └── loader.py Builds nifty100.db from all 12 source files
├── src/etl/
│ ├── normaliser.py normalize_year(), normalize_ticker()
│ └── validator.py 16 Data Quality rules (DQ-01 to DQ-16)
├── tests/
│ ├── etl/ 40 tests — year/ticker normalisation
│ └── dq/ 8 tests — DQ rule logic
├── notebooks/
│ ├── exploratory_queries.sql 10 SQL queries against the loaded DB
│ ├── day6_qa_review.md Manual QA on 5 sample companies
│ └── sprint1_retro.md Full sprint retrospective + findings
├── output/
│ ├── load_audit.csv Per-table row counts
│ └── validation_failures.csv All DQ rule violations, with severity
├── reports/
│ └── pytest_report.html Full test suite HTML report
├── dev_notes/diagnostics/ Investigation scripts (see its README)
├── docs/
│ └── Nifty100_Project_Document_FINAL.pdf Master spec
├── requirements.txt
├── .env.template
├── Makefile
└── README.md


## What's implemented (Sprint 1 exit criteria)

- [x] `SELECT COUNT(*) FROM companies` = 92
- [x] `PRAGMA foreign_key_check` = 0 rows
- [x] `output/load_audit.csv` shows zero CRITICAL rejections
- [x] 48/48 unit tests passing (40 normaliser + 8 DQ rules)
- [x] 5 companies manually reviewed and documented
- [x] 10 exploratory queries run against the final database

## Known data findings (see `notebooks/sprint1_retro.md` for full detail)

- **TTM** (Trailing Twelve Months) rows are recognized as a valid
  category, not forced into a fake fiscal year.
- **8 companies** referenced in P&L/BS/CF have no matching entry in
  `companies.xlsx` — correctly excluded via FK enforcement, pending a
  team decision on whether to add them to the master file.
- **AGTL → ATGL**: a confirmed ticker typo in `cashflow.xlsx`, corrected
  via an explicit, documented mapping rather than silently dropped.
- **`opm_percentage`** is unreliable for 21 companies (mainly the
  Financials sector, where OPM isn't a meaningful metric) — Sprint 2's
  Ratio Engine should compute OPM directly rather than trust this field.
- **SBIN** has zero rows in `balancesheet.xlsx` — an isolated source-data
  gap, confirmed not to affect any other bank in the dataset.

## Tech Stack

pandas, openpyxl, SQLite3, pytest, pytest-html

## Running individual components

```bash
python db/loader.py                                  # full pipeline
pytest tests/etl/test_normalise.py -v                 # normaliser tests only
pytest tests/dq/test_rules.py -v                       # DQ rule tests only
python -c "..." # see notebooks/exploratory_queries.sql for ad-hoc queries
```

## Next: Sprint 2 — Financial Ratio Engine (Days 8–14)

Builds 50+ KPIs per company-year into a `financial_ratios` table.
Carries forward the OPM and SBIN findings above as known constraints.