# Performance & Integration Test Notes — Sprint 6, Day 43

Tested 2026-09-23.

## 1. Load test — 10 concurrent screener API calls

Script: `scripts/perf/load_test_screener.py`
Method: 10 varied real filter combinations fired concurrently at the live
`GET /api/v1/screener` endpoint via `ThreadPoolExecutor` (real HTTP calls
against a running `uvicorn` server, not the in-process `TestClient`).

**Result: total wall time 0.555s (target: under 10s) — PASS**, large headroom.

Per-request latency ranged 0.325s–0.546s. All 10 requests returned HTTP 200
with real, varied row counts (5–83 companies depending on filter).

Two issues were found and fixed in the *test script itself* during this
check — neither was an API bug:
- First run used `sector=IT` as a test parameter, which correctly 400'd
  because the real stored `broad_sector` value is `"Information Technology"`,
  not `"IT"`. Confirmed directly against the `sectors` table (10 real
  sectors, matching every prior sprint's finding).
- First run's `row_count` metric read `len(resp.json())`, which counted the
  3 top-level keys of the API's `{"count", "filters_applied", "results"}`
  response shape instead of actual result rows — every request showed
  `rows=3` regardless of filter. Fixed to read `response["count"]` directly.
  Confirmed via a direct `curl` + `json.tool` inspection of the real
  response shape before assuming the API itself was broken.

## 2. Dashboard performance — Company Profile load time, 5 tickers

Script: `scripts/perf/dashboard_load_time.py`
Method: calls the exact 4 per-ticker data-loading functions
`src/dashboard/pages/02_profile.py` uses (`get_ratios`,
`get_ratios_history`, `get_pl`, `get_pros_cons`) plus the shared
`get_companies()` baseline, directly from `src/dashboard/utils/db.py`,
timed cold (no `@st.cache_data` warm-cache benefit, since that requires a
live Streamlit runtime a standalone script doesn't have — this measures
the realistic worst case, a user's first view of a given ticker).

| Ticker | Total data-fetch time | Target | Result |
|---|---|---|---|
| TCS | 0.030s | <3s | PASS |
| HDFCBANK | 0.028s | <3s | PASS |
| RELIANCE | 0.026s | <3s | PASS |
| SUNPHARMA | 0.027s | <3s | PASS |
| TATASTEEL | 0.025s | <3s | PASS |

**All 5 PASS**, ~100x under target. This measures the data-fetch layer only,
not full Streamlit render/paint time — but since SQLite reads are the only
real cost in this pipeline (a handful of small KPI tiles and charts render
fast regardless), this is representative of where load time would actually
go.

Manually confirmed separately in the browser: Company Profile page for ABB
(Abbott India Ltd) rendered correctly with all 6 KPI tiles populated
(ROE 32.5%, ROCE 36.5%, Net Profit Margin 20.5%, D/E 0.0, Revenue CAGR 5yr
9.7%, FCF 1095.0 Cr) and the Revenue & Net Profit chart section loading
beneath it.

## 3. End-to-end: Streamlit + FastAPI running simultaneously

Started both processes at once:
```
uvicorn src.api.main:app --port 8000
streamlit run src/dashboard/app.py   (default port 8501)
```

**Result: PASS.** No port conflict. Both processes stayed up concurrently,
both reading the same `data/nifty100.db` SQLite file with no
`database is locked` error or any other contention issue observed.

Manually verified in-browser with both processes running:
- Company Profile page (ABB) — loaded correctly, all KPI tiles populated
  with real data.
- Screener page — loaded correctly, 89 companies matched the default
  filter state, real per-company metrics displayed in the results table.

## 4. SQLite query optimisation / indexing

Spec text: "Apply SQLite query optimisation if needed — add indexes on
company_id and year columns in large tables."

**Not applied — genuinely not needed at current scale.** All three checks
above passed with large headroom (10 concurrent screener calls in 0.555s
against a 10s target; per-ticker profile loads in ~0.03s against a 3s
target). At 92 companies and roughly 1,000–1,600 rows per core table, SQLite
performs these reads fast enough without indexes that adding them now would
be optimising a bottleneck that doesn't exist, rather than a genuine fix.
Documented here explicitly rather than adding indexes just to tick the
spec's line — consistent with this project's standing rule against
fabricating work to match spec wording. Worth revisiting only if the
dataset scope grows well beyond the current ~92-company, ~6-year window.

## Summary

| Check | Target | Result | Status |
|---|---|---|---|
| 10 concurrent screener calls | <10s total | 0.555s | PASS |
| Company Profile load (5 tickers) | <3s each | 0.025–0.030s each | PASS |
| Streamlit + FastAPI simultaneous | No conflicts | No conflicts | PASS |
| SQLite indexing | Apply if needed | Not needed at current scale | N/A — documented |

No real bottlenecks found. Day 43 performance/integration testing complete.