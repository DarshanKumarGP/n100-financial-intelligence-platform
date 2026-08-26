# N100 Financial Intelligence Platform

**Status:** Sprint 2 complete · **Sprint:** Days 1–14 of 45
**Author:** Darshan Kumar · Bluestock Fintech Internship

## Overview

This project builds a unified SQLite data warehouse and analytics engine
for 92 Nifty 100 companies. Sprint 1 (Days 1–7) built the data foundation
— ingestion, validation, and loading of 12 raw Excel files into
`nifty100.db`. Sprint 2 (Days 8–14) built the Financial Ratio Engine —
30+ computed KPIs per company-year, CAGR growth metrics, cash flow
intelligence, and a capital allocation classifier — all written to a
`financial_ratios` table that later modules (Screener, Health Score,
Dashboard, API) will query.

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

# 6. Run the full ETL pipeline (Sprint 1)
python db/loader.py

# 7. Populate the Financial Ratio Engine (Sprint 2)
python src/analytics/populate_ratios.py
python src/analytics/generate_capital_allocation.py
python src/analytics/generate_edge_case_log.py

# 8. Run the full test suite
pytest tests/ --html=reports/pytest_report.html --self-contained-html -v
```

Expected result: `data/nifty100.db` built with 14 tables (12 from Sprint
1 + `financial_ratios_source` renamed + `financial_ratios` populated),
`PRAGMA foreign_key_check` returns 0 violations, `financial_ratios` has
1,070 rows, 92/92 unit tests pass.

## Project Structure
n100_financial_intelligence/
├── data/
│ ├── raw/ 7 core Excel files (read-only source data)
│ ├── supporting/ 5 supplementary Excel files
│ └── nifty100.db Generated SQLite database (not committed)
├── db/
│ ├── schema.sql 14-table schema, PK/FK constraints
│ └── loader.py Builds nifty100.db from all 12 source files
├── src/
│ ├── etl/
│ │ ├── normaliser.py normalize_year(), normalize_ticker()
│ │ └── validator.py 16 Data Quality rules (DQ-01 to DQ-16)
│ └── analytics/
│ ├── ratios.py Profitability, leverage, efficiency ratios
│ ├── cagr.py CAGR engine — 6 edge cases, TTM-safe
│ ├── cashflow_kpis.py FCF, CFO quality, CapEx intensity, 8-pattern classifier
│ ├── populate_ratios.py Populates the financial_ratios table
│ ├── generate_capital_allocation.py Generates capital_allocation.csv
│ └── generate_edge_case_log.py Cross-checks computed vs source ROCE/ROE
├── tests/
│ ├── etl/ 40 tests — year/ticker normalisation
│ ├── dq/ 8 tests — DQ rule logic
│ └── kpi/ 44 tests — ratios, CAGR, cash flow KPIs
├── notebooks/
│ ├── exploratory_queries.sql 10 SQL queries against the loaded DB (Sprint 1)
│ ├── day6_qa_review.md Manual QA on 5 sample companies (Sprint 1)
│ ├── day12_spot_check.md Manual ROE/CAGR verification, 3 companies (Sprint 2)
│ ├── sprint1_retro.md Sprint 1 retrospective + findings
│ └── sprint2_retro.md Sprint 2 retrospective + findings
├── output/
│ ├── load_audit.csv Per-table row counts (Sprint 1)
│ ├── validation_failures.csv All DQ rule violations, with severity (Sprint 1)
│ ├── capital_allocation.csv 8-pattern label per company-year (Sprint 2)
│ └── ratio_edge_cases.log 54 categorized ROCE/ROE anomalies (Sprint 2)
├── reports/
│ └── pytest_report.html Full test suite HTML report (not committed)
├── dev_notes/diagnostics/ Investigation scripts (see its README)
├── docs/
│ └── Nifty100_Project_Document_FINAL.pdf Master spec
├── requirements.txt
├── .env.template
├── Makefile
└── README.md


## What's implemented

### Sprint 1 — Data Foundation (Days 1–7)

- [x] `SELECT COUNT(*) FROM companies` = 92
- [x] `PRAGMA foreign_key_check` = 0 rows
- [x] `output/load_audit.csv` shows zero CRITICAL rejections
- [x] 48/48 ETL unit tests passing (40 normaliser + 8 DQ rules)
- [x] 5 companies manually reviewed and documented
- [x] 10 exploratory queries run against the final database

### Sprint 2 — Financial Ratio Engine (Days 8–14)

- [x] `financial_ratios` table populated: 1,070 rows (non-TTM company-years — see note below)
- [x] 30+ computed KPI columns: profitability, leverage, efficiency, CAGR (3/5/10yr), cash flow quality, composite quality score
- [x] 44/44 KPI unit tests passing (exceeds spec's 20-test minimum)
- [x] Manual spot-check: ROE and 5yr Revenue CAGR for 3 companies (TCS, SUNPHARMA, HDFCBANK) match hand-calculation within 0.1%
- [x] `output/capital_allocation.csv` — 8-pattern classification, 1,063 rows
- [x] `output/ratio_edge_cases.log` — 54 anomalies, every entry with a genuine investigated explanation
- [x] Screener preview (ROE>15% AND D/E<1) validated: 35 companies, outlier-guarded, business-sensible results

**Row count note:** `financial_ratios` has 1,070 rows against the spec's
"≥1,100" target. This is a deliberate, correct exclusion of TTM rows —
TTM is a rolling 12-month window, not a fixed fiscal year-end, and
including it would be incoherent with a `year` column representing
fixed periods. Every real fiscal year of data is represented; see
`notebooks/sprint2_retro.md` for full reasoning.

## Known data findings

### From Sprint 1 (see `notebooks/sprint1_retro.md`)

- **TTM** (Trailing Twelve Months) rows are recognized as a valid
  category, not forced into a fake fiscal year.
- **8 companies** referenced in P&L/BS/CF have no matching entry in
  `companies.xlsx` — correctly excluded via FK enforcement, pending a
  team decision on whether to add them to the master file.
- **AGTL → ATGL**: a confirmed ticker typo in `cashflow.xlsx`, corrected
  via an explicit, documented mapping rather than silently dropped.
- **`opm_percentage`** is unreliable for 21 companies (mainly the
  Financials sector) — the Ratio Engine computes OPM directly instead.
- **SBIN** has zero rows in `balancesheet.xlsx` — an isolated source-data
  gap; SBIN's balance-sheet-dependent ratios are correctly NULL
  throughout `financial_ratios`.

### From Sprint 2 (see `notebooks/sprint2_retro.md`)

- **`financial_ratios` vs `financial_ratios_source`**: the Day-5-loaded
  source table was renamed to `financial_ratios_source` (display/
  cross-check only); `financial_ratios` is our own computed, authoritative
  table for all analytics.
- **Small standalone equity base outliers** (HAL, BEL, INDIGO): these
  companies show net_profit at 9–47x their equity+reserves, producing
  mathematically correct but analytically meaningless extreme ROE/ROCE
  values (e.g. BEL: 4744% ROE). A `net_profit/equity_base > 5` guard
  reliably identifies these cases — required for Sprint 3's Screener
  and Health Score modules.
- **`operating_profit` reliability question** for CIPLA and COALINDIA —
  both show an unusually large gap between operating_profit and
  net_profit, driving their ROCE mismatch vs source data. Flagged for
  further scrutiny before use in scoring.
- **Capital-employed definition gap** — roughly 15 companies show
  consistent 5–15 percentage point ROCE differences vs source data,
  most plausibly from a differing capital-employed formula definition.

## Tech Stack

pandas, openpyxl, SQLite3, pytest, pytest-html

## Running individual components

```bash
# Sprint 1
python db/loader.py                                    # full ETL pipeline
pytest tests/etl/test_normalise.py -v                   # normaliser tests only
pytest tests/dq/test_rules.py -v                        # DQ rule tests only

# Sprint 2
python src/analytics/populate_ratios.py                 # populate financial_ratios
python src/analytics/generate_capital_allocation.py     # capital_allocation.csv
python src/analytics/generate_edge_case_log.py          # ratio_edge_cases.log
pytest tests/kpi/ -v                                     # all KPI tests

# Ad-hoc queries
# See notebooks/exploratory_queries.sql (Sprint 1)
```

## Next: Sprint 3 — Screener, Health Score & Sector Analytics (Days 15–21)

Builds the Investment Screener (6 preset filters), Financial Health
Score (0–100 composite), and Sector Analytics modules. Carries forward
from Sprint 2: the outlier guard requirement for extreme-ROE companies,
the CIPLA/COALINDIA operating_profit question, and Sprint 1's SBIN /
missing-companies open items.