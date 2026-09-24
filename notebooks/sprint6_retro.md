# Sprint 6 Retrospective — API Server, Clustering & Final QA

Days 36–45 | Final sprint of the N100 Financial Intelligence Platform

## What was built

- **KMeans clustering** (`src/analytics/clustering.py`): 5 clusters over
  `return_on_equity_pct, debt_to_equity, revenue_cagr_5yr, fcf_cagr_5yr,
  operating_profit_margin_pct`, sector-median imputation with a global-median
  fallback, `n_clusters=5, random_state=42`. `output/cluster_labels.csv`
  (92/92 assigned), `reports/elbow_plot.png`.
- **Cluster profiling** (`src/analytics/cluster_profiling.py`): mean/median
  per cluster, descriptive naming with a sector-dominance override rule
  (Financials mislabeled "Value Cyclicals" on first pass — high D/E is the
  sector's normal business model, not distress). `reports/correlation_heatmap.png`,
  `output/outlier_report.csv`, `output/portfolio_stats.csv`.
- **FastAPI server** (`src/api/`): 16 endpoints across 8 routers, CORS,
  request-logging middleware, a global `RequestValidationError` → 400
  handler. `docs/openapi.json`, full Postman collection export.
- **112 → 146 tests**: new `tests/api/` (13 tests), `tests/screener/
  test_dashboard_api_parity.py` (3 tests), `tests/nlp/test_pros_cons_generator.py`
  (9 tests, Day 45 addition). Zero redundant tests written to pad counts —
  Day 41's existing coverage was verified sufficient for 3 of 4 named tasks
  before writing anything new.
- **Performance & integration testing** (Day 43): load test, dashboard
  load time, and simultaneous Streamlit+FastAPI checks, all passing with
  large headroom. `output/perf_notes.md`.
- **Documentation** (Day 44): 119 missing docstrings inserted across 34
  files (0 remaining gaps, confirmed by AST scan); `black`/`ruff` clean;
  `docs/analyst_guide.pdf` (10 pages); 32 real deliverables archived to
  `output/final_deliverables/`.
- **Final sign-off** (Day 45): all 20 acceptance gates checked against the
  live system with real evidence.

## Real bugs found and fixed this sprint

1. **`sectors.py` — sector medians/company_count computed over the wrong
   dataframe.** `list_sectors()` built a `latest`-year-only dataframe via
   `groupby("company_id").tail(1)` but then aggregated over the full
   multi-year `fr` dataframe instead, discovered during the Day 44 ruff
   pass (`F841 latest assigned but never used`). Two real consequences:
   `median_roe`/`median_de` were medians across *every* historical year for
   every company in a sector, not the latest year; `company_count` counted
   company-*years*, not distinct companies. Invisible to `test_sectors.py`
   the whole time — that test only ever checked the top-level sector count
   (10), never `company_count` or the median values. Fixed by aggregating
   over `latest` instead, and added an explicit `ORDER BY company_id, year`
   to the source query (the original had none, so `tail(1)` was only
   "correct" by accident of SQLite's unordered return order). A new
   regression test, `test_company_count_matches_distinct_companies_per_sector`,
   checks `company_count` against an independent `COUNT(DISTINCT
   company_id)` query so this can't silently regress.

2. **`con_06_low_icr` and the inline `C11` (Net Debt > 3x EBITDA) rule had
   no financials exemption.** Found during the Day 45 AC-10 visual check —
   HDFCBANK's tearsheet showed "Interest coverage ratio below 1.5x" and
   "Net debt exceeding 3 times EBITDA" as cons, both structurally
   meaningless for a bank (deposits/borrowings are the core business, not
   discretionary leverage — the same reasoning already applied to
   `con_01_high_de`'s exemption and the screener's D/E sector exemption
   since Sprint 3). `con_06_low_icr` had no `is_financials` parameter at
   all. Separately, `C11` was never built as its own testable function like
   every other rule — it was inlined directly in `main()`, which is likely
   *why* its missing exemption went undetected through Sprint 5, all of
   Sprint 6's docstring scan, and the `ruff` pass: no function named
   `con_11_...` existed for either to catch. Fixed: `con_06_low_icr(latest,
   is_financials)` now exempts financials; the inline logic is now its own
   `con_11_high_net_debt(latest, pl_latest, is_financials)`, wired into
   `main()` the same way every other rule is. 9 new regression tests added
   in `tests/nlp/test_pros_cons_generator.py` — the first test coverage
   this file has ever had.

3. **My own AC-06 acceptance-check script used the wrong methodology on
   its first run.** Computed a relative percentage difference instead of
   the project's own established absolute-percentage-point convention
   (the same one `ratio_edge_cases.log` uses). Produced 4 false failures
   (HDFCBANK, INFY, RELIANCE, ABB) that a `grep` against the existing edge
   case log immediately disproved — none of the four appeared there.
   Recomputed with the correct methodology; all 5 sampled companies pass.
   Not a data or product bug, but worth recording since the check script is
   part of this sprint's real output.

4. **My own AC-14 acceptance-check script used a nonexistent column name**
   (`peer_group` instead of the real `peer_group_name`), producing a false
   FAIL. Confirmed via `PRAGMA table_info` and fixed; the real data shows
   11 peer groups, matching Sprint 3's original finding exactly.

## Deviations from literal spec wording, with justification

- **AC-04 (financial_ratios ≥ 1,100)**: real count is 1,070, and verified
  to be the true, complete maximum — every single company's
  `financial_ratios` row count exactly equals their available non-TTM
  `profitandloss` history, 0 gaps anywhere. The spec's number doesn't match
  achievable coverage.
- **AC-17 (92 tearsheets)**: 91 exist. JIOFIN is correctly skipped (2 years
  of history, below the 3-year minimum) — documented since Sprint 5.
- **"11 sectors"** (recurring since Sprint 4): real count is 10, confirmed
  again this sprint in `/api/v1/sectors`, `test_sectors.py`, and the
  clustering/profiling work.
- **Sprint 6 spec's own health-endpoint task ("10 tables")**: real schema
  has 14 tables. Disclosed via `db_table_count_note` in the `/health`
  response.
- **con_10_low_roce (deferred, not fixed)**: same structural gap as
  con_06/con_11 — no financials exemption — connects to the already-known
  open item on insurance-sector ROCE distortions (HDFCLIFE 646%,
  ICICIPRULI 754%, ICICIGI 145%). A conscious decision to defer rather than
  expand scope at the very end of the final sprint; documented in code
  comments and here rather than silently left unaddressed.

## What's carried forward / open

1. The 8 companies missing from `companies.xlsx` (unresolved since Sprint 1).
2. SBIN's missing balance sheet data (unresolved since Sprint 1).
3. CIPLA/COALINDIA `operating_profit` reliability (unresolved since Sprint 1/2).
4. `con_10_low_roce`'s missing financials exemption (new this sprint, deferred).
5. No single-run mode exists for `sector_report.py` or `portfolio_summary.py`
   (only `tearsheet.py` got a `--ticker` CLI option this sprint).
6. The dashboard's screener page (`03_screener.py`) duplicates
   `apply_filters()`'s logic manually rather than calling it directly —
   confirmed functionally equivalent via `test_dashboard_api_parity.py`,
   but remains structural duplication worth consolidating in any future work.

## Final test count

146 tests, 146 passing, 0 failures. `reports/pytest_report.html` current
as of the last full run this sprint.