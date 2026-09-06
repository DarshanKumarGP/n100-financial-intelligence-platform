# N100 Financial Intelligence Platform

**Status:** Sprint 3 complete · **Sprint:** Days 1–21 of 45
**Author:** Darshan Kumar · Bluestock Fintech Internship

## Overview

This project builds a unified SQLite data warehouse and analytics engine
for 92 Nifty 100 companies. Sprint 1 (Days 1–7) built the data foundation
— ingestion, validation, and loading of 12 raw Excel files into
`nifty100.db`. Sprint 2 (Days 8–14) built the Financial Ratio Engine —
30+ computed KPIs per company-year, CAGR growth metrics, cash flow
intelligence, and a capital allocation classifier. Sprint 3 (Days 15–21)
built the Investment Screener (6 preset filters, custom threshold
support) and Peer Comparison Engine (percentile rankings across 11 peer
groups, radar charts, colour-coded Excel reports).

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

# 8. Run the Screener & Peer Comparison Engine (Sprint 3)
python src/screener/compute_composite_scores.py
python src/screener/export_screener_output.py
python src/analytics/peer.py
python src/reports/generate_radar_charts.py
python src/reports/generate_peer_comparison.py

# 9. Run the full test suite
pytest tests/ --html=reports/pytest_report.html --self-contained-html -v
```

Expected result: `data/nifty100.db` built with 15 tables, `PRAGMA
foreign_key_check` returns 0 violations, `financial_ratios` has 1,070
rows with sector-relative composite scores, `peer_percentiles` has 560
rows, 92 radar charts generated, 109/109 unit tests pass.

## Project Structure
```
n100_financial_intelligence/
├── data/
│ ├── raw/ 7 core Excel files (read-only source data)
│ ├── supporting/ 5 supplementary Excel files
│ └── nifty100.db Generated SQLite database (not committed)
├── db/
│ ├── schema.sql 15-table schema, PK/FK constraints
│ └── loader.py Builds nifty100.db from all 12 source files
├── src/
│ ├── etl/
│ │ ├── normaliser.py normalize_year(), normalize_ticker()
│ │ └── validator.py 16 Data Quality rules (DQ-01 to DQ-16)
│ ├── analytics/
│ │ ├── ratios.py Profitability, leverage, efficiency ratios
│ │ ├── cagr.py CAGR engine — 6 edge cases, TTM-safe
│ │ ├── cashflow_kpis.py FCF, CFO quality, CapEx intensity, 8-pattern classifier
│ │ ├── populate_ratios.py Populates the financial_ratios table
│ │ ├── generate_capital_allocation.py Generates capital_allocation.csv
│ │ ├── generate_edge_case_log.py Cross-checks computed vs source ROCE/ROE
│ │ └── peer.py Peer percentile rankings (11 groups, 10 metrics)
│ ├── screener/
│ │ ├── engine.py Filter engine — 15 metrics, sector exemptions
│ │ ├── presets.py 6 preset screeners
│ │ ├── compute_composite_scores.py Sector-relative composite quality score
│ │ └── export_screener_output.py Generates screener_output.xlsx
│ └── reports/
│ ├── generate_radar_charts.py 92 radar/bar charts
│ └── generate_peer_comparison.py Generates peer_comparison.xlsx
├── config/
│ └── screener_config.yaml 15 filterable metrics, analyst-editable
├── tests/
│ ├── etl/ 40 tests — year/ticker normalisation
│ ├── dq/ 17 tests — all 16 DQ rules (DQ-13 excluded, network-dependent)
│ ├── kpi/ 44 tests — ratios, CAGR, cash flow KPIs
│ └── screener/ 8 tests — filter engine, peer percentiles
├── notebooks/
│ ├── exploratory_queries.sql 10 SQL queries against the loaded DB (Sprint 1)
│ ├── day6_qa_review.md Manual QA on 5 sample companies (Sprint 1)
│ ├── day12_spot_check.md Manual ROE/CAGR verification, 3 companies (Sprint 2)
│ ├── sprint1_retro.md Sprint 1 retrospective + findings
│ ├── sprint2_retro.md Sprint 2 retrospective + findings
│ └── sprint3_retro.md Sprint 3 retrospective + findings
├── output/
│ ├── load_audit.csv Per-table row counts (Sprint 1)
│ ├── validation_failures.csv All DQ rule violations, with severity (Sprint 1)
│ ├── capital_allocation.csv 8-pattern label per company-year (Sprint 2)
│ ├── ratio_edge_cases.log 54 categorized ROCE/ROE anomalies (Sprint 2)
│ ├── screener_output.xlsx 6 preset sheets + Notes, colour-coded (Sprint 3)
│ └── peer_comparison.xlsx 11 peer group sheets, colour-coded (Sprint 3)
├── reports/
│ ├── pytest_report.html Full test suite HTML report (not committed)
│ └── radar_charts/ 92 PNG charts, one per company (Sprint 3)
├── dev_notes/diagnostics/ Investigation scripts (see its README)
├── docs/
│ └── Nifty100_Project_Document_FINAL.pdf Master spec
├── requirements.txt
├── .env.template
├── Makefile
└── README.md
```


## What's implemented

### Sprint 1 — Data Foundation (Days 1–7)

- [x] `SELECT COUNT(*) FROM companies` = 92
- [x] `PRAGMA foreign_key_check` = 0 rows
- [x] `output/load_audit.csv` shows zero CRITICAL rejections
- [x] 48/48 ETL unit tests passing (40 normaliser + 8 DQ rules)
- [x] 5 companies manually reviewed and documented
- [x] 10 exploratory queries run against the final database

### Sprint 2 — Financial Ratio Engine (Days 8–14)

- [x] `financial_ratios` table populated: 1,070 rows (non-TTM company-years)
- [x] 30+ computed KPI columns: profitability, leverage, efficiency, CAGR (3/5/10yr), cash flow quality, composite quality score
- [x] 44/44 KPI unit tests passing (exceeds spec's 20-test minimum)
- [x] Manual spot-check: ROE and 5yr Revenue CAGR for 3 companies match hand-calculation within 0.1%
- [x] `output/capital_allocation.csv` — 8-pattern classification, 1,063 rows
- [x] `output/ratio_edge_cases.log` — 54 anomalies, every entry with a genuine investigated explanation

### Sprint 3 — Screener & Peer Comparison Engine (Days 15–21)

- [x] 6 preset screeners implemented — 5 of 6 return 5-50 companies naturally;
      Value Pick returns 2 (investigated, confirmed genuine — see note below)
- [x] `composite_quality_score` recomputed with full spec formula (sector-relative,
      P10/P90 winsorized across 10 sectors)
- [x] `output/screener_output.xlsx` — 6 preset sheets + explanatory Notes sheet, colour-coded
- [x] `peer_percentiles` table — 560 rows, 56 companies × 10 metrics, all 11 peer groups
- [x] 36 ungrouped companies correctly handled (no error, explicit "no peer group" status)
- [x] Peer ranking correctness verified in both IT Services and FMCG groups —
      highest-ROE company also shows highest percentile rank in each
- [x] 92 radar/bar charts generated — 56 with peer group overlay, 36 standalone
- [x] `output/peer_comparison.xlsx` — 11 sheets, colour-coded, benchmark-highlighted, median summary rows
- [x] DQ test coverage closed: 17 tests now covering 15 of 16 rules (up from 8/7)
- [x] 109/109 total unit tests passing project-wide

**Row count note (Sprint 2, still applies):** `financial_ratios` has
1,070 rows against the spec's "≥1,100" target — a deliberate, correct
exclusion of TTM rows. See `notebooks/sprint2_retro.md`.

**Value Pick note (Sprint 3):** Returns 2 companies against the spec's
5-50 expected range. Investigated: the `market_cap` join is confirmed
clean (92/92 companies have data). P/B<3 (10 pass) and P/E<20 (14 pass)
are the binding constraints, not D/E or Dividend Yield (69/72 pass).
Reflects genuine current valuation levels in the Nifty 100 — kept as
specified rather than loosened. See `notebooks/sprint3_retro.md`.

## Known data findings

### From Sprint 1 (see `notebooks/sprint1_retro.md`)

- **TTM** rows recognized as a valid category, not forced into a fake fiscal year.
- **8 companies** referenced in P&L/BS/CF have no matching entry in `companies.xlsx` — pending a team decision.
- **AGTL → ATGL**: confirmed ticker typo in `cashflow.xlsx`, corrected via documented mapping.
- **`opm_percentage`** unreliable for 21 companies (mainly Financials) — Ratio Engine computes OPM directly.
- **SBIN** has zero rows in `balancesheet.xlsx` — an isolated source-data gap.

### From Sprint 2 (see `notebooks/sprint2_retro.md`)

- **`financial_ratios` vs `financial_ratios_source`**: source table renamed and preserved for display/cross-check only.
- **Small standalone equity base outliers** (HAL, BEL, INDIGO): `net_profit/equity_base > 5` guard required across all scoring modules.
- **`operating_profit` reliability question** for CIPLA and COALINDIA — flagged for further scrutiny.
- **Capital-employed definition gap** — ~15 companies show consistent ROCE differences vs source data.

### From Sprint 3 (see `notebooks/sprint3_retro.md`)

- **Debt-Free Blue Chip's exact `D/E == 0` filter was a real bug** — fixed
  to `D/E < 0.01` after finding economically debt-free companies
  (BAJAJHLDNG, BOSCHLTD, ITC, MARUTI) compute tiny non-zero D/E via float division.
- **Value Pick's narrow result confirmed genuine**, not a bug — see note above.
- **Sector exemption confirmed correct**: Sprint 3's screener includes 13
  Financials-sector companies that Day 14's earlier, simpler preview had
  wrongly excluded — a fix, not a regression.
- **Excel colour-coding bug** (Day 20): traced to reading percentile
  values back from written cells instead of the source DataFrame; fixed
  by colouring directly from the DataFrame during the write pass.
- **SBIN's known NULL balance-sheet data confirmed to render gracefully**
  in `peer_comparison.xlsx` — blank BS-dependent cells, correctly
  gold-highlighted as the Public Sector Banks benchmark.

## Tech Stack

pandas, openpyxl, SQLite3, pytest, pytest-html, PyYAML, matplotlib

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

# Sprint 3
python src/screener/compute_composite_scores.py          # recompute composite scores
python src/screener/export_screener_output.py             # screener_output.xlsx
python src/analytics/peer.py                                # peer_percentiles table
python src/reports/generate_radar_charts.py                  # 92 radar/bar charts
python src/reports/generate_peer_comparison.py                # peer_comparison.xlsx
pytest tests/screener/ -v                                       # screener + peer tests

# Full suite
pytest tests/ -v
```

