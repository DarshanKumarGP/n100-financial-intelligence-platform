# Diagnostic Scripts — Sprint 1 Development History

These scripts were written during Days 2–7 to investigate specific data
quality findings before deciding on a fix. Kept here (not deleted) as an
audit trail — each one maps to a documented finding in
`notebooks/sprint1_retro.md`.

| Script | Finding it investigates |
|---|---|
| `diagnose_year_parse.py` | TTM / stub-period year values (Day 2) |
| `diagnose_balancesheet_years.py` | `'2024.5'` anomaly in balancesheet (Day 2) |
| `diagnose_dq_findings.py`, `diagnose_dq_root_causes.py` | 522 CRITICAL DQ findings breakdown (Day 3–4) |
| `diagnose_bs_reconciliation.py` | Dedup/orphan count reconciliation (Day 4) |
| `diagnose_cashflow_contradiction.py`, `diagnose_cashflow_silent_filter.py` | Cashflow validator/loader mismatch, AGTL/ATGL typo (Day 5) |
| `diagnose_day6_anomalies.py` | BAJFINANCE OPM field, HAL equity outlier (Day 6) |
| `diagnose_sbin_gap.py` | SBIN missing from balancesheet.xlsx (Day 7) |
| `inspect_remaining_files.py` | Column/shape inspection before Day 5 loader code |
| `day6_manual_qa.py`, `run_exploratory_queries.py` | Producing `day6_qa_review.md` and `exploratory_queries.sql` output |

These are not part of the production pipeline (`src/etl/`, `db/`) and are
not required to run the project — they're historical/investigative only.
