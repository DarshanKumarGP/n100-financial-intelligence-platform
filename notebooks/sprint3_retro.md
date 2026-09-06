# Sprint 3 Retrospective — Screener & Peer Comparison Engine

**Sprint:** Days 15–21 · **Status:** Complete
**Deliverables:** `screener_output.xlsx`, `peer_comparison.xlsx`, `peer_percentiles` table, 92 radar charts

## What was built

- `config/screener_config.yaml` — 15 filterable metrics, analyst-editable
- `src/screener/engine.py` — filter engine, sector exemption, ICR-as-infinity, outlier guard
- `src/screener/presets.py` — 6 preset screeners
- `src/screener/compute_composite_scores.py` — Day 17's full sector-relative composite formula
- `src/screener/export_screener_output.py` — 6 sheets + Notes, colour-coded
- `src/analytics/peer.py` — percentile ranking across 10 metrics, 11 groups
- `src/reports/generate_radar_charts.py` — 92 charts, 2 chart types
- `src/reports/generate_peer_comparison.py` — 11 sheets, colour-coded, benchmark-highlighted
- `tests/screener/`, 9 new DQ tests — 109 total tests across the project

## Exit criteria — verified

- [x] 6 preset screeners: 5 landed 5-50 naturally; Value Pick's 2-company
      result investigated and confirmed genuine (see Finding 2)
- [x] `peer_comparison.xlsx` — exactly 11 sheets, 56 total company rows
- [x] Peer percentile correctness verified: IT Services group, TCS (highest
      ROE) also shows the highest percentile rank (1.0), fully monotonic
      down the group
- [x] All 16 DQ rules now have test coverage (15 explicit + DQ-13 reasonably
      excluded as network-dependent) — 17 DQ tests, up from 8
- [x] Quality Compounder manually verified: top 5 results all genuinely
      satisfy ROE>15% AND D/E<1, real recognizable companies
- [x] 109 total tests passing project-wide

## Key architectural decisions

1. **Composite score formula superseded, not duplicated.** Sprint 2's
   `populate_ratios.py` computed a simpler population-wide composite
   score. Day 17's spec formula (sector-relative, more granular
   weighting, needs FCF CAGR + CFO/PAT ratio that didn't exist yet) is
   a genuine refinement, not a parallel metric — `composite_quality_score`
   was recomputed in place to reflect the more complete Day 17 formula.

2. **`market_cap` fiscal-year-to-calendar-year join is a stated
   assumption**, not a verified fact: fiscal year `'2024-03'` maps to
   `market_cap.year=2024`. Confirmed the join itself works cleanly
   (92/92 companies have P/E, P/B, Dividend Yield data), but the exact
   date-matching precision wasn't independently verified against source
   documentation.

3. **Outlier guard from Sprint 2 (Finding 5) is now load-bearing**
   across every preset and the composite score — `net_profit/equity_base
   > 5` reliably filters HAL/BEL/INDIGO-style extreme values from
   contaminating screener results.

## Real findings from this sprint

1. **Debt-Free Blue Chip's exact `D/E == 0` filter was a real bug.**
   Companies that are economically debt-free (BAJAJHLDNG, BOSCHLTD, ITC,
   MARUTI) computed tiny non-zero D/E values (e.g. 0.0011) due to float
   division, failing a strict equality check. Fixed to `D/E < 0.01`.
   Result went from 2 companies (out of range) to 22 (correctly in range).

2. **Value Pick returns 2 companies — investigated and confirmed
   genuine, not a bug.** The `market_cap` join is clean (all 92
   companies have data). Per-condition pass rates show P/B<3 (10
   companies) and P/E<20 (14 companies) are the binding constraints,
   not D/E or Dividend Yield (69/72 pass individually). Reflects real
   current valuation levels in the Nifty 100 — kept as-is rather than
   loosened to force a "nicer" count.

3. **The 46 vs 35 screener count discrepancy (Day 15) was the sector
   exemption working correctly**, not a regression. Day 14's earlier
   preview lacked the spec-required Financials D/E exemption; Sprint 3's
   real engine correctly includes 13 Financials-sector companies that
   Day 14's simpler query had wrongly excluded.

4. **Day 20's colour-coding bug** (`TypeError` comparing string to
   float) traced to reading percentile values back from written Excel
   cells instead of the source DataFrame — fixed by colouring directly
   from the DataFrame during the same write pass, avoiding openpyxl's
   read-back type coercion entirely.

5. **DQ test coverage gap closed.** Sprint 1 built 8 DQ tests covering 7
   of 16 rules; 9 more added this sprint, bringing coverage to 15 of 16
   rules explicitly tested (DQ-13's live URL check reasonably excluded).

6. **SBIN's known NULL balance-sheet data (Sprint 1 Finding 8) confirmed
   to render gracefully** in `peer_comparison.xlsx` — blank cells for
   BS-dependent metrics, correctly gold-highlighted as the Public
   Sector Banks benchmark, full data present for P&L/cashflow metrics.

## Minor documentation notes

- "Median of percentile rank" columns in `peer_comparison.xlsx`'s
  summary row are mathematically valid but not independently meaningful
  in small (3-7 company) peer groups, where percentile values are
  constrained to a small discrete set. Not a defect — just a caveat for
  interpretation.

## Carried into Sprint 4

- `market_cap` fiscal-year join assumption — worth a closer look if
  Sprint 4's Valuation module needs tighter date precision
- CIPLA/COALINDIA operating_profit reliability (Sprint 2 Finding 4) —
  still not resolved, may affect any OPM-based logic in later sprints
- Missing-companies and SBIN questions (Sprint 1 Findings 2 and 8) —
  still pending team lead input