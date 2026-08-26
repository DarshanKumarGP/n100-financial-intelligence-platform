# Day 12 — Manual Spot-Check: ROE and 5yr Revenue CAGR

Per spec exit criteria: 3 companies, ROE and 5yr Revenue CAGR recomputed
by hand, compared to `financial_ratios` table values, tolerance 0.1%.

## Companies checked: TCS, SUNPHARMA, HDFCBANK (year: 2024-03)

| Company | Metric | Manual calc | Database value | Match |
|---|---|---|---|---|
| TCS | ROE | 50.94% | 50.9443% | ✓ |
| TCS | Revenue CAGR 5yr | 10.46% | 10.4636% | ✓ |
| SUNPHARMA | ROE | 15.09% | 15.0942% | ✓ |
| SUNPHARMA | Revenue CAGR 5yr | 10.78% | 10.7812% | ✓ |
| HDFCBANK | ROE | 14.34% | 14.3397% | ✓ |
| HDFCBANK | Revenue CAGR 5yr | 21.95% | 21.9510% | ✓ |

All 6 values match within the required 0.1% tolerance.

## Process note

Initial verification attempt for TCS and SUNPHARMA showed a mismatch on
ROE (TCS: 45.42% hand-calc vs 50.94% database). Root cause traced and
confirmed: the manual verification query selected the balance sheet's
"latest by year DESC" row, which for TCS and SUNPHARMA is a `2024-09`
mid-year filing, not the `2024-03` fiscal year-end that the P&L data
(and `financial_ratios` table, via its exact `(company_id, year)` SQL
join) actually uses. Once the manual calculation was corrected to use
matched fiscal years, all values reconciled exactly.

This confirms `populate_ratios.py`'s join logic (`LEFT JOIN balancesheet
b ON p.company_id = b.company_id AND p.year = b.year`) is correct --
the initial discrepancy was in the verification method, not the pipeline.
HDFCBANK required no correction since it has no `2024-09` row, serving
as a useful confirming contrast case.