# Sprint 5 Retrospective — Intelligence, NLP & PDF Reports
**Days 29–35 | Completed 2026-09**

## What was built

- `src/nlp/parser.py` — regex parser for `analysis.xlsx` text fields
- `src/nlp/pros_cons_generator.py` — 12 pro + 12 con rules, confidence-scored,
  outlier-guarded, with a 3-tier fallback system for guaranteed coverage
- `src/analytics/cashflow_kpis.py` — extended (not overwritten) with
  `detect_distress_signal()` and `detect_deleveraging()`
- `src/analytics/cashflow_intelligence.py` — orchestration script producing
  `cashflow_intelligence.xlsx` and `distress_alerts.csv`
- `src/analytics/capital_allocation_report.py` — pattern distribution
  summary and year-over-year `pattern_changes.csv`
- `src/reports/tearsheet.py` — 2-page ReportLab tearsheet template
- `src/reports/generate_tearsheets_batch.py` — batch runner for all 92 companies
- `src/reports/sector_report.py` — one PDF per sector
- `src/reports/portfolio_summary.py` — one-page-per-company portfolio PDF

## Exit criteria — verified with evidence

- ✅ `pros_cons_generated.csv`: 92/92 companies have ≥1 pro and ≥1 con (560 rows)
- ✅ `cashflow_intelligence.xlsx`: 92 rows, all required columns, 0 unexplained nulls
- ✅ 91/92 tearsheets generated (JIOFIN correctly skipped, <3yr history), all 83.5–148.5 KB, well above the 30KB floor
- ✅ 10 sector PDFs (not 11 — see deviations below), verified via direct PDF text extraction, not just file size
- ✅ Portfolio summary: 92 pages, correct trend logic, verified via extraction
- ✅ 109/109 existing tests still passing throughout — zero regressions from any Sprint 5 work

## Real bugs found and fixed (root-caused, not patched blind)

1. **con_13 P/E fallback silently dead for all 92 companies** — `pe_ratio`
   doesn't exist in `financial_ratios` (only in `market_cap`). Confirmed via
   schema check. Fixed by sourcing from `mc_latest`, same place `dividend_yield`
   already came from.
2. **Fallback con rule_id mislabeling** — all fallback cons were hardcoded to
   `"C13_fallback"` regardless of which tier (C13/C14/C15/C16) actually fired.
   Caught via spot-check on PNB. Fixed by tracking the actual tier that returned
   a result.
3. **`cfo_quality_label` never populated** — column is `None` for all 1070 rows
   in `financial_ratios`; no script in the pipeline ever wrote it. The underlying
   ratio (`cfo_pat_ratio_5yr`) was correct throughout. Fixed by deriving the
   label in `cashflow_intelligence.py` via a shared `_cfo_quality_label()`
   helper extracted from `cfo_quality_score()` (pure refactor, no behavior change).
4. **Excel bool-column dtype upcast** — a `deleveraging_flag` column mixing
   `True`/`False`/`None` silently became `1.0`/`0.0`/`NaN` on Excel write.
   Fixed with an explicit Yes/No/`"Not Available"` string conversion —
   NOT `"N/A"`, because pandas' default NA-values list treats `"N/A"` as a
   missing-value marker on read-back, silently undoing the fix (caught via
   a second round of testing after the first "fix").
5. **`balancesheet` interim/quarterly contamination** — 127 non-fiscal-year-end
   rows (June/Sept/Dec) mixed into annual data, first surfaced as a stray
   `2024-09` bar in TCS's balance sheet chart. `financial_ratios` was already
   implicitly clean (verified for TCS). One company, SIEMENS, genuinely reports
   on a September fiscal year — confirmed consistent in both `balancesheet`
   and `financial_ratios`. Fixed by filtering `balancesheet` to only the years
   already present in that company's own `financial_ratios`, rather than
   hardcoding a "-03" filter that would have wrongly zeroed out SIEMENS.
6. **ROE/ROCE dual-axis chart tick mislabeling risk** — `set_xticklabels()`
   called without `set_xticks()` first on a line plot; matplotlib warned that
   labels could land on the wrong points. Fixed by pinning tick positions
   first, matching the pattern already used in the other 3 chart functions.
7. **Portfolio PDF trend arrows rendering as garbage glyphs** — Unicode arrow
   characters (↑↓→) aren't supported by ReportLab's default Helvetica/WinAnsi
   encoding; rendered as `fi`/`fl`/stray characters across all 92 pages.
   Fixed by switching to plain ASCII text (`UP`/`DOWN`/`FLAT`) — no font
   dependency risk.

## Real findings, confirmed correct (not bugs, documented and left alone)

- **18 companies fell through the con-rule fallback chain to progressively
  deeper tiers** — verified via real P/E-vs-sector-median and dividend-yield
  data that these are genuinely fairly-valued, decent-yield companies, not a
  bug. One holdout (PNB) traced to `operating_profit = None` for all 12 years
  in its `profitandloss` rows — a genuine, isolated source-data gap, resolved
  with a CFO/PAT-based fallback (C16) borrowing Day 31's own "Accrual Risk"
  definition a day early.
- **PNB's `distress_flag=True` but classified "Growth Funded by Debt"**, not
  "Distress Signal" — confirmed intentional: `detect_distress_signal()`'s
  2-variable definition (CFO<0, CFF>0) is deliberately broader than
  `classify_capital_allocation()`'s narrower 3-variable pattern label.
- **ASIANPAINT: 12 consecutive years as "Reinvestor"**, zero pattern changes —
  a genuinely stable, disciplined capital allocation history, not a data gap
  (unlike JIOFIN's trivial "0 changes" from only 1 valid year).
- **Insurance-sector ROCE outliers (HDFCLIFE 646%, ICICIPRULI 754%, ICICIGI
  145%)** — same small-denominator/large-numerator artifact as HAL/BEL/INDIGO,
  but a different sector and different companies than the outlier guard
  currently covers. Not fixed this sprint (existing guard was scoped to
  HAL/BEL/INDIGO specifically); flagged here for whoever does ROCE-based
  analysis in Sprint 6 or beyond.
- Sector PDF file sizes (2.5–5.3 KB) initially looked suspiciously small
  compared to tearsheets (83–148 KB) — investigated via direct PDF text
  extraction rather than assumed broken; confirmed correct (plain text tables
  vs. embedded chart PNGs is a legitimately different size profile).

## Known documented deviations from literal spec wording

- **10 sector PDFs generated, not 11** — `sectors.xlsx` has only 10 genuine
  `broad_sector` values (consistent with the "10 sectors, not 11" finding from
  Sprint 1/2). Real count printed explicitly by the script rather than forcing
  a fake 11th sector.
- **HDFCBANK's cons include ICR and ROCE thresholds** even though these behave
  differently for banks. Spec's Con Rule 1 (D/E) explicitly says "for
  non-financial companies"; Con Rules 6 (ICR) and 10 (ROCE) carry no such
  qualifier. Implemented literally as specified; flagged as a methodology
  note rather than silently exempted.

## Open items carried forward

- Insurance-sector ROCE outliers (see above) — not yet guarded against in any
  rule; worth considering for Sprint 6 if ROCE-based screening/scoring expands.
- The 3 pre-existing open questions from earlier sprints (8 missing companies,
  SBIN's missing balance sheet, CIPLA/COALINDIA operating_profit reliability)
  remain unresolved, pending a decision from outside this project.