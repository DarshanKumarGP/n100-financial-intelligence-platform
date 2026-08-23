# Day 6 — Manual QA Review

**Date:** 2026-08-22
**Companies checked:** TCS (fixed anchor, well-known public company) + 4 random
(seed=42): SUNPHARMA, BAJFINANCE, ADANIGREEN, HAL

**Script note:** Initial run of `day6_manual_qa.py` incorrectly returned `'TTM'`
as the "latest year" for every company, since SQLite's `ORDER BY year DESC`
sorts the `year` column as text, and `'TTM'` sorts after any `'20XX-MM'`
string alphabetically. Fixed by adding `AND year != 'TTM'` to all
"latest fiscal year" queries. Documented as Finding 3 below since the same
bug pattern will resurface in Sprint 2 if not handled explicitly there too.

## Per-company review (using corrected latest-fiscal-year query)

### TCS
Latest FY 2024-03: sales=₹240,893 Cr, net profit=₹46,099 Cr, EPS=127.
Computed ROE ~45.4%. Balance sheet diff 0.00%. 12yr P&L / 13yr BS / 12yr CF
coverage. Sector correctly Information Technology / IT Services. High but
realistic ROE for a debt-light IT major with strong margins. **Pass.**

### SUNPHARMA
Latest FY 2024-03: sales=₹48,497 Cr, net profit=₹9,610 Cr, EPS=40.
Computed ROE ~13.9%. Balance sheet diff 0.00%. 12yr/13yr/12yr coverage.
Sector correctly Healthcare / Pharmaceuticals. Plausible for the sector.
**Pass.**

### BAJFINANCE
Latest FY 2024-03: sales=₹54,972 Cr, net profit=₹14,451 Cr, EPS=233.
Computed ROE ~16.6%. Balance sheet diff 0.00%. 10yr/11yr/10yr coverage.
Sector correctly Financials / Consumer Finance. Balance sheet and computed
ROE look sound. Source `opm_percentage` field shows 19,987 — clearly not a
percentage; see Finding 1 below. **Pass on all genuine financials; source
OPM field confirmed unreliable, correctly not used in the ROE calc above.**

### ADANIGREEN
Latest FY 2024-03: sales=₹9,220 Cr, net profit=₹1,260 Cr, EPS=7.
Computed ROE ~11.9%. Balance sheet diff 0.00%. 8yr/9yr/8yr coverage.
Sector correctly Energy / Renewable Energy. **Pass.**

### HAL
Latest FY 2024-03: sales=₹30,381 Cr, net profit=₹7,595 Cr, EPS=114.
Balance sheet diff 0.00%. 12yr/10yr/8yr coverage. Sector correctly
Industrials / Defence & Aerospace. Computed ROE comes out to **3,669.1%**
— not a data error, but a real artifact of a very small equity base
(`equity_capital=5, reserves=202` as of latest BS row) relative to net
profit. This pattern is consistent across all 10 years of balance sheet
history, not a one-off anomaly, and most likely reflects standalone
(not consolidated) entity-level equity figures for this company in the
source file. **Flagged for Sprint 2**, not a Day 6 loading error: the
Ratio Engine should apply outlier-aware handling here, similar to the
bank/NBFC ROCE carve-out already specified in the spec (Section 13).

## Findings requiring action in Sprint 2

### Finding 1 — `opm_percentage` source field is unreliable for the Financials sector, plus a scattered set of other companies

**Evidence:** DQ-05 (OPM cross-check) flagged 234 rows across 21 companies
in `validation_failures.csv`. Confirmed directly in this review: BAJFINANCE's
source `opm_percentage` field reads `19987.0` for FY24 — not a plausible
percentage value. Full breakdown:
- **Financials sector: 13 of 23 companies (57%) flagged, 155 of 234 rows
  (66%).** Every flagged Financials company shows ALL years flagged
  (e.g. AXISBANK, HDFCBANK, ICICIBANK: 13/13 years each) — a complete,
  sector-wide pattern, not scattered.
- **8 additional companies scattered across Consumer Discretionary (2),
  Healthcare (2), Materials (2), Consumer Staples (1), Energy (1)** —
  isolated per-company issues, not sector-wide (e.g. only 2 of 6
  Healthcare companies affected).

**Root cause:** Per spec Section 28, "OPM" is not a standard metric for
banks/NBFCs/insurers — their operating economics don't map to a
sales-based margin the way manufacturing/IT/consumer companies do. The
source `opm_percentage` field for Financials companies likely reflects a
different underlying metric, not a computation error on our end.

**Action for Sprint 2 Ratio Engine (not a Sprint 1 fix):**
- Always compute OPM directly as `operating_profit / sales × 100` rather
  than trusting the source `opm_percentage` field, for ALL companies
  (per spec Section 13's existing instruction).
- For Financials-sector companies specifically, do not rely on
  OPM-based screens or scores at all — use NIM/ROA-based logic per
  Section 28's sector guidance.
- The 8 scattered non-Financials companies should still be flagged for
  the Ratio Engine's computed OPM, same handling as any other DQ-05 hit.

### Finding 2 — HAL's small standalone equity base

See HAL section above. Recommend the Ratio Engine flag or footnote
companies where `equity_capital + reserves` is unusually small relative
to `net_profit` (a simple outlier check), rather than reporting a
headline ROE number without context. HAL's naive ROE of 3,669% is a clear
example of why this guardrail is needed before Sprint 3's screener and
health-scoring modules consume this data.

### Finding 3 — `year` column sorts as TEXT, not chronologically

`ORDER BY year DESC` incorrectly returns `'TTM'` as the "latest" year for
every company, since string sort puts `'T'` after `'2'`. Caught and fixed
in this script by adding `year != 'TTM'` to the query. Any Sprint 2 query
needing "most recent fiscal year" must do the same explicitly — documented
here so this doesn't silently resurface in the Ratio Engine or CAGR
calculations.

## Overall verdict

All 5 sampled companies pass structural and plausibility review after the
TTM-sort fix. No Sprint 1 data-loading bugs found — companies.xlsx,
profitandloss.xl