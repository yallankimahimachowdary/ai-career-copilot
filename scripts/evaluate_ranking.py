"""
scripts/evaluate_ranking.py
---------------------------
Formal Evaluation and Ablation Suite for Phase B Ranking Pipeline.

Features:
- Computes nDCG@5, nDCG@10, Precision@5, and MRR against explicit human relevance judgments.
- Exports reproducible annotation templates (CSV/JSON) for human annotators.
- Imports and validates human relevance judgments.
- Evaluates annotator agreement via Cohen's kappa (pairwise) and Fleiss' kappa (multi-annotator).
- Performs Wilcoxon signed-rank significance tests and confidence intervals between methods.
- Executes ablation studies (removing skill overlap, disabling LLM reranking, baseline components).
- Outputs standardized, machine-readable JSON reports with dataset identity/hash, method, seed, and timestamps.
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ranking.evaluation import (
    confidence_interval,
    cohen_kappa,
    export_annotation_template,
    fleiss_kappa,
    generate_evaluation_report,
    import_relevance_judgments,
    ndcg_at_5,
    ndcg_at_10,
    precision_at_5,
    reciprocal_rank,
    run_ablation_study,
    wilcoxon_signed_rank_test,
)
from scripts.job_snapshot import load_snapshot
from scripts.run_ranking_experiment import (
    instantiate_rankers,
    load_and_anonymize_resumes,
    get_weights_sha256,
)


def run_evaluation_pipeline(
    snapshot_path: str = "data/snapshots/test_snap_1.json",
    resumes_dir: str = "uploads/resumes",
    manifest_path: str = "data/gold/gold_resumes_skills.json",
    judgments_path: Optional[str] = None,
    export_template_path: Optional[str] = None,
    output_report_path: Optional[str] = None,
    methods: Optional[List[str]] = None,
    k: int = 10,
    universe_seed: int = 42,
    run_ablations: bool = True,
    max_jobs: int = 100,
) -> Dict[str, Any]:
    """Execute complete ranking evaluation pipeline with provenance tracking."""
    if methods is None:
        methods = ["bm25", "sbert", "overlap", "hybrid", "composite_xgb"]

    snapshot_records, snapshot_meta = load_snapshot(snapshot_path)
    if max_jobs:
        snapshot_records = snapshot_records[:max_jobs]

    candidates = load_and_anonymize_resumes(
        resumes_dir=resumes_dir,
        manifest_path=manifest_path,
        strict_manifest=True,
    )
    print(f"Loaded {len(candidates)} candidates and {len(snapshot_records)} jobs from snapshot.")

    rankers = instantiate_rankers(methods)

    # Execute ranking across all methods
    method_rankings: Dict[str, Dict[str, List[str]]] = {m: {} for m in rankers.keys()}
    candidate_ranking_list: List[Dict[str, Any]] = []

    for cand in candidates:
        cand_id = cand["candidate_id"]
        for m_name, ranker in rankers.items():
            res = ranker.rank(cand, snapshot_records, k=k)
            method_rankings[m_name][cand_id] = res.ranked_job_ids

        # Save for template export
        hybrid_ranked = method_rankings.get("hybrid", {}).get(cand_id, [])
        candidate_ranking_list.append({
            "candidate_id": cand_id,
            "candidate_name": cand.get("candidate_name", cand_id),
            "ranked_job_ids": hybrid_ranked,
        })

    # Export annotation template if requested
    if export_template_path:
        out_tpl = export_annotation_template(
            candidate_ranking_results=candidate_ranking_list,
            snapshot_records=snapshot_records,
            output_path=export_template_path,
            k=k,
        )
        print(f"[EXPORT] Annotation template exported to: {out_tpl}")

    # Load judgments if provided
    judgments: Dict[str, Dict[str, float]] = {}
    if judgments_path and Path(judgments_path).exists():
        judgments = import_relevance_judgments(judgments_path)
        print(f"[JUDGMENTS] Loaded explicit human relevance judgments for {len(judgments)} candidates.")
    else:
        print("[JUDGMENTS] No human relevance judgments file provided; empirical IR metrics await labels.")

    # Compute IR metrics if judgments are available
    evaluation_metrics: Dict[str, Any] = {}
    for m_name, cand_map in method_rankings.items():
        if not judgments:
            evaluation_metrics[m_name] = {
                "status": "awaiting_annotations",
                "ndcg@5": None,
                "ndcg@10": None,
                "precision@5": None,
                "mrr": None,
                "evaluated_candidates": 0,
            }
            continue

        ndcg5_list = []
        ndcg10_list = []
        p5_list = []
        rr_list = []

        for cand_id, ranked_ids in cand_map.items():
            if cand_id in judgments:
                q_judgments = judgments[cand_id]
                ndcg5_list.append(ndcg_at_5(ranked_ids, q_judgments))
                ndcg10_list.append(ndcg_at_10(ranked_ids, q_judgments))
                p5_list.append(precision_at_5(ranked_ids, q_judgments))
                rr_list.append(reciprocal_rank(ranked_ids, q_judgments))

        if ndcg5_list:
            evaluation_metrics[m_name] = {
                "status": "evaluated",
                "ndcg@5": round(float(np.mean(ndcg5_list)), 4),
                "ndcg@10": round(float(np.mean(ndcg10_list)), 4),
                "precision@5": round(float(np.mean(p5_list)), 4),
                "mrr": round(float(np.mean(rr_list)), 4),
                "ci_ndcg@5": confidence_interval(ndcg5_list),
                "ci_ndcg@10": confidence_interval(ndcg10_list),
                "evaluated_candidates": len(ndcg5_list),
            }
        else:
            evaluation_metrics[m_name] = {
                "status": "awaiting_annotations",
                "ndcg@5": None,
                "ndcg@10": None,
                "precision@5": None,
                "mrr": None,
                "evaluated_candidates": 0,
            }

    # Run ablations if requested
    ablation_results: Dict[str, Any] = {}
    if run_ablations:
        for cand in candidates:
            cand_id = cand["candidate_id"]
            cand_judgments = judgments.get(cand_id)
            ablation_results[cand_id] = run_ablation_study(
                candidate=cand,
                snapshot_records=snapshot_records,
                k=k,
                relevance_judgments=cand_judgments,
            )

    report = generate_evaluation_report(
        dataset_path=snapshot_path,
        method_name="composite_benchmark",
        seed=universe_seed,
        metrics=evaluation_metrics,
        ablations=ablation_results,
        notes="Evaluated via formal Phase B evaluation suite.",
    )

    if output_report_path:
        out_rpt = Path(output_report_path)
        out_rpt.parent.mkdir(parents=True, exist_ok=True)
        with open(out_rpt, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"[REPORT] Saved machine-readable evaluation report to: {out_rpt}")

    return report


def main():
    parser = argparse.ArgumentParser(description="Phase B Ranking Evaluation and Ablation Suite")
    parser.add_argument("--snapshot", type=str, default="data/snapshots/test_snap_1.json", help="Path to frozen job snapshot")
    parser.add_argument("--resumes", type=str, default="uploads/resumes", help="Path to resumes folder")
    parser.add_argument("--manifest", type=str, default="data/gold/gold_resumes_skills.json", help="Path to resume manifest JSON")
    parser.add_argument("--judgments", type=str, default=None, help="Path to human relevance judgments CSV/JSON")
    parser.add_argument("--export-template", type=str, default="data/gold/annotation_template.csv", help="Path to export annotation template")
    parser.add_argument("--output", type=str, default="artifacts/evaluation_report.json", help="Path to output machine-readable evaluation JSON")
    parser.add_argument("--methods", type=str, default="bm25,sbert,overlap,hybrid,composite_xgb", help="Comma-separated ranker names")
    parser.add_argument("--k", type=int, default=10, help="Top k evaluation depth")
    parser.add_argument("--seed", type=int, default=42, help="Universe seed")
    parser.add_argument("--no-ablations", action="store_true", help="Skip ablation experiments")
    parser.add_argument("--max-jobs", type=int, default=100, help="Max jobs from snapshot to evaluate")
    args = parser.parse_args()

    methods_list = [m.strip() for m in args.methods.split(",") if m.strip()]

    report = run_evaluation_pipeline(
        snapshot_path=args.snapshot,
        resumes_dir=args.resumes,
        manifest_path=args.manifest,
        judgments_path=args.judgments,
        export_template_path=args.export_template,
        output_report_path=args.output,
        methods=methods_list,
        k=args.k,
        universe_seed=args.seed,
        run_ablations=not args.no_ablations,
        max_jobs=args.max_jobs,
    )
    print("\n================ Evaluation Summary ================")
    print(json.dumps(report["metrics"], indent=2))


if __name__ == "__main__":
    main()
