# Sprint 1 Retrospective — Data Foundation

**Sprint:** Days 1–7 · **Status:** Complete
**Deliverable:** `data/nifty100.db` — 12 tables, fully validated and loaded

## What was built

- `src/etl/normaliser.py` — `normalize_year()` and `normalize_ticker()`,
  40 unit tests, handles every year-format variant found in the real
  data (standard month-year, FY-prefix, bare year, TTM, and known
  ticker typo correction)
- `src/etl/validator.py` — all 16 DQ rules implemented, 8 unit tests,
  outputs `output/validation_failures.csv`
- `db/schema.sql` — 12-table SQLite schema with composite PK/FK
  constraints enforcing DQ-01/02/03 at the database level
- `db/loader.py` — builds `nifty100.db` from all 12 source files,
  applies dedup (DQ-02) and orphan-rejection (DQ-03), generates
  `output/load_audit.csv`
- `notebooks/exploratory_queries.sql` — 10 queries covering row counts,
  null checks, year coverage, sector distribution, and targeted
  spot-checks tied to findings below
- `notebooks/day6_qa_review.md` — manual QA on 5 companies

## Exit criteria — verified

- [x] `SELECT COUNT(*) FROM companies` = 92
- [x] `PRAGMA foreign_key_check` = 0 rows
- [x] `load_audit.csv` shows zero CRITICAL rejections in the final DB
- [x] 48/48 unit tests passing (40 normaliser + 8 DQ rules) —
      `reports/pytest_report.html` generated, 2.27s runtime
- [x] Manual review of 5 companies completed with documented findings
- [x] 10 exploratory queries run and verified against `nifty100.db`

## Real findings from this sprint

1. **TTM rows (100 in P&L)** — a legitimate reporting period, explicitly
   recognized rather than rejected or force-parsed into a fake date.

2. **8 companies missing from `companies.xlsx`** (ULTRACEMCO, UNIONBANK,
   UNITDSPR, VBL, VEDL, WIPRO, ZOMATO, ZYDUSLIFE) — genuinely absent
   from the master file despite having years of P&L/BS/CF data. Their
   rows are correctly excluded from `nifty100.db` via FK rejection.
   **Open item: awaiting confirmation from team lead on whether these
   should be added to companies.xlsx or intentionally excluded.**

3. **AGTL/ATGL ticker typo** — confirmed and corrected via
   `KNOWN_TICKER_CORRECTIONS` in `normaliser.py`. 7 rows recovered in
   `cashflow.xlsx` that would otherwise have been silently lost.

4. **`opm_percentage` source field unreliable for 21 companies**
   (155/234 flagged rows in the Financials sector specifically, tied to
   OPM not being a meaningful metric for banks/NBFCs per spec Section
   28). Directly confirmed via Query 9 of `exploratory_queries.sql`:
   BAJFINANCE's source field reads 19,987 against a computed value of
   29.29. **Action for Sprint 2:** Ratio Engine must compute OPM
   directly rather than trust this source field, and use NIM/ROA logic
   for Financials.

5. **HAL's small standalone equity base** produces an implausible naive
   ROE (>3,600%). **Action for Sprint 2:** Ratio Engine needs an
   outlier guard on equity-based ratios.

6. **`year` column sorts as TEXT** — `ORDER BY year DESC` incorrectly
   surfaces `'TTM'` as "latest" for any company. Documented so this
   doesn't silently break Sprint 2's CAGR/ratio queries.

7. **119 `financial_ratios` rows deduplicated with differing values**
   (not exact duplicates) — kept last per DQ-02, logged for review.

8. **SBIN has zero rows in `balancesheet.xlsx`** — found via Day 7's
   coverage-matrix query. Confirmed via direct inspection of the raw
   source file: SBIN is entirely absent from `balancesheet.xlsx`, not
   mislabeled or filtered by our loader. Checked whether this reflects
   a broader "banks report differently" pattern — **ruled out**: all 8
   other banks checked (HDFCBANK, ICICIBANK, AXISBANK, KOTAKBANK, PNB,
   CANBK, BANKBARODA, INDUSINDBK) each have a full 12 rows. This is an
   isolated gap specific to SBIN, most likely a source-file omission.
   SBIN does have P&L (13yr) and cashflow (12yr) data. **Action:** flag
   to team lead alongside the 8-missing-companies question — SBIN, as
   India's largest bank by assets, will need balance-sheet-derived
   metrics (D/E, ROCE, asset turnover) either sourced separately or
   explicitly marked unavailable in Sprint 2+ modules.

## Data quality summary

- 522 total CRITICAL findings from Day 3's validator, all fully
  reconciled and explained (8 unparseable years, 234 exact-duplicate
  rows, 280 orphan-company rows) — none were unexplained noise.
- Every dedup/rejection number in the final load traced back to a
  specific, evidenced root cause, not assumed.
- Coverage gap check (Query 10) surfaced exactly one company (SBIN)
  missing from one table entirely — investigated and explained above.

## Engineering notes (process, not data)

- Two import-path issues surfaced during the week: `validator.py`
  needed `sys.path` handling to work correctly both as a direct script
  and as a pytest-imported module; `run_exploratory_queries.py`
  initially discarded every SQL statement due to a comment-filtering
  bug that checked whole blocks instead of individual lines. Both
  fixed and verified.

## Carried into Sprint 2

- Missing-companies decision (Finding 2) — still pending team lead input
- SBIN balance-sheet gap (Finding 8) — still pending team lead input
- OPM field handling for Ratio Engine (Finding 4)
- Equity-outlier guard for ROE-type ratios (Finding 5)
- TTM-exclusion pattern for any "latest year" query (Finding 6)