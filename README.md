# N100 Financial Intelligence Platform

**Status:** Sprint 5 complete · **Sprint:** Days 1–35 of 45
**Author:** Darshan Kumar · Bluestock Fintech Internship

## Overview

This project builds a unified SQLite data warehouse and analytics engine
for 92 Nifty 100 companies. Sprint 1 (Days 1–7) built the data foundation.
Sprint 2 (Days 8–14) built the Financial Ratio Engine. Sprint 3 (Days
15–21) built the Investment Screener and Peer Comparison Engine. Sprint 4
(Days 22–28) built an 8-screen Streamlit dashboard and the Valuation
module. Sprint 5 (Days 29–35) built the NLP intelligence layer — auto
pros/cons generation, cash flow intelligence, capital allocation
reporting — and the automated PDF report generator: 92 company
tearsheets, 10 sector reports, and a one-page-per-company portfolio
summary.

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

# 13. Run the full test suite
pytest tests/ --html=reports/pytest_report.html --self-contained-html -v
```

Expected result: dashboard opens at `http://localhost:8501` with 8
navigable screens, `output/pros_cons_generated.csv` covers all 92
companies with ≥1 pro and ≥1 con, `output/cashflow_intelligence.xlsx`
has 92 rows, `reports/tearsheets/` has 91 PDFs (JIOFIN skipped — <3yr
history), `reports/sector/` has 10 PDFs, `reports/portfolio/` has one
92-page PDF, 109/109 unit tests pass.

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

## PDF Reports (Sprint 5)

| Report | Location | Contents |
|---|---|---|
| **Company Tearsheet** | `reports/tearsheets/<TICKER>_tearsheet.pdf` | 2 pages: navy header, 6 KPI tiles, Revenue/Net Profit and ROE/ROCE charts, Balance Sheet composition, Cash Flow waterfall, auto-generated Pros/Cons, Capital Allocation badge. 91 of 92 companies (JIOFIN skipped, <3yr history) |
| **Sector Report** | `reports/sector/<SECTOR>_report.pdf` | Sector median KPI summary + full company table (8 metrics each). 10 reports — see *Known data findings* below on the sector count |
| **Portfolio Summary** | `reports/portfolio/portfolio_summary.pdf` | One page per company, alphabetical, top 6 KPIs with UP/DOWN/FLAT/N/A trend vs prior year. 92 pages |

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
│ │ ├── cashflow_kpis.py FCF, CFO quality, CapEx intensity, 8-pattern classifier,
│ │ │ distress signal + deleveraging detection (Sprint 5)
│ │ ├── populate_ratios.py Populates the financial_ratios table
│ │ ├── generate_capital_allocation.py Generates capital_allocation.csv
│ │ ├── generate_edge_case_log.py Cross-checks computed vs source ROCE/ROE
│ │ ├── cashflow_intelligence.py Generates cashflow_intelligence.xlsx, distress_alerts.csv (Sprint 5)
│ │ ├── capital_allocation_report.py Pattern distribution summary, pattern_changes.csv (Sprint 5)
│ │ ├── peer.py Peer percentile rankings (11 groups, 10 metrics)
│ │ └── valuation.py FCF yield, sector median P/E, overvaluation flags
│ ├── nlp/
│ │ ├── parser.py Regex parser for analysis.xlsx text fields (Sprint 5)
│ │ ├── cross_validate_analysis.py Parsed vs computed CAGR cross-check (Sprint 5)
│ │ └── pros_cons_generator.py 12+12 rules, 3-tier fallback system, confidence-scored (Sprint 5)
│ ├── screener/
│ │ ├── engine.py Filter engine — 15 metrics, sector exemptions
│ │ ├── presets.py 6 preset screeners
│ │ ├── compute_composite_scores.py Sector-relative composite quality score
│ │ └── export_screener_output.py Generates screener_output.xlsx
│ ├── reports/
│ │ ├── generate_radar_charts.py 92 radar/bar charts
│ │ ├── generate_peer_comparison.py Generates peer_comparison.xlsx
│ │ ├── tearsheet.py 2-page company tearsheet template (Sprint 5)
│ │ ├── generate_tearsheets_batch.py Batch runner, all 92 companies (Sprint 5)
│ │ ├── sector_report.py One PDF per sector (Sprint 5)
│ │ └── portfolio_summary.py One-page-per-company portfolio PDF (Sprint 5)
│ └── dashboard/
│ ├── app.py Streamlit entry point, sidebar navigation
│ ├── utils/db.py 9 cached data-loading functions, TTM-safe
│ └── pages/ 8 screen files (01_home.py – 08_reports.py)
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
│ ├── sprint3_retro.md Sprint 3 retrospective + findings
│ ├── sprint4_retro.md Sprint 4 retrospective + findings
│ └── sprint5_retro.md Sprint 5 retrospective + findings
├── output/
│ ├── load_audit.csv Per-table row counts (Sprint 1)
│ ├── validation_failures.csv All DQ rule violations, with severity (Sprint 1)
│ ├── capital_allocation.csv 8-pattern label per company-year (Sprint 2)
│ ├── ratio_edge_cases.log 54 categorized ROCE/ROE anomalies (Sprint 2)
│ ├── screener_output.xlsx 6 preset sheets + Notes, colour-coded (Sprint 3)
│ ├── peer_comparison.xlsx 11 peer group sheets, colour-coded (Sprint 3)
│ ├── valuation_summary.xlsx 92 companies, valuation multiples + flags (Sprint 4)
│ ├── valuation_flags.csv 46 Caution/Discount flagged companies (Sprint 4)
│ ├── analysis_parsed.csv Structured CAGR values from analysis.xlsx (Sprint 5)
│ ├── parse_failures.csv Unmatched text entries, 0 rows (Sprint 5)
│ ├── analysis_cross_validation.csv Parsed vs computed CAGR comparison (Sprint 5)
│ ├── pros_cons_generated.csv Pros/cons for all 92 companies, confidence-scored (Sprint 5)
│ ├── cashflow_intelligence.xlsx CFO quality, CapEx intensity, distress/deleveraging flags (Sprint 5)
│ ├── distress_alerts.csv Companies with CFO<0 AND CFF>0 (Sprint 5)
│ ├── pattern_distribution_summary.csv Capital allocation pattern counts, latest year (Sprint 5)
│ ├── pattern_changes.csv Year-over-year pattern transitions per company (Sprint 5)
│ └── skipped_tearsheets.csv Companies skipped from batch tearsheet generation (Sprint 5)
├── reports/
│ ├── pytest_report.html Full test suite HTML report (not committed)
│ ├── radar_charts/ 92 PNG charts, one per company (Sprint 3)
│ ├── tearsheets/ 91 company tearsheet PDFs, 2 pages each (Sprint 5)
│ ├── sector/ 10 sector PDFs (Sprint 5)
│ └── portfolio/ 1 portfolio summary PDF, 92 pages (Sprint 5)
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
- [x] 30+ computed KPI columns
- [x] 44/44 KPI unit tests passing
- [x] Manual spot-check within 0.1% tolerance
- [x] `output/capital_allocation.csv`, `output/ratio_edge_cases.log`

### Sprint 3 — Screener & Peer Comparison Engine (Days 15–21)

- [x] 6 preset screeners implemented — Value Pick's narrow result investigated and confirmed genuine
- [x] `composite_quality_score` recomputed with full sector-relative formula
- [x] `output/screener_output.xlsx`, `output/peer_comparison.xlsx`
- [x] Peer ranking correctness verified in IT Services and FMCG groups
- [x] 92 radar/bar charts generated
- [x] 17 DQ tests now covering 15 of 16 rules

### Sprint 4 — Dashboard & Valuation Module (Days 22–28)

- [x] All 8 Streamlit screens functional, tested across 5+ sectors and known edge cases
- [x] Company Profile loads under 3 seconds
- [x] Screener CSV export produces valid, correctly-headed files
- [x] Extreme filter values handled gracefully in both directions
- [x] `output/valuation_summary.xlsx` — 92 rows, all required columns
- [x] `output/valuation_flags.csv` — 46 flagged companies
- [x] 5 real UI/logic bugs found and fixed (see `notebooks/sprint4_retro.md`)
- [x] 109/109 project-wide tests passing, zero regressions from dashboard work

### Sprint 5 — Intelligence, NLP & PDF Reports (Days 29–35)

- [x] `output/analysis_parsed.csv` — 64 rows, 0 parse failures, cross-validated against computed CAGR
- [x] `output/pros_cons_generated.csv` — all 92 companies have ≥1 pro and ≥1 con (560 rows), via 12+12 primary rules plus a documented 3-tier fallback system, no fabricated signals
- [x] `output/cashflow_intelligence.xlsx` — 92 rows, all required columns, `cfo_quality_label` correctly derived (was never populated by any prior script)
- [x] `output/distress_alerts.csv` — 13 companies flagged
- [x] `output/pattern_distribution_summary.csv`, `output/pattern_changes.csv` — capital allocation audit and year-over-year change tracking
- [x] `reports/tearsheets/` — 91 of 92 PDFs (JIOFIN skipped, <3yr history), all 83.5–148.5 KB, well above the 30KB floor
- [x] `reports/sector/` — 10 PDFs (real sector count, not the spec's literal 11 — see findings below), verified via direct text extraction
- [x] `reports/portfolio/portfolio_summary.pdf` — 92 pages, UP/DOWN/FLAT trend indicators
- [x] 7 real bugs found and fixed (see `notebooks/sprint5_retro.md`)
- [x] 109/109 project-wide tests passing, zero regressions from any Sprint 5 work

## Known data findings

### From Sprint 1 (see `notebooks/sprint1_retro.md`)
TTM handling, 8 missing companies, AGTL→ATGL typo fix, unreliable `opm_percentage` for 21 companies, SBIN's missing balance sheet.

### From Sprint 2 (see `notebooks/sprint2_retro.md`)
`financial_ratios` vs `financial_ratios_source` split, HAL/BEL/INDIGO small-equity-base outliers, CIPLA/COALINDIA operating_profit question, capital-employed definition gap vs source ROCE.

### From Sprint 3 (see `notebooks/sprint3_retro.md`)
Debt-Free Blue Chip float-precision fix, Value Pick's genuine narrowness, sector exemption correction, Excel colour-coding bug fix, SBIN's graceful rendering in peer comparison.

### From Sprint 4 (see `notebooks/sprint4_retro.md`)
Average-vs-median ROE bug, dual-axis chart rendering bug (2 occurrences), slider type-mismatch crash, JIOFIN stub-year discovery, Discount/Caution threshold asymmetry (mathematically confirmed, not a bug), sector count correction (10, not 11) reconfirmed in the dashboard context.

### From Sprint 5 (see `notebooks/sprint5_retro.md`)
`financial_ratios` has no `pe_ratio` column (only `market_cap` does) — a fallback rule was silently dead until traced; `cfo_quality_label` was never populated by any pipeline script despite the underlying ratio being correct; `balancesheet` contains 127 interim/quarterly rows mixed into annual data (SIEMENS genuinely reports on a September fiscal year, confirmed consistent across both `balancesheet` and `financial_ratios`); Excel silently upcasts a boolean column containing `None` to `1.0`/`0.0`/`NaN`, and `"N/A"` collides with pandas' default missing-value list on read-back; ReportLab's default font doesn't support Unicode arrow glyphs; insurance-sector ROCE outliers (HDFCLIFE 646%, ICICIPRULI 754%, ICICIGI 145%) found but not yet guarded against — same root cause as HAL/BEL/INDIGO, different sector; 10 sector PDFs generated, not the spec's literal 11, consistent with the already-confirmed sector count.

## Tech Stack

pandas, openpyxl, SQLite3, pytest, pytest-html, PyYAML, matplotlib, streamlit, plotly, ReportLab, pdfplumber (dev/verification only)

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

# Full suite
pytest tests/ -v
```

## Next: Sprint 6 (not yet started)

Per the master spec: KMeans clustering, a FastAPI REST server (16
endpoints), a final full test suite (60+ tests targeted — already at
109), final documentation/analyst guide, and acceptance sign-off. Exact
day-by-day task list not yet provided by the team lead.

Carried forward from Sprint 5: the insurance-sector ROCE outlier finding
(not yet guarded against in any rule). From earlier sprints: CIPLA/
COALINDIA's operating_profit reliability, the 8 missing companies, and
SBIN's missing balance sheet — all still pending a decision from outside
this project.