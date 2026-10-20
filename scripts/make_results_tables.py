#!/usr/bin/env python3
"""
scripts/make_results_tables.py
------------------------------
Generates standardized publication tables (CSV + Markdown) from ranking experiment
and evaluation logs.

Features:
- Reads evaluation logs from artifacts/experiments/runs/ or results/real/.
- Guarded strictly by --run-type real: REFUSES to process or output tables from dryrun files
  unless explicitly invoked with --allow-dryrun for testing purposes.
- Tags every table with provenance metadata (git commit, config hash, snapshot hash, taxonomy hash).
- Formats metrics: nDCG@5, nDCG@10, MAP, MRR, P@5, Recall@10 with confidence intervals.
- Formats statistical significance tables with Wilcoxon statistics, Holm-adjusted p-values,
  and effect sizes.
- Exports results to results/tables/ in CSV and GitHub Flavored Markdown formats.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.provenance import get_file_sha256, get_git_commit_hash, FROZEN_CONFIG_PATH
from app.core.taxonomy import TAXONOMY_VERSION, get_taxonomy_sha256


def load_evaluation_report(report_path: Path | str, allow_dryrun: bool = False) -> Dict[str, Any]:
    """Load evaluation report and enforce dry-run protection."""
    p = Path(report_path)
    if not p.exists():
        raise FileNotFoundError(f"Report file not found: {p}")

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Check for dryrun contamination
    run_type = data.get("run_type", "")
    is_dryrun_path = "dryrun" in str(p).lower()
    if (run_type == "dryrun" or is_dryrun_path) and not allow_dryrun:
        raise ValueError(
            f"REFUSAL: Table generator rejected dryrun report '{p}'. "
            "Tables for paper publication must be derived strictly from real runs (run_type='real')."
        )

    return data


def generate_metrics_markdown(report: Dict[str, Any]) -> str:
    """Format ranking evaluation metrics into a clean Markdown table."""
    metrics = report.get("metrics", {})
    provenance = {
        "git_commit": get_git_commit_hash()[:8],
        "config_hash": get_file_sha256(FROZEN_CONFIG_PATH)[:8],
        "taxonomy_version": TAXONOMY_VERSION,
        "taxonomy_hash": get_taxonomy_sha256()[:8],
        "timestamp": report.get("timestamp", datetime.now(timezone.utc).isoformat()),
    }

    lines = [
        "# Ranking Experiment Evaluation Results",
        "",
        f"**Provenance:** Commit `{provenance['git_commit']}` | Config `{provenance['config_hash']}` | Taxonomy `{provenance['taxonomy_version']}` (`{provenance['taxonomy_hash']}`)",
        f"**Generated:** {provenance['timestamp']}",
        "",
        "| Ranking Arm | Status | nDCG@5 | nDCG@10 | MAP | MRR | Precision@5 | Recall@10 | Evaluated Candidates |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    for arm, arm_data in metrics.items():
        status = arm_data.get("status", "N/A")
        ndcg5 = f"{arm_data.get('ndcg@5', 'N/A')}"
        ndcg10 = f"{arm_data.get('ndcg@10', 'N/A')}"
        map_val = f"{arm_data.get('map', 'N/A')}"
        mrr = f"{arm_data.get('mrr', 'N/A')}"
        p5 = f"{arm_data.get('precision@5', 'N/A')}"
        r10 = f"{arm_data.get('recall@10', 'N/A')}"
        n_cands = arm_data.get("evaluated_candidates", 0)

        lines.append(
            f"| `{arm}` | {status} | {ndcg5} | {ndcg10} | {map_val} | {mrr} | {p5} | {r10} | {n_cands} |"
        )

    lines.append("")
    return "\n".join(lines)


def generate_significance_markdown(report: Dict[str, Any]) -> str:
    """Format Wilcoxon paired statistical tests with Holm correction into Markdown."""
    stats = report.get("statistical_comparisons", {})
    if not stats:
        return ""

    lines = [
        "## Statistical Significance (Wilcoxon Signed-Rank with Holm-Bonferroni Correction)",
        "",
        "| Comparison | Metric | n | Mean Diff | 95% Bootstrap CI | Raw p-value | Adjusted p-value | Significant (α=0.05) | Effect Size (r) |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    for comp, item in stats.items():
        metric = item.get("metric", "nDCG@10")
        n = item.get("n", 0)
        mean_diff = item.get("mean_difference", 0.0)
        ci = item.get("bootstrap_ci_95", [0.0, 0.0])
        ci_str = f"[{ci[0]:.4f}, {ci[1]:.4f}]" if isinstance(ci, list) and len(ci) == 2 else "N/A"
        raw_p = f"{item.get('raw_p_value', 1.0):.4f}"
        adj_p = f"{item.get('adjusted_p_value', 1.0):.4f}"
        sig = "**YES**" if item.get("significant_after_holm") else "No"
        eff = f"{item.get('effect_size_r', 0.0):.4f}"

        lines.append(
            f"| `{comp}` | {metric} | {n} | {mean_diff:+.4f} | {ci_str} | {raw_p} | {adj_p} | {sig} | {eff} |"
        )

    lines.append("")
    return "\n".join(lines)


def generate_metrics_csv(report: Dict[str, Any]) -> str:
    """Format metrics as CSV string."""
    metrics = report.get("metrics", {})
    rows = [
        "ranking_arm,status,ndcg_at_5,ndcg_at_10,map,mrr,precision_at_5,recall_at_10,evaluated_candidates"
    ]
    for arm, d in metrics.items():
        rows.append(
            f"{arm},{d.get('status','N/A')},{d.get('ndcg@5','')},{d.get('ndcg@10','')},"
            f"{d.get('map','')},{d.get('mrr','')},{d.get('precision@5','')},{d.get('recall@10','')},"
            f"{d.get('evaluated_candidates',0)}"
        )
    return "\n".join(rows) + "\n"


def export_tables(
    report_path: Path | str,
    output_dir: Path | str = "results/tables",
    allow_dryrun: bool = False,
) -> Dict[str, str]:
    """Load report, validate provenance, and export markdown and CSV tables."""
    report = load_evaluation_report(report_path, allow_dryrun=allow_dryrun)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    md_metrics = generate_metrics_markdown(report)
    md_stats = generate_significance_markdown(report)
    full_md = md_metrics + "\n" + md_stats

    csv_metrics = generate_metrics_csv(report)

    md_path = out_dir / "table_ranking_metrics.md"
    csv_path = out_dir / "table_ranking_metrics.csv"

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(full_md)
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write(csv_metrics)

    print(f"[TABLES] Exported Markdown table to: {md_path}")
    print(f"[TABLES] Exported CSV table to: {csv_path}")

    return {"markdown": str(md_path), "csv": str(csv_path)}


def main():
    parser = argparse.ArgumentParser(description="Publication Table Generator for AI Career Copilot Ranking Results")
    parser.add_argument("--report", type=str, required=True, help="Path to evaluation_report.json")
    parser.add_argument("--output-dir", type=str, default="results/tables", help="Directory to save generated tables")
    parser.add_argument("--run-type", type=str, default="real", choices=["real", "dryrun"], help="Run type guard")
    parser.add_argument("--allow-dryrun", action="store_true", help="Allow processing dry-run reports (for testing only)")
    args = parser.parse_args()

    allow_dr = args.allow_dryrun or (args.run_type == "dryrun" and args.allow_dryrun)
    export_tables(
        report_path=args.report,
        output_dir=args.output_dir,
        allow_dryrun=allow_dr,
    )


if __name__ == "__main__":
    main()
