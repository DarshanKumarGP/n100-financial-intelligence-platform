# N100 Financial Intelligence Platform

**Status:** All 6 sprints complete · **Sprint:** Days 1–45 of 45
**Author:** Darshan Kumar · Bluestock Fintech Internship

## Overview

This project builds a unified SQLite data warehouse and analytics engine
for 92 Nifty 100 companies. Sprint 1 (Days 1–7) built the data foundation.
Sprint 2 (Days 8–14) built the Financial Ratio Engine. Sprint 3 (Days
15–21) built the Investment Screener and Peer Comparison Engine. Sprint 4
(Days 22–28) built an 8-screen Streamlit dashboard and the Valuation
module. Sprint 5 (Days 29–35) built the NLP intelligence layer — auto
pros/cons generation, cash flow intelligence, capital allocation
reporting — and the automated PDF report generator: company tearsheets,
sector reports, and a portfolio summary. Sprint 6 (Days 36–45) added
KMeans company clustering, a 16-endpoint FastAPI REST server, a full
project-wide test suite, complete documentation, and final acceptance
sign-off. The platform is now complete end to end: ingest → analytics →
dashboard → API → reports, with no dependency on any third-party paid
service.

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

# 9. Run the Valuation module (Sprint 4)
python src/analytics/valuation.py

# 10. Launch the dashboard (Sprint 4)
streamlit run src/dashboard/app.py

# 11. Run the NLP intelligence layer (Sprint 5)
python src/nlp/parser.py
python src/nlp/pros_cons_generator.py
python src/analytics/cashflow_intelligence.py
python src/analytics/capital_allocation_report.py

# 12. Generate all PDF reports (Sprint 5)
python src/reports/generate_tearsheets_batch.py
python src/reports/sector_report.py
python src/reports/portfolio_summary.py

# 13. Run KMeans clustering & cluster profiling (Sprint 6)
python src/analytics/clustering.py
python src/analytics/cluster_profiling.py

# 14. Launch the API server (Sprint 6)
uvicorn src.api.main:app --port 8000
# Interactive docs: http://localhost:8000/docs

# 15. Run the full test suite
pytest tests/ --html=reports/pytest_report.html --self-contained-html -v

# 16. (Optional) Run performance checks and rebuild the analyst guide / archive
python scripts/perf/load_test_screener.py          # requires uvicorn running
python scripts/perf/dashboard_load_time.py
python scripts/archive/build_final_deliverables.py
```

Expected result: dashboard opens at `http://localhost:8501` with 8
navigable screens; the API opens at `http://localhost:8000` with 16
endpoints under `/api/v1`; `output/pros_cons_generated.csv` covers all 92
companies with ≥1 pro and ≥1 con; `output/cashflow_intelligence.xlsx` has
92 rows; `output/cluster_labels.csv` has all 92 companies assigned to a
cluster; `reports/tearsheets/` has 91 PDFs (JIOFIN skipped — <3yr
history); `reports/sector/` has 10 PDFs; `reports/portfolio/` has one
92-page PDF; **146/146 tests pass**.

## Dashboard Screens

| Screen | What it shows |
|---|---|
| **Home** | 6 summary KPI tiles (median-based, outlier-robust), sector donut chart (10 real sectors), top 5 companies by composite quality score, year selector |
| **Company Profile** | Search by name/ticker, company card, 6 KPI tiles, Revenue/Net Profit and ROE/ROCE dual-axis charts (up to 10yr), pros/cons badges, graceful handling of missing data (e.g. SBIN) and thin history (e.g. JIOFIN) |
| **Screener** | 10 metric sliders, 6 one-click presets, live-updating results table, CSV export |
| **Peer Comparison** | Peer group selector, 8-axis radar chart (company vs peer average), full comparison table with benchmark row highlighted |
| **Trend Analysis** | Overlay up to 3 metrics over 10 years, hover tooltips show YoY % change |
| **Sector Analysis** | Bubble chart (Revenue × ROE × Market Cap, coloured by sub-sector), sector median KPI charts |
| **Capital Allocation Map** | Treemap of all 92 companies by 8 capital allocation patterns, dropdown to browse companies within a pattern |
| **Annual Reports** | Company search, clickable BSE PDF links, "Report unavailable" badge for missing links |

## REST API (Sprint 6)

Start with `uvicorn src.api.main:app --port 8000`. Interactive Swagger
docs at `localhost:8000/docs`. All 16 endpoints live under `/api/v1`:

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Server status, DB row counts, uptime |
| GET | `/companies` | List all companies; filter by sector, market cap category, search |
| GET | `/companies/{ticker}` | Full company profile + latest KPIs |
| GET | `/companies/{ticker}/pl` | P&L history (`from_year`/`to_year` params) |
| GET | `/companies/{ticker}/bs` | Balance sheet history |
| GET | `/companies/{ticker}/cashflow` | Cash flow history |
| GET | `/companies/{ticker}/ratios` | Computed KPIs per year (optional `year` param) |
| GET | `/companies/{ticker}/tearsheet` | Pre-generated tearsheet PDF (binary download) |
| GET | `/screener` | Ranked, filtered company list |
| GET | `/sectors` | All 10 real sectors with median metrics |
| GET | `/sectors/{sector}/companies` | Companies in a sector |
| GET | `/peers/{group_name}` | Peer group with percentile ranks |
| GET | `/companies/{ticker}/peers/compare` | Radar data vs. peer group + benchmark |
| GET | `/market-cap/{ticker}` | Historical P/E, P/B, EV/EBITDA, dividend yield (2019–2024) |
| GET | `/portfolio/stats` | P10–P90 percentile table across 10 core KPIs |
| GET | `/companies/{ticker}/documents` | Annual report links with URL-validity flag |

Full spec: `docs/openapi.json`. Postman collection also provided in `docs/`.

## PDF Reports

| Report | Location | Contents |
|---|---|---|
| **Company Tearsheet** | `reports/tearsheets/<TICKER>_tearsheet.pdf` | 2 pages: navy header, 6 KPI tiles, Revenue/Net Profit and ROE/ROCE charts, Balance Sheet composition, Cash Flow waterfall, auto-generated Pros/Cons, Capital Allocation badge. 91 of 92 companies (JIOFIN skipped, <3yr history). Also generate a single ticker directly: `python src/reports/tearsheet.py --ticker <TICKER>` |
| **Sector Report** | `reports/sector/<SECTOR>_report.pdf` | Sector median KPI summary + full company table (8 metrics each). 10 reports (real sector count — see *Known data findings*) |
| **Portfolio Summary** | `reports/portfolio/portfolio_summary.pdf` | One page per company, alphabetical, top 6 KPIs with UP/DOWN/FLAT trend vs prior year. 92 pages |

## Analyst Guide

`docs/analyst_guide.pdf` (10 pages) — screener usage, dashboard
navigation, PDF report generation, API curl examples, and a
troubleshooting section covering the most common issues an analyst using
the platform day-to-day is likely to hit.

## Project Structure
```
n100_financial_intelligence/
├── data/
│ ├── raw/ 7 core Excel files (read-only source data)
│ ├── supporting/ 5 supplementary Excel files
│ └── nifty100.db Generated SQLite database (not committed), 14 tables
├── db/
│ ├── schema.sql Table definitions, PK/FK constraints
│ └── loader.py Builds nifty100.db from all 12 source files
├── src/
│ ├── etl/
│ │ ├── normaliser.py normalize_year(), normalize_ticker()
│ │ └── validator.py 16 Data Quality rules (DQ-01 to DQ-16)
│ ├── analytics/
│ │ ├── ratios.py Profitability, leverage, efficiency ratios
│ │ ├── cagr.py CAGR engine — 6 edge cases, TTM-safe
│ │ ├── cashflow_kpis.py FCF, CFO quality, CapEx intensity, 8-pattern classifier,
│ │ │ distress signal + deleveraging detection (Sprint 5)
│ │ ├── populate_ratios.py Populates the financial_ratios table
│ │ ├── generate_capital_allocation.py Generates capital_allocation.csv
│ │ ├── generate_edge_case_log.py Cross-checks computed vs source ROCE/ROE
│ │ ├── cashflow_intelligence.py Generates cashflow_intelligence.xlsx, distress_alerts.csv (Sprint 5)
│ │ ├── capital_allocation_report.py Pattern distribution summary, pattern_changes.csv (Sprint 5)
│ │ ├── peer.py Peer percentile rankings (11 groups, 10 metrics)
│ │ ├── valuation.py FCF yield, sector median P/E, overvaluation flags
│ │ ├── clustering.py KMeans clustering, 5 clusters, sector-median imputation (Sprint 6)
│ │ └── cluster_profiling.py Cluster naming, correlation heatmap, outlier detection (Sprint 6)
│ ├── nlp/
│ │ ├── parser.py Regex parser for analysis.xlsx text fields (Sprint 5)
│ │ ├── cross_validate_analysis.py Parsed vs computed CAGR cross-check (Sprint 5)
│ │ └── pros_cons_generator.py 12+12 rules, 3-tier fallback system, confidence-scored (Sprint 5),
│ │ financials exemption fixes on con_06/con_11 (Sprint 6)
│ ├── screener/
│ │ ├── engine.py Filter engine — 15 metrics, sector exemptions
│ │ ├── presets.py 6 preset screeners
│ │ ├── compute_composite_scores.py Sector-relative composite quality score
│ │ └── export_screener_output.py Generates screener_output.xlsx
│ ├── reports/
│ │ ├── generate_radar_charts.py 92 radar/bar charts
│ │ ├── generate_peer_comparison.py Generates peer_comparison.xlsx
│ │ ├── tearsheet.py 2-page company tearsheet template, --ticker CLI option (Sprint 5/6)
│ │ ├── generate_tearsheets_batch.py Batch runner, all 92 companies (Sprint 5)
│ │ ├── sector_report.py One PDF per sector (Sprint 5)
│ │ └── portfolio_summary.py One-page-per-company portfolio PDF (Sprint 5)
│ ├── dashboard/
│ │ ├── app.py Streamlit entry point, sidebar navigation
│ │ ├── utils/db.py 9 cached data-loading functions, TTM-safe
│ │ └── pages/ 8 screen files (01_home.py – 08_reports.py)
│ └── api/
│ ├── main.py FastAPI app, CORS, request-logging middleware (Sprint 6)
│ └── routers/ 8 router files, 16 endpoints total (Sprint 6)
├── scripts/
│ ├── perf/ Load test + dashboard load time scripts (Sprint 6)
│ ├── acceptance/ Automated acceptance gate checks, AC-01 to AC-20 (Sprint 6)
│ ├── archive/ Final deliverables archive builder (Sprint 6)
│ └── docs/ Automated docstring insertion tool (Sprint 6)
├── config/
│ └── screener_config.yaml 15 filterable metrics, analyst-editable
├── tests/
│ ├── etl/ 51 tests — year/ticker normalisation, loader
│ ├── dq/ 17 tests — all 16 DQ rules (DQ-13 excluded, network-dependent)
│ ├── kpi/ 44 tests — ratios, CAGR, cash flow KPIs
│ ├── screener/ 8 tests — filter engine, peer percentiles, dashboard/API parity
│ ├── nlp/ 9 tests — pros/cons rule financials exemptions (Sprint 6)
│ └── api/ 13 tests — health, companies, screener, sectors endpoints (Sprint 6)
│ TOTAL: 146 tests, all passing
├── notebooks/
│ ├── exploratory_queries.sql 10 SQL queries against the loaded DB (Sprint 1)
│ ├── day6_qa_review.md Manual QA on 5 sample companies (Sprint 1)
│ ├── day12_spot_check.md Manual ROE/CAGR verification, 3 companies (Sprint 2)
│ ├── sprint1_retro.md through sprint6_retro.md Sprint retrospectives + findings
├── output/
│ ├── load_audit.csv, validation_failures.csv Sprint 1
│ ├── capital_allocation.csv, ratio_edge_cases.log Sprint 2
│ ├── screener_output.xlsx, peer_comparison.xlsx Sprint 3
│ ├── valuation_summary.xlsx, valuation_flags.csv Sprint 4
│ ├── analysis_parsed.csv, parse_failures.csv, analysis_cross_validation.csv,
│ │ pros_cons_generated.csv, cashflow_intelligence.xlsx, distress_alerts.csv,
│ │ pattern_distribution_summary.csv, pattern_changes.csv, skipped_tearsheets.csv Sprint 5
│ ├── cluster_labels.csv, outlier_report.csv, portfolio_stats.csv, perf_notes.md Sprint 6
│ └── final_deliverables/ Archived copy of every sprint's real deliverables, with MANIFEST.txt (Sprint 6)
├── reports/
│ ├── pytest_report.html Full test suite HTML report (not committed)
│ ├── radar_charts/ 92 PNG charts, one per company (Sprint 3)
│ ├── tearsheets/ 91 company tearsheet PDFs, 2 pages each (Sprint 5)
│ ├── sector/ 10 sector PDFs (Sprint 5)
│ ├── portfolio/ 1 portfolio summary PDF, 92 pages (Sprint 5)
│ ├── elbow_plot.png KMeans elbow curve (Sprint 6)
│ └── correlation_heatmap.png Pearson correlation of 10 KPIs (Sprint 6)
├── dev_notes/diagnostics/ Investigation scripts (see its README)
├── docs/
│ ├── Nifty100_Project_Document_FINAL.pdf Master spec
│ ├── openapi.json OpenAPI 3.0 spec (Sprint 6)
│ ├── analyst_guide.pdf 10-page user guide (Sprint 6)
│ └── (Postman collection export) (Sprint 6)
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

- [x] `financial_ratios` table populated: 1,070 rows (non-TTM company-years) — confirmed Sprint 6 to be the true, complete maximum given real data coverage
- [x] 30+ computed KPI columns
- [x] 44/44 KPI unit tests passing
- [x] Manual spot-check within 0.1% tolerance (reconfirmed Sprint 6, TCS & RELIANCE, 0.000pp diff)
- [x] `output/capital_allocation.csv`, `output/ratio_edge_cases.log`

### Sprint 3 — Screener & Peer Comparison Engine (Days 15–21)

- [x] 6 preset screeners implemented — Value Pick's narrow result investigated and confirmed genuine
- [x] `composite_quality_score` recomputed with full sector-relative formula
- [x] `output/screener_output.xlsx`, `output/peer_comparison.xlsx`
- [x] Peer ranking correctness verified in IT Services and FMCG groups; 11 real peer groups reconfirmed Sprint 6
- [x] 92 radar/bar charts generated
- [x] 17 DQ tests now covering 15 of 16 rules

### Sprint 4 — Dashboard & Valuation Module (Days 22–28)

- [x] All 8 Streamlit screens functional, tested across 5+ sectors and known edge cases
- [x] Company Profile loads under 3 seconds (reconfirmed Sprint 6: 0.025–0.030s per ticker)
- [x] Screener CSV export produces valid, correctly-headed files (reconfirmed Sprint 6 via round-trip check)
- [x] Extreme filter values handled gracefully in both directions
- [x] `output/valuation_summary.xlsx` — 92 rows, all required columns
- [x] `output/valuation_flags.csv` — 46 flagged companies
- [x] 5 real UI/logic bugs found and fixed (see `notebooks/sprint4_retro.md`)

### Sprint 5 — Intelligence, NLP & PDF Reports (Days 29–35)

- [x] `output/analysis_parsed.csv` — 64 rows, 0 parse failures, cross-validated against computed CAGR
- [x] `output/pros_cons_generated.csv` — all 92 companies have ≥1 pro and ≥1 con, via 12+12 primary rules plus a documented 3-tier fallback system, no fabricated signals
- [x] `output/cashflow_intelligence.xlsx` — 92 rows, all required columns, `cfo_quality_label` correctly derived
- [x] `output/distress_alerts.csv`
- [x] `output/pattern_distribution_summary.csv`, `output/pattern_changes.csv`
- [x] `reports/tearsheets/` — 91 of 92 PDFs (JIOFIN skipped, <3yr history)
- [x] `reports/sector/` — 10 PDFs (real sector count, not the spec's literal 11)
- [x] `reports/portfolio/portfolio_summary.pdf` — 92 pages, UP/DOWN/FLAT trend indicators
- [x] 7 real bugs found and fixed (see `notebooks/sprint5_retro.md`)

### Sprint 6 — API Server, Clustering & Final QA (Days 36–45)

- [x] `output/cluster_labels.csv` — all 92 companies assigned to one of 5 profiled clusters
- [x] `reports/elbow_plot.png`, `reports/correlation_heatmap.png`, `output/outlier_report.csv`, `output/portfolio_stats.csv`
- [x] `src/api/` — 16 live FastAPI endpoints, `docs/openapi.json`, full Postman collection
- [x] 146/146 tests passing (`reports/pytest_report.html`), including 22 new tests written this sprint
- [x] `output/perf_notes.md` — load test, dashboard load time, and simultaneous-process checks, all passing with large headroom; SQLite indexing evaluated and found unnecessary at current scale
- [x] 119 missing docstrings inserted (0 remaining), `black`/`ruff` clean
- [x] `docs/analyst_guide.pdf` — 10 pages
- [x] 32 real deliverables archived to `output/final_deliverables/` with a manifest
- [x] All 20 acceptance gates checked against the live system with real evidence — 18 clean passes, 2 gates fail against the spec's literal numbers but pass against verified-correct, fully-documented real data (see below)
- [x] 2 real bugs found and fixed during final QA (see *Known data findings*)

## Acceptance Gates (Sprint 6, Day 45)

All 20 gates checked with real evidence against the live system.

| Gate | Result | Note |
|---|---|---|
| AC-01 | PASS | 92 companies |
| AC-02 | PASS | 91.3% of companies have ≥10yr P&L/BS/CF coverage |
| AC-03 | PASS | 0 FK violations |
| AC-04 | FAIL (literal) / **PASS (verified)** | 1,070 is the true, complete max — 0 companies have any coverage gap; spec's "≥1,100" doesn't match achievable data |
| AC-05 | PASS | Independent manual recompute, 0.000pp diff |
| AC-06 | PASS | All 5 sampled companies within 5pp |
| AC-07 | PASS | Quality Compounder: 22 companies |
| AC-08 | PASS | 0.025–0.030s per ticker |
| AC-09 | PASS | CSV round-trip clean |
| AC-10 | PASS | 5 tearsheets visually confirmed clean; 1 real bug found and fixed along the way |
| AC-11 | PASS | `/health` → 200 |
| AC-12 | PASS | TCS: 12 years |
| AC-13 | PASS | API vs. Excel: identical company sets |
| AC-14 | PASS | 11 real peer groups |
| AC-15 | PASS | 92/92 cluster_id assigned |
| AC-16 | PASS | 0 companies missing a pro or con |
| AC-17 | FAIL (literal) / **PASS (verified)** | 91/92 — JIOFIN correctly skipped (2yr history, below 3yr minimum) |
| AC-18 | PASS | 146 tests, 0 failures |
| AC-19 | PASS | All required columns present |
| AC-20 | PASS | 10 pages |

## Known data findings

### From Sprint 1 (see `notebooks/sprint1_retro.md`)
TTM handling, 8 missing companies, AGTL→ATGL typo fix, unreliable `opm_percentage` for 21 companies, SBIN's missing balance sheet.

### From Sprint 2 (see `notebooks/sprint2_retro.md`)
`financial_ratios` vs `financial_ratios_source` split, HAL/BEL/INDIGO small-equity-base outliers, CIPLA/COALINDIA operating_profit question, capital-employed definition gap vs source ROCE.

### From Sprint 3 (see `notebooks/sprint3_retro.md`)
Debt-Free Blue Chip float-precision fix, Value Pick's genuine narrowness, sector exemption correction, Excel colour-coding bug fix, SBIN's graceful rendering in peer comparison.

### From Sprint 4 (see `notebooks/sprint4_retro.md`)
Average-vs-median ROE bug, dual-axis chart rendering bug (2 occurrences), slider type-mismatch crash, JIOFIN stub-year discovery, Discount/Caution threshold asymmetry (mathematically confirmed, not a bug), sector count correction (10, not 11) reconfirmed.

### From Sprint 5 (see `notebooks/sprint5_retro.md`)
`financial_ratios` has no `pe_ratio` column (only `market_cap` does) — a fallback rule was silently dead until traced; `cfo_quality_label` was never populated by any pipeline script despite the underlying ratio being correct; `balancesheet` contains 127 interim/quarterly rows mixed into annual data (SIEMENS genuinely reports on a September fiscal year); Excel silently upcasts a boolean column containing `None`; ReportLab's default font doesn't support Unicode arrow glyphs; insurance-sector ROCE outliers (HDFCLIFE 646%, ICICIPRULI 754%, ICICIGI 145%) found but not yet guarded against.

### From Sprint 6 (see `notebooks/sprint6_retro.md`)
- **`/api/v1/sectors` was aggregating sector medians and `company_count` over the full multi-year `financial_ratios` table instead of each company's latest year** — invisible to the test suite because `test_sectors.py` only ever checked the top-level sector count. Fixed; a new regression test checks `company_count` against an independent query.
- **`con_06_low_icr` and `C11` (Net Debt > 3x EBITDA) in `pros_cons_generator.py` had no financials exemption**, producing structurally meaningless cons for banks (e.g. HDFCBANK). `C11` had never been built as its own testable function, which is likely why the gap went undetected through two full sprints of test-writing. Fixed; 9 new regression tests added — the first test coverage this file has ever had.
- **`con_10_low_roce` has the same missing-exemption gap, deliberately deferred** — connects to the already-known insurance-sector ROCE outlier finding from Sprint 6's clustering work. Documented in code and here, not silently dropped.
- TCS's `companies.roe_percentage` field (0.52) is a raw decimal, not a percentage — the platform's own computed ROE is correct and unaffected; only the raw source field is off, and only for TCS.
- `financial_ratios` (1,070 rows) confirmed to be the true, complete maximum for real data coverage, not a population gap — every company's row count exactly matches their available `profitandloss` history.
- 91 of 92 tearsheets exist — JIOFIN correctly skipped (2yr history, below the 3yr minimum).

## Tech Stack

pandas, numpy, openpyxl, SQLite3, pytest, pytest-html, PyYAML, matplotlib,
streamlit, plotly, ReportLab, pdfplumber (dev/verification only),
scikit-learn, seaborn, FastAPI, uvicorn, httpx, requests, pypdf

## Running individual components

```bash
# Sprint 1
python db/loader.py
pytest tests/etl/ -v
pytest tests/dq/ -v

# Sprint 2
python src/analytics/populate_ratios.py
python src/analytics/generate_capital_allocation.py
python src/analytics/generate_edge_case_log.py
pytest tests/kpi/ -v

# Sprint 3
python src/screener/compute_composite_scores.py
python src/screener/export_screener_output.py
python src/analytics/peer.py
python src/reports/generate_radar_charts.py
python src/reports/generate_peer_comparison.py
pytest tests/screener/ -v

# Sprint 4
python src/analytics/valuation.py
streamlit run src/dashboard/app.py

# Sprint 5
python src/nlp/parser.py
python src/nlp/pros_cons_generator.py
python src/analytics/cashflow_intelligence.py
python src/analytics/capital_allocation_report.py
python src/reports/generate_tearsheets_batch.py
python src/reports/sector_report.py
python src/reports/portfolio_summary.py
pytest tests/kpi/test_cashflow_kpis.py -v
pytest tests/nlp/ -v

# Sprint 6
python src/analytics/clustering.py
python src/analytics/cluster_profiling.py
uvicorn src.api.main:app --port 8000
pytest tests/api/ -v
pytest tests/screener/test_dashboard_api_parity.py -v
python scripts/perf/load_test_screener.py     # requires uvicorn running
python scripts/perf/dashboard_load_time.py
python scripts/archive/build_final_deliverables.py

# Full suite
pytest tests/ --html=reports/pytest_report.html --self-contained-html -v
```

## Project Status: Complete

All 6 sprints delivered, 20/20 acceptance gates checked with real
evidence (18 clean passes, 2 documented spec-vs-reality discrepancies),
146/146 tests passing. Carried-forward, unresolved items — all
previously raised to the team lead, none silently resolved:

1. The 8 companies missing from `companies.xlsx` (unresolved since Sprint 1).
2. SBIN's missing balance sheet data (unresolved since Sprint 1).
3. CIPLA/COALINDIA `operating_profit` reliability (unresolved since Sprint 1/2).
4. `con_10_low_roce`'s missing financials exemption (found and deferred Sprint 6, connects to the insurance-sector ROCE outlier finding).
5. No single-run CLI mode for `sector_report.py` or `portfolio_summary.py` (only `tearsheet.py` got a `--ticker` option).
6. The dashboard's screener page duplicates `apply_filters()`'s logic manually rather than calling it directly — confirmed functionally equivalent, but remains structural duplication worth consolidating.