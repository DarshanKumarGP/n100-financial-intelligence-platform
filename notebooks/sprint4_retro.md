# Sprint 4 Retrospective — Dashboard & Valuation Module

**Sprint:** Days 22–28 · **Status:** Complete
**Deliverables:** 8-screen Streamlit dashboard, `valuation_summary.xlsx`, `valuation_flags.csv`

## What was built

- `src/dashboard/app.py` — main entry point, sidebar navigation
- `src/dashboard/utils/db.py` — 9 cached data-loading functions, TTM exclusion built into every query
- 8 screens: Home, Company Profile, Screener, Peer Comparison, Trend Analysis, Sector Analysis, Capital Allocation Map, Annual Reports
- `src/analytics/valuation.py` — FCF yield, sector median P/E, overvaluation/discount flagging

## Exit criteria — verified

- [x] All 8 screens load without errors, tested across IT, Financials, FMCG, Energy, Healthcare sectors plus known edge cases (SBIN's missing balance sheet, JIOFIN's 2-year history, HAL/BEL/INDIGO's extreme ratios)
- [x] Company Profile loads under 3 seconds (confirmed across 5 tickers)
- [x] Screener CSV download produces a valid file with correct headers
- [x] `valuation_summary.xlsx` — 92 rows, all required columns
- [x] Extreme slider values (both directions) handled gracefully
- [x] 109/109 project-wide tests still passing after all Sprint 4 changes — zero regressions

## Real bugs found and fixed this sprint

1. **Home screen "Average ROE" tile showed 125.1%** — a meaningless number
   caused by 3 extreme small-equity-base outliers (HAL, BEL, INDIGO)
   dragging a simple mean far from reality. Fixed by switching to
   median (20.7% without outliers, confirmed by direct query). Same
   fix applied consistently to the Sector Analysis median KPI chart.

2. **ROE line invisible on Company Profile's dual-axis chart** — traced
   to `make_subplots(secondary_y=True)` silently failing to render one
   trace despite clean float64 data (verified on HDFCBANK: ROE 14-20%,
   ROCE 2.7-4.8%, both real, only ROCE drew). Fixed by rebuilding the
   chart with explicit `yaxis`/`yaxis2` layout definitions instead of
   `make_subplots`, which is now the standard pattern used everywhere
   dual-axis charts appear in this dashboard.

3. **Net Profit bars visually flattened against Revenue** — same shared-
   axis problem recurring in a different form (bars, not lines).
   Fixed identically: separate y-axes for the two series.

4. **Slider type mismatch crash on preset button click** — clicking a
   Screener preset wrote raw Python ints to `st.session_state` while
   the sliders themselves were defined with float bounds, producing a
   `StreamlitAPIException`. Fixed by forcing `float(val)` when presets
   write to session state.

5. **JIOFIN's Revenue & Net Profit chart looked broken but wasn't** —
   one bar visually dwarfing the other. Root cause: JIOFIN was demerged
   and listed in August 2023, so its first reported year (2023-03,
   sales=45 Cr) is a genuine partial stub period versus its first full
   year (2024-03, sales=1,855 Cr) — a real ~41x jump, not a data error.
   Added a general-purpose caption (triggers on any >10x YoY jump, not
   JIOFIN-specific) explaining likely partial-period causes rather than
   leaving the chart to look like a rendering glitch.

## Documented deviations from literal spec wording

- **Trend Analysis's "YoY % annotation"**: implemented as hover tooltips
  rather than permanent on-chart text labels, since up to 3 overlaid
  metrics × 10 years would produce up to 30 cluttering labels.
- **Capital Allocation Map's "click to filter"**: Plotly treemaps don't
  natively support Streamlit click-event filtering; implemented as a
  dropdown selector achieving the same end result (view companies in a
  chosen pattern) without custom JS.
- **Annual Reports' "404 detection"**: implemented as a static check on
  whether the URL field is present/well-formed, not a live HTTP request
  per pageview — consistent with how DQ-13 (Sprint 1) treats URL
  validation as a batch job, not an inline UI check.

## Sector count correction (carried from Sprint 3, reconfirmed)

Dashboard's sector donut chart correctly shows **10** sectors, not the
spec's stated 11 — `sectors.xlsx` has zero companies in the
"Conglomerates/Other" category. Verified fresh via `get_sectors()` on
Day 22 before any chart was built, so this was never a display bug to
catch later.

## Valuation module finding: Discount/Caution asymmetry investigated

Flag distribution: 46 Fair, 30 Discount, 16 Caution — a real asymmetry
that was investigated rather than accepted at face value. Confirmed:
P/E distribution is nearly symmetric (skewness -0.07), ruling out
skewed underlying data as the cause. The asymmetry is a **direct,
confirmed mathematical consequence of the spec's own threshold
multipliers**: the Discount threshold (0.7x median) sits only ~13.5
points below a typical sector median P/E of ~45, while the Caution
threshold (1.5x median) sits ~22.5 points above it. For a symmetric
distribution, the nearer threshold catches proportionally more
companies. Not a bug, not a data artifact — a structural property of
asymmetric multipliers applied to roughly-centered data.

## Outlier guard applied consistently across Sprint 4

The `net_profit/equity_base > 5` guard (established Sprint 2, Finding
5) was applied in three new places this sprint: the Home screen's
median calculations, the Screener's snapshot building (inherited
directly from Sprint 3's `engine.py`), and the Valuation module's
sector median P/E calculation (HAL/BEL/INDIGO excluded from computing
the benchmark, though they still appear in the final output with their
own flag).

## Carried into Sprint 5

- `market_cap` fiscal-year-to-calendar-year join remains a stated,
  verified-for-coverage but not fully precision-tested assumption
- CIPLA/COALINDIA operating_profit reliability question (Sprint 2)
  still unresolved
- Missing-companies and SBIN questions (Sprint 1) still pending team
  lead input