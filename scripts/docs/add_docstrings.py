"""
N100 Financial Intelligence Platform
Sprint 6, Day 44: Automated docstring insertion

Location: scripts/docs/add_docstrings.py

Inserts a one-line docstring into every public function currently
missing one, per the ast-based scan run 2026-09-23. Matches functions
by (file, function name) and locates each function's real signature
end-line dynamically (handles both single-line and multi-line def
signatures) rather than trusting a stale line number, since inserting
at the wrong line would corrupt a file.

Does NOT touch any other code -- only inserts a new docstring line
immediately after a function's signature, and only for functions that
don't already have one (re-checks with ast.get_docstring() before
inserting, so it's safe to run more than once).

Usage:
    python scripts/docs/add_docstrings.py            # apply
    python scripts/docs/add_docstrings.py --dry-run   # preview only
"""

import ast
import sys

DOCSTRINGS = {
    "src/analytics/capital_allocation_report.py": {
        "main": "CLI entry point: verify Sprint 2's capital_allocation.csv coverage, build the pattern distribution summary, and write pattern_changes.csv.",
    },
    "src/analytics/cashflow_intelligence.py": {
        "main": "CLI entry point: compute CFO quality, CapEx intensity, and distress/deleveraging flags for all companies; write cashflow_intelligence.xlsx and distress_alerts.csv.",
    },
    "src/analytics/clustering.py": {
        "load_latest_features": "Load each company's latest-year clustering features, imputing missing values with the sector median (falling back to the global median where a sector median is itself undefined).",
        "generate_elbow_plot": "Fit KMeans for k=2..10 and save an inertia-vs-k elbow plot to reports/elbow_plot.png.",
        "main": "CLI entry point: run KMeans clustering (n_clusters=5, random_state=42) and write output/cluster_labels.csv.",
    },
    "src/analytics/cluster_profiling.py": {
        "load_latest_ratios": "Load each company's latest-year value for every profiling KPI from financial_ratios.",
        "build_cluster_profile": "Compute mean and median of the clustering features per cluster and assign a descriptive cluster name.",
        "build_correlation_heatmap": "Compute the Pearson correlation matrix of the 10 profiling KPIs and save it as an annotated seaborn heatmap to reports/correlation_heatmap.png.",
        "build_portfolio_stats": "Compute P10-P90, mean, and standard deviation for each KPI across all companies.",
        "main": "CLI entry point: profile clusters, run per-sector outlier detection, and write outlier_report.csv and portfolio_stats.csv.",
    },
    "src/analytics/generate_capital_allocation.py": {
        "main": "CLI entry point: classify each company-year's capital allocation pattern and write output/capital_allocation.csv.",
    },
    "src/analytics/generate_edge_case_log.py": {
        "main": "CLI entry point: cross-check computed ROE/ROCE against source values and log categorized anomalies to output/ratio_edge_cases.log.",
    },
    "src/analytics/peer.py": {
        "write_to_db": "Write computed peer percentile rankings to the peer_percentiles table.",
        "main": "CLI entry point: compute peer percentile rankings for all peer groups and persist them to the database.",
    },
    "src/analytics/populate_ratios.py": {
        "main": "CLI entry point: compute and populate the financial_ratios table for all companies and years.",
        "composite": "Compute a company's sector-relative composite quality score from its individual ratio percentiles.",
    },
    "src/analytics/valuation.py": {
        "compute_fcf_yield": "Compute free cash flow yield (FCF divided by market cap) for a company-year.",
        "main": "CLI entry point: compute valuation flags (FCF yield, sector median P/E, over/undervaluation) and write valuation_summary.xlsx and valuation_flags.csv.",
    },
    "src/api/routers/companies.py": {
        "list_companies": "List all companies, optionally filtered by sector, market cap category, or a partial name/ticker search.",
        "get_company_detail": "Return a single company's full profile, including latest-year computed KPIs and sector data; 404 if the ticker is not found.",
        "get_profit_and_loss": "Return a company's P&L history, optionally filtered to a from_year/to_year range.",
        "get_balance_sheet": "Return a company's balance sheet history, optionally filtered to a from_year/to_year range.",
        "get_cashflow": "Return a company's cash flow history, optionally filtered to a from_year/to_year range.",
        "get_ratios": "Return a company's computed KPIs for every year, or a single year if the year query param is given.",
        "get_tearsheet": "Return the pre-generated tearsheet PDF for a company as a binary download; 404 if the ticker doesn't exist or has no generated tearsheet.",
    },
    "src/api/routers/documents.py": {
        "get_company_documents": "Return a company's annual report links with a concurrently-checked is_url_valid flag for each.",
    },
    "src/api/routers/health.py": {
        "get_health": "Return service status, row counts for every table in the database, uptime, and the API version.",
    },
    "src/api/routers/peers.py": {
        "get_peer_group": "Return all companies in a peer group with their percentile rank for each tracked metric; 404 if the group is unknown.",
        "compare_to_peers": "Return radar-chart data comparing a company against its peer group average and a benchmark company.",
    },
    "src/api/routers/portfolio.py": {
        "get_portfolio_stats": "Return the pre-computed P10-P90 percentile table for core KPIs across all companies.",
    },
    "src/api/routers/screener.py": {
        "screener": "Filter and rank companies by the given query parameters, wrapping engine.py's run_screener(); returns HTTP 400 for invalid parameter values.",
    },
    "src/api/routers/sectors.py": {
        "list_sectors": "Return all sectors with company count and median ROE/P-E/D-E; discloses the real sector count where it differs from the spec.",
        "get_sector_companies": "Return all companies in a sector with their latest-year KPIs; 404 if the sector is unknown.",
    },
    "src/api/routers/valuation.py": {
        "get_market_cap_history": "Return a company's historical valuation multiples (P/E, P/B, EV/EBITDA, dividend yield) for 2019-2024.",
    },
    "src/dashboard/pages/02_profile.py": {
        "fmt": "Format a KPI value for display, returning 'N/A' for missing data.",
    },
    "src/dashboard/pages/03_screener.py": {
        "get_snapshot": "Load and cache the latest company snapshot with the outlier guard applied, shared across all screener filters.",
    },
    "src/dashboard/pages/04_peers.py": {
        "normalize": "Normalize a metric value onto a common scale for radar chart plotting.",
        "highlight_benchmark": "Style the benchmark company's row/trace distinctly in the peer comparison view.",
    },
    "src/etl/loader.py": {
        "main": "CLI entry point: rebuild data/nifty100.db from the raw Excel source files.",
    },
    "src/etl/validator.py": {
        "load_and_normalize": "Load a core source file and apply ticker/year normalization; reused by every DQ rule and the loader.",
        "dq01_company_pk_uniqueness": "DQ-01: flag duplicate company_id values in companies.xlsx.",
        "dq02_annual_pk_uniqueness": "DQ-02: flag duplicate (company_id, year) pairs within an annual table.",
        "dq03_fk_integrity": "DQ-03: flag rows referencing a company_id with no matching row in companies.xlsx.",
        "dq07_year_format": "DQ-07: flag year values that don't normalize to a recognized fiscal-year format.",
        "dq08_ticker_format": "DQ-08: flag ticker values that are too short or otherwise malformed.",
        "dq04_balance_sheet_balance": "DQ-04: flag balance sheet rows where assets don't balance against liabilities within tolerance.",
        "dq05_opm_cross_check": "DQ-05: flag rows where the source opm_percentage diverges materially from operating_profit/sales.",
        "dq06_positive_sales": "DQ-06: flag rows with zero or missing sales.",
        "dq09_net_cash_check": "DQ-09: flag cash flow rows where CFO+CFI+CFF doesn't reconcile with the reported net cash flow.",
        "dq10_non_negative_fixed_assets": "DQ-10: flag rows with negative fixed assets.",
        "dq11_tax_rate_range": "DQ-11: flag rows where the implied tax rate falls outside a plausible range.",
        "dq12_dividend_payout_cap": "DQ-12: flag rows where the dividend payout ratio exceeds a sanity cap.",
        "dq14_eps_sign_consistency": "DQ-14: flag rows where EPS sign doesn't match net profit sign.",
        "dq15_strict_balance_info": "DQ-15: return informational (non-blocking) detail on balance sheet reconciliation for a single company-year.",
        "dq16_coverage_check": "DQ-16: flag companies with too few years of history to support 'sustained/consecutive year' analysis.",
        "run_all_rules": "Run every DQ rule against a loaded table and return the combined list of violations.",
        "main": "CLI entry point: run all DQ rules against the raw source files and write output/validation_failures.csv.",
    },
    "src/nlp/cross_validate_analysis.py": {
        "main": "CLI entry point: cross-validate parser.py's parsed CAGR values against the Ratio Engine's computed CAGR and flag divergences over 5%.",
    },
    "src/nlp/parser.py": {
        "main": "CLI entry point: parse analysis.xlsx's text fields and write output/analysis_parsed.csv and output/parse_failures.csv.",
    },
    "src/nlp/pros_cons_generator.py": {
        "clamp_confidence": "Clamp a computed confidence score to the valid 0-100 range.",
        "pro_01_roe_sustained": "Pro rule 1: flag companies with ROE above 20% sustained for 3+ years.",
        "pro_02_fcf_positive_5yr": "Pro rule 2: flag companies with positive free cash flow for 5+ consecutive years.",
        "pro_03_debt_free": "Pro rule 3: flag companies with D/E of 0 in the latest year.",
        "pro_04_revenue_cagr_15": "Pro rule 4: flag companies with 5-year revenue CAGR above 15%.",
        "pro_05_opm_25": "Pro rule 5: flag companies with operating profit margin above 25% in the latest year.",
        "pro_06_pat_cagr_20": "Pro rule 6: flag companies with 5-year PAT CAGR above 20%.",
        "pro_07_icr_high": "Pro rule 7: flag companies with interest coverage ratio above 10, or debt-free.",
        "pro_08_dividend_yield": "Pro rule 8: flag companies with dividend yield above 2% and positive FCF.",
        "pro_09_eps_cagr_15": "Pro rule 9: flag companies with 5-year EPS CAGR above 15%.",
        "pro_10_roe_improving": "Pro rule 10: flag companies with ROE improving for 3 consecutive years.",
        "pro_11_operating_leverage": "Pro rule 11: flag companies where 5-year revenue CAGR is below PAT CAGR, indicating operating leverage.",
        "pro_12_assets_growing_debt_declining": "Pro rule 12: flag companies with growing assets alongside declining debt.",
        "con_01_high_de": "Con rule 1: flag non-financial companies with D/E above 2.0.",
        "con_02_fcf_negative_3yr": "Con rule 2: flag companies with negative free cash flow for 3 consecutive years.",
        "con_03_opm_declining": "Con rule 3: flag companies with operating margin declining for 3 consecutive years.",
        "con_04_net_loss": "Con rule 4: flag companies with a net loss in the latest year.",
        "con_05_revenue_declining": "Con rule 5: flag companies with revenue declining for 2+ consecutive years.",
        "con_06_low_icr": "Con rule 6: flag companies with interest coverage ratio below 1.5.",
        "con_07_high_payout": "Con rule 7: flag companies with dividend payout ratio above 100%.",
        "con_08_de_rising": "Con rule 8: flag companies with D/E rising for 3 consecutive years.",
        "con_09_eps_declining": "Con rule 9: flag companies with EPS declining for 3 consecutive years.",
        "con_10_low_roce": "Con rule 10: flag companies with ROCE below 10%.",
        "con_12_low_revenue_cagr": "Con rule 12: flag companies with 5-year revenue CAGR below 5%.",
        "main": "CLI entry point: run all pro/con rules plus the fallback tier for every company and write output/pros_cons_generated.csv.",
    },
    "src/reports/generate_peer_comparison.py": {
        "load_peer_data": "Load each peer group's member companies and their latest-year metric values.",
        "load_percentiles": "Load each company's computed percentile rank within its peer group.",
        "write_sheet": "Write one peer group's comparison table to its own sheet in the output workbook.",
        "main": "CLI entry point: generate peer_comparison.xlsx with one sheet per peer group.",
    },
    "src/reports/generate_radar_charts.py": {
        "load_latest_snapshot": "Load each company's latest-year metric values used to plot its radar chart.",
        "main": "CLI entry point: generate a radar/bar chart PNG for every company under reports/radar_charts/.",
    },
    "src/reports/generate_tearsheets_batch.py": {
        "main": "CLI entry point: batch-generate tearsheet PDFs for all companies with at least 3 years of data, logging skipped tickers to output/skipped_tearsheets.csv.",
    },
    "src/reports/portfolio_summary.py": {
        "fmt": "Format a KPI value for display, returning 'N/A' for missing data.",
        "build_header": "Build the navy header bar for a portfolio summary page.",
        "build_kpi_table": "Build the top-6-KPI table with UP/DOWN/FLAT trend labels for a company's portfolio summary page.",
        "generate_portfolio_pdf": "Generate the one-page-per-company portfolio summary PDF for all companies, alphabetical by ticker.",
    },
    "src/reports/sector_report.py": {
        "fmt": "Format a KPI value for display, returning 'N/A' for missing data.",
        "build_header": "Build the navy header bar for a sector report.",
        "build_median_summary": "Build the sector-level median KPI summary section.",
        "build_company_table": "Build the table listing every company in the sector with its key metrics.",
        "generate_sector_report": "Generate the 2-part sector PDF (median summary + company table) for one sector.",
        "main": "CLI entry point: batch-generate all 10 sector report PDFs under reports/sector/.",
    },
    "src/reports/tearsheet.py": {
        "gather_company_data": "Load a company's financial_ratios, P&L, balance sheet (fiscal-year-filtered), and cash flow data needed to build its tearsheet.",
        "get_pros_cons": "Load a company's generated pros and cons text from output/pros_cons_generated.csv.",
        "get_capital_allocation_label": "Load a company's capital allocation pattern label from output/cashflow_intelligence.xlsx.",
        "make_revenue_profit_chart": "Build the 10-year Revenue vs Net Profit bar chart as a ReportLab Image.",
        "make_roe_roce_chart": "Build the 10-year ROE vs ROCE dual-axis line chart as a ReportLab Image.",
        "make_balance_sheet_stack_chart": "Build the balance sheet composition stacked bar chart as a ReportLab Image, or None if no data is available.",
        "make_cashflow_waterfall_chart": "Build the latest-year cash flow waterfall chart as a ReportLab Image, or None if no data is available.",
        "build_header": "Build the navy header bar showing the company ticker.",
        "build_kpi_tiles": "Build the 2x3 grid of latest-year KPI tiles.",
        "build_pros_cons_section": "Build the green pros / red cons bullet-list section.",
        "build_capital_allocation_badge": "Build the capital allocation pattern badge shown at the bottom of page 2.",
        "generate_tearsheet": "Generate the 2-page tearsheet PDF for one company; returns (False, reason) if it has fewer than 3 years of ratio history.",
        "fmt": "Format a KPI value for display, returning 'N/A' for missing data.",
    },
    "src/screener/compute_composite_scores.py": {
        "main": "CLI entry point: compute sector-relative composite quality scores for all companies.",
        "weighted_row": "Compute one company's weighted composite score from its individual percentile ranks.",
    },
    "src/screener/engine.py": {
        "load_config": "Load the screener's filterable metrics and outlier guard settings from screener_config.yaml.",
    },
    "src/screener/export_screener_output.py": {
        "write_sheet": "Write one preset's screener results to its own colour-coded sheet in the output workbook.",
        "main": "CLI entry point: run all 6 screener presets and write screener_output.xlsx.",
    },
}


def find_sig_end_index(lines, def_idx):
    """0-based index of the line where a def's signature colon closes (handles multi-line signatures)."""
    idx = def_idx
    depth = 0
    while idx < len(lines):
        depth += lines[idx].count("(") - lines[idx].count(")")
        stripped = lines[idx].rstrip()
        if depth <= 0 and stripped.endswith(":"):
            return idx
        idx += 1
    return def_idx


def process_file(path, func_docs, dry_run):
    with open(path, encoding="utf-8") as f:
        source = f.read()
    lines = source.splitlines(keepends=True)

    tree = ast.parse(source, filename=path)
    targets = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in func_docs and not ast.get_docstring(node):
                targets.append((node.lineno, node.name))

    if not targets:
        return 0

    # Insert bottom-to-top so earlier line numbers stay valid
    targets.sort(key=lambda t: t[0], reverse=True)
    count = 0
    for lineno, name in targets:
        def_idx = lineno - 1
        sig_end_idx = find_sig_end_index(lines, def_idx)
        body_line = lines[sig_end_idx + 1] if sig_end_idx + 1 < len(lines) else ""
        indent = ""
        for ch in body_line:
            if ch in (" ", "\t"):
                indent += ch
            else:
                break
        if not indent:
            # fall back to def's own indent + 4 spaces
            def_line = lines[def_idx]
            base_indent = def_line[: len(def_line) - len(def_line.lstrip())]
            indent = base_indent + "    "

        docstring = func_docs[name]
        new_line = f'{indent}"""{docstring}"""\n'
        lines.insert(sig_end_idx + 1, new_line)
        count += 1
        print(f"  {'[dry-run] ' if dry_run else ''}{path}:{lineno} -> {name}")

    if not dry_run:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines)

    return count


def main():
    dry_run = "--dry-run" in sys.argv
    total = 0
    for path, func_docs in DOCSTRINGS.items():
        n = process_file(path, func_docs, dry_run)
        total += n
    print(f"\n{'Would insert' if dry_run else 'Inserted'} {total} docstrings across {len(DOCSTRINGS)} files.")


if __name__ == "__main__":
    main()