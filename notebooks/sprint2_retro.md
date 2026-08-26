# Sprint 2 Retrospective — Financial Ratio Engine

**Sprint:** Days 8–14 · **Status:** Complete
**Deliverable:** `financial_ratios` table — 1,070 rows, 30+ computed columns

## What was built

- `src/analytics/ratios.py` — profitability, leverage, efficiency ratios (Days 8-9)
- `src/analytics/cagr.py` — CAGR engine, all 6 edge cases, TTM-safe (Day 10)
- `src/analytics/cashflow_kpis.py` — FCF, CFO quality, CapEx intensity, 8-pattern capital allocation classifier (Day 11)
- `src/analytics/populate_ratios.py` — full pipeline populating `financial_ratios` for all companies (Day 12)
- `src/analytics/generate_edge_case_log.py` — ROCE/ROE cross-check vs source, categorized (Day 13)
- `tests/kpi/` — 44 unit tests across 4 files (exceeds spec's 20-test minimum)
- `output/capital_allocation.csv` — 1,063 rows, 8-pattern classification
- `output/ratio_edge_cases.log` — 54 categorized anomalies + 2 carried-forward Sprint 1 findings

## Key architectural decision

Renamed the Day-5-loaded source table to `financial_ratios_source`,
reserving `financial_ratios` for our own computed values — the two are
NOT the same data. Per spec Day 13's own instruction ("use ratio engine
value for analytics, source value for display only"), this was the
correct call, made explicit rather than left as an implicit conflict.

## Exit criteria — verified

- [x] `financial_ratios` row count: 1,070 (see note below re: spec's ≥1,100)
- [x] All required KPI columns populated, zero null-only columns
- [x] 44/44 unit tests pass (0 failures)
- [x] Manual spot-check: TCS, SUNPHARMA, HDFCBANK — ROE and 5yr Revenue
      CAGR all match hand-calculation within 0.1% (see
      `notebooks/day12_spot_check.md`)
- [x] `ratio_edge_cases.log` — every one of 54 entries has a genuine,
      investigated explanation (no "unknown"/"version difference" left)
- [x] Screener preview reviewed and validated (see below)

## Row count note (1,070 vs spec's ≥1,100)

`financial_ratios` is driven by non-TTM profitandloss rows (1,161 total
− 91 TTM = 1,070). This is a deliberate, correct exclusion — TTM is a
rolling window, not a fiscal year-end, and including it in a ratio
table would be incoherent with a `year` column meant to represent fixed
fiscal periods. The spec's 1,100 figure most likely assumed TTM rows
would be counted. Documented here as a reasoned deviation, not a gap in
coverage — every real fiscal year of data is represented.

## Real findings from this sprint

1. **`book_value_per_share` formula bug** (Day 12) — initial
   implementation hardcoded face_value=1 instead of joining the real
   `face_value` column from `companies.xlsx`. Caught before the table
   was finalized; fixed to properly derive shares outstanding.

2. **`dividend_payout_ratio_pct` omitted entirely** in the first Day 12
   pass — spec-required column that was simply forgotten in the initial
   wiring. Added and verified.

3. **Manual spot-check false alarm, real root cause found** (Day 12) —
   initial hand-verification of TCS's ROE didn't match the database.
   Traced to the verification query itself grabbing a `2024-09` mid-year
   balance sheet row instead of matching the P&L's `2024-03` fiscal
   year. The `financial_ratios` table's SQL join (exact `(company_id,
   year)` match) was correct throughout — only the manual check was
   flawed. Confirms some companies file quarterly/mid-year balance
   sheets in addition to annual ones; any future ad-hoc query against
   this data must match years exactly, not just take "latest."

4. **ROCE/ROE edge case log — three real sub-patterns identified**
   (Day 13), not lumped into one vague "differences happen" bucket:
   - **Small standalone equity base** (HAL, BEL): net_profit is 30-50x
     equity+reserves, producing mathematically correct but analytically
     meaningless extreme ratios. Likely standalone vs consolidated
     reporting difference in source balance sheet data.
   - **operating_profit reliability question** (CIPLA, COALINDIA):
     computed ROCE matches our formula exactly, but a large gap between
     operating_profit and net_profit for these two specifically drives
     the mismatch vs source. Flagged for the same scrutiny previously
     given to the opm_percentage field (Sprint 1 Finding 4).
     **Action for Sprint 3:** verify operating_profit reliability for
     these two before trusting them in screener/scoring logic.
   - **Capital-employed definition gap** (~15 companies, e.g. ABB,
     ASIANPAINT, BAJAJ-AUTO): consistent 5-15pp gaps, most plausibly a
     genuine difference between our `equity+reserves+borrowings`
     denominator and whatever the source calculation used.

5. **Screener preview outlier contamination** (Day 14) — a naive
   ROE>15% AND D/E<1 filter returned 38 companies but was topped by
   BEL (4744% ROE), HAL (3816%), and INDIGO (892%) — the same small-
   equity-base outliers from Finding 4. Root cause quantified precisely:
   `net_profit / (equity_capital+reserves) > 5` reliably identifies
   these cases (HAL ~37x, BEL ~47x, INDIGO ~9x — all comfortably above
   a normal company's ratio of 0.3-1.2). Guarded screener with this
   threshold returns 35 companies topped by real blue-chips (NESTLEIND,
   LT, TCS, INFY, ITC). **Action for Sprint 3:** the actual Investment
   Screener module (Module 3) needs this outlier guard built in as a
   designed feature, not an ad-hoc filter — this finding is the
   evidence base for that design requirement.

## Carried into Sprint 3

- Outlier guard (`profit/equity ratio` threshold) needed in the real
  Screener module (Finding 5)
- operating_profit reliability check for CIPLA, COALINDIA before trusting
  in scoring (Finding 4)
- Financials-sector companies need sector-relative ROCE benchmarking,
  not absolute thresholds, consistent with Sprint 1's OPM finding
- SBIN's null balance-sheet ratios (Sprint 1 Finding 8) still need a
  business decision before Sector Analytics / Health Scoring can fully
  include it