"""
N100 Financial Intelligence Platform
Sprint 6, Day 44: Final Deliverables Archive

Location: scripts/archive/build_final_deliverables.py

Copies every real, confirmed deliverable from Sprints 1-6 into
output/final_deliverables/, organized by sprint subfolder, and writes
a manifest.

Note on the spec's "23 deliverables": no single enumerated list of
exactly 23 items exists anywhere in this project's history -- it's a
spec-stated count, not something ever itemized file-by-file. The real,
confirmed deliverable set below has 31 or 32 distinct items (depending
on whether output/perf_notes.md exists -- see the check below), likely
because the spec's "23" bundles some multi-file outputs (e.g. all of
Sprint 5's NLP outputs) as single line items rather than counting each
file. Documented here explicitly, same treatment as the sector-count
(10 vs 11) and tearsheet-count (91 vs 92) discrepancies elsewhere in
this project, rather than trimming the real list to force a match.

Usage:
    python scripts/archive/build_final_deliverables.py
"""

import os
import shutil

DEST_ROOT = "output/final_deliverables"

# (source path, sprint label, is_directory)
DELIVERABLES = [
    # --- Sprint 1 ---
    ("output/load_audit.csv", "sprint1", False),
    ("output/validation_failures.csv", "sprint1", False),
    # --- Sprint 2 ---
    ("output/capital_allocation.csv", "sprint2", False),
    ("output/ratio_edge_cases.log", "sprint2", False),
    # --- Sprint 3 ---
    ("output/screener_output.xlsx", "sprint3", False),
    ("output/peer_comparison.xlsx", "sprint3", False),
    ("reports/radar_charts", "sprint3", True),
    # --- Sprint 4 ---
    ("output/valuation_summary.xlsx", "sprint4", False),
    ("output/valuation_flags.csv", "sprint4", False),
    # --- Sprint 5 ---
    ("output/analysis_parsed.csv", "sprint5", False),
    ("output/parse_failures.csv", "sprint5", False),
    ("output/analysis_cross_validation.csv", "sprint5", False),
    ("output/pros_cons_generated.csv", "sprint5", False),
    ("output/cashflow_intelligence.xlsx", "sprint5", False),
    ("output/distress_alerts.csv", "sprint5", False),
    ("output/pattern_distribution_summary.csv", "sprint5", False),
    ("output/pattern_changes.csv", "sprint5", False),
    ("output/skipped_tearsheets.csv", "sprint5", False),
    ("reports/tearsheets", "sprint5", True),
    ("reports/sector", "sprint5", True),
    ("reports/portfolio", "sprint5", True),
    # --- Sprint 6 ---
    ("output/cluster_labels.csv", "sprint6", False),
    ("reports/elbow_plot.png", "sprint6", False),
    ("reports/correlation_heatmap.png", "sprint6", False),
    ("output/outlier_report.csv", "sprint6", False),
    ("output/portfolio_stats.csv", "sprint6", False),
    ("src/api", "sprint6", True),
    ("docs/openapi.json", "sprint6", False),
    ("docs/N100 Financial Intelligence Platform API.postman_collection.json", "sprint6", False),
    ("reports/pytest_report.html", "sprint6", False),
    ("docs/analyst_guide.pdf", "sprint6", False),
    ("output/perf_notes.md", "sprint6", False),  # flagged if missing, see check below
]


def main():
    os.makedirs(DEST_ROOT, exist_ok=True)

    manifest = []
    missing = []

    for src, sprint, is_dir in DELIVERABLES:
        dest_dir = os.path.join(DEST_ROOT, sprint)
        os.makedirs(dest_dir, exist_ok=True)
        basename = os.path.basename(src.rstrip("/"))
        dest = os.path.join(dest_dir, basename)

        if not os.path.exists(src):
            missing.append(src)
            continue

        if is_dir:
            if os.path.exists(dest):
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
            file_count = sum(len(files) for _, _, files in os.walk(dest))
            manifest.append(f"{sprint}/{basename}/  ({file_count} files)")
        else:
            shutil.copy2(src, dest)
            size_kb = os.path.getsize(dest) / 1024
            manifest.append(f"{sprint}/{basename}  ({size_kb:.1f} KB)")

    manifest_path = os.path.join(DEST_ROOT, "MANIFEST.txt")
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write("N100 Financial Intelligence Platform -- Final Deliverables Manifest\n")
        f.write("=" * 70 + "\n\n")
        f.write(
            f"Archived {len(manifest)} of {len(DELIVERABLES)} listed deliverables.\n"
        )
        f.write(
            "Note: the Sprint 6 spec states '23 deliverables' but no single\n"
            "itemized list of exactly 23 exists anywhere in this project's\n"
            "history. The real, confirmed deliverable set (this manifest) has\n"
            f"{len(DELIVERABLES)} distinct items across all 6 sprints -- likely because\n"
            "the spec bundles some multi-file outputs as single line items.\n"
            "Documented here rather than trimmed to force a match, consistent\n"
            "with this project's handling of the sector-count (10 vs 11) and\n"
            "tearsheet-count (91 vs 92) discrepancies.\n\n"
        )
        if missing:
            f.write(f"MISSING ({len(missing)}), not archived:\n")
            for m in missing:
                f.write(f"  - {m}\n")
            f.write("\n")
        f.write("Archived:\n")
        for line in manifest:
            f.write(f"  {line}\n")

    print(f"Archived {len(manifest)} of {len(DELIVERABLES)} deliverables to {DEST_ROOT}/")
    if missing:
        print(f"\nMISSING ({len(missing)}):")
        for m in missing:
            print(f"  - {m}")
    print(f"\nManifest written to {manifest_path}")


if __name__ == "__main__":
    main()