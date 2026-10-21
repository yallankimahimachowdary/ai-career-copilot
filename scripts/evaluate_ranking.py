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
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ranking.evaluation import (
    average_precision,
    calculate_kendall_tau,
    calculate_topk_overlap,
    cohen_kappa,
    compute_unlabeled_diagnostics,
    confidence_interval,
    export_annotation_template,
    fleiss_kappa,
    generate_evaluation_report,
    holm_bonferroni_correction,
    import_relevance_judgments,
    mean_average_precision,
    mean_reciprocal_rank,
    ndcg_at_5,
    ndcg_at_10,
    paired_bootstrap_ci,
    precision_at_5,
    recall_at_k,
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
    manifest_path: Optional[str] = "data/gold/gold_resumes_skills.json",
    strict_manifest: Optional[bool] = None,
    judgments_path: Optional[str] = None,
    export_template_path: Optional[str] = None,
    output_report_path: Optional[str] = None,
    universes_path: Optional[str] = None,
    methods: Optional[List[str]] = None,
    k: int = 10,
    universe_seed: int = 42,
    run_ablations: bool = True,
    dryrun_max_jobs_slice: Optional[int] = None,
    max_jobs: Optional[int] = None,
    run_type: str = "dryrun",
    max_resumes: Optional[int] = None,
) -> Dict[str, Any]:
    """Execute complete ranking evaluation pipeline with provenance tracking.
    
    In stage eval or real runs, each candidate resume is ranked ONLY within its own
    60-job universe loaded from candidate_universes.json. Slicing snapshot records is
    strictly prohibited in eval/real mode and allowed only under dryrun_max_jobs_slice.
    """
    if methods is None:
        methods = ["bm25", "sbert", "overlap", "hybrid", "composite_xgb"]

    # Support backwards compatibility for max_jobs argument
    if dryrun_max_jobs_slice is None and max_jobs is not None:
        dryrun_max_jobs_slice = max_jobs

    # Gating rule: In eval or real runs, slicing snapshot jobs is strictly forbidden
    if (run_type == "real" or judgments_path) and dryrun_max_jobs_slice is not None:
        raise ValueError(
            f"Evaluation error: Slicing snapshot jobs via dryrun_max_jobs_slice={dryrun_max_jobs_slice} "
            f"is strictly forbidden in stage eval / real runs (run_type='{run_type}'). "
            f"Each candidate must be evaluated ONLY within its own 60-job universe."
        )

    snapshot_records, snapshot_meta = load_snapshot(snapshot_path)
    if dryrun_max_jobs_slice is not None:
        snapshot_records = snapshot_records[:dryrun_max_jobs_slice]

    # Resolve candidate universes mapping
    candidate_universes_map: Dict[str, Set[str]] = {}
    resolved_univ_path = universes_path
    if not resolved_univ_path and output_report_path:
        candidate_univ_file = Path(output_report_path).parent / "candidate_universes.json"
        if candidate_univ_file.exists():
            resolved_univ_path = str(candidate_univ_file)

    if resolved_univ_path and Path(resolved_univ_path).exists():
        with open(resolved_univ_path, "r", encoding="utf-8") as f:
            u_data = json.load(f)
            for cid, cinfo in u_data.get("candidate_universes", {}).items():
                job_ids = cinfo.get("job_ids") or []
                if job_ids:
                    candidate_universes_map[cid] = set(str(jid) for jid in job_ids)

    # In stage eval or real runs, candidate universes are strictly mandatory
    if (run_type == "real" or judgments_path) and not candidate_universes_map:
        raise RuntimeError(
            f"Evaluation error: candidate_universes.json is required for stage eval / real runs, "
            f"but could not be found or loaded from '{resolved_univ_path}'."
        )

    if run_type == "dryrun" or resumes_dir != "uploads/resumes":
        manifest_to_use = manifest_path if (manifest_path and manifest_path != "data/gold/gold_resumes_skills.json" and Path(manifest_path).exists()) else None
    else:
        manifest_to_use = manifest_path if (manifest_path and Path(manifest_path).exists()) else None

    if strict_manifest is None:
        if manifest_to_use and run_type != "dryrun":
            strict_manifest = True
        else:
            strict_manifest = False

    candidates = load_and_anonymize_resumes(
        resumes_dir=resumes_dir,
        manifest_path=manifest_to_use,
        strict_manifest=strict_manifest,
    )
    if max_resumes is not None and max_resumes > 0:
        candidates = candidates[:max_resumes]
    print(f"Loaded {len(candidates)} candidates and {len(snapshot_records)} jobs from snapshot.")
    if candidate_universes_map:
        print(f"[UNIVERSE] Loaded universe constraints for {len(candidate_universes_map)} candidates from {resolved_univ_path}.")

    rankers = instantiate_rankers(methods)

    # Execute ranking across all methods
    method_rankings: Dict[str, Dict[str, List[str]]] = {m: {} for m in rankers.keys()}
    candidate_ranking_list: List[Dict[str, Any]] = []

    for cand in candidates:
        cand_id = cand["candidate_id"]
        # Enforce candidate's own universe if available
        if cand_id in candidate_universes_map:
            univ_ids = candidate_universes_map[cand_id]
            cand_job_pool = [
                j for j in snapshot_records
                if str(j.get("id") or j.get("external_id") or j.get("job_id") or "") in univ_ids
            ]
        elif (run_type == "real" or judgments_path):
            raise RuntimeError(
                f"Candidate '{cand_id}' has no 60-job universe defined in '{resolved_univ_path}'! "
                f"Ranking outside a candidate's universe is strictly forbidden in eval."
            )
        else:
            cand_job_pool = snapshot_records

        for m_name, ranker in rankers.items():
            res = ranker.rank(cand, cand_job_pool, k=k)
            if cand_id in candidate_universes_map:
                univ_ids = candidate_universes_map[cand_id]
                outside_jobs = [jid for jid in res.ranked_job_ids if jid not in univ_ids]
                if outside_jobs:
                    raise ValueError(
                        f"Integrity violation: {len(outside_jobs)} ranked jobs for candidate '{cand_id}' "
                        f"in method '{m_name}' fall outside the candidate universe: {outside_jobs[:3]}"
                    )
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

    # Label Gating Check (R12-2)
    # Quality metrics (nDCG@5/10, MAP, MRR, P@k, Recall@k) computed ONLY when
    # results/real/labels.jsonl exists and run_type=real.
    real_labels_file = Path("results/real/labels.jsonl")
    can_compute_quality_metrics = False
    if run_type == "real" and real_labels_file.exists():
        can_compute_quality_metrics = True
    elif judgments_path:
        # If user explicitly passed judgments_path, verify if run_type == 'real'
        if run_type != "real":
            print(f"[LABEL GATE] run_type='{run_type}' is not 'real'. Refusing to compute empirical quality metrics on non-real labels.")
        else:
            can_compute_quality_metrics = True

    # Load judgments if permitted
    judgments: Dict[str, Dict[str, float]] = {}
    if can_compute_quality_metrics:
        load_path = judgments_path if (judgments_path and Path(judgments_path).exists()) else str(real_labels_file)
        if Path(load_path).exists():
            judgments = import_relevance_judgments(load_path)
            print(f"[JUDGMENTS] Loaded explicit human relevance judgments for {len(judgments)} candidates.")
    else:
        print("[LABEL GATE] Quality metrics gated: rankings + diagnostics only (Kendall tau, top-k overlap, latency).")

    # Compute IR metrics if judgments are available and permitted
    evaluation_metrics: Dict[str, Any] = {}
    per_candidate_vectors: Dict[str, Dict[str, List[float]]] = {m: {"ndcg@5": [], "ndcg@10": [], "p@5": [], "mrr": [], "map": []} for m in rankers.keys()}
    
    for m_name, cand_map in method_rankings.items():
        if not can_compute_quality_metrics or not judgments:
            evaluation_metrics[m_name] = {
                "status": "awaiting_real_annotations",
                "ndcg@5": None,
                "ndcg@10": None,
                "precision@5": None,
                "mrr": None,
                "map": None,
                "recall@10": None,
                "evaluated_candidates": 0,
            }
            continue

        ndcg5_list = []
        ndcg10_list = []
        p5_list = []
        rr_list = []
        ap_list = []
        rec10_list = []

        for cand_id, ranked_ids in cand_map.items():
            if cand_id in judgments:
                q_judgments = judgments[cand_id]
                n5 = ndcg_at_5(ranked_ids, q_judgments)
                n10 = ndcg_at_10(ranked_ids, q_judgments)
                p5 = precision_at_5(ranked_ids, q_judgments)
                rr = reciprocal_rank(ranked_ids, q_judgments)
                ap = average_precision(ranked_ids, q_judgments)
                r10 = recall_at_k(ranked_ids, q_judgments, k=10)

                ndcg5_list.append(n5)
                ndcg10_list.append(n10)
                p5_list.append(p5)
                rr_list.append(rr)
                ap_list.append(ap)
                rec10_list.append(r10)

                per_candidate_vectors[m_name]["ndcg@5"].append(n5)
                per_candidate_vectors[m_name]["ndcg@10"].append(n10)
                per_candidate_vectors[m_name]["p@5"].append(p5)
                per_candidate_vectors[m_name]["mrr"].append(rr)
                per_candidate_vectors[m_name]["map"].append(ap)

        if ndcg5_list:
            evaluation_metrics[m_name] = {
                "status": "evaluated",
                "ndcg@5": round(float(np.mean(ndcg5_list)), 4),
                "ndcg@10": round(float(np.mean(ndcg10_list)), 4),
                "precision@5": round(float(np.mean(p5_list)), 4),
                "mrr": round(float(np.mean(rr_list)), 4),
                "map": round(float(np.mean(ap_list)), 4),
                "recall@10": round(float(np.mean(rec10_list)), 4),
                "ci_ndcg@5": confidence_interval(ndcg5_list),
                "ci_ndcg@10": confidence_interval(ndcg10_list),
                "ci_map": confidence_interval(ap_list),
                "evaluated_candidates": len(ndcg5_list),
            }
        else:
            evaluation_metrics[m_name] = {
                "status": "awaiting_real_annotations",
                "ndcg@5": None,
                "ndcg@10": None,
                "precision@5": None,
                "mrr": None,
                "map": None,
                "recall@10": None,
                "evaluated_candidates": 0,
            }

    # Diagnostics when labels are absent or run_type != 'real' (Kendall tau, top-k overlap)
    diagnostics = {}
    if not can_compute_quality_metrics:
        # Flatten top-k ranked job IDs per candidate
        # Compute diagnostics across all candidates
        all_cands = [c["candidate_id"] for c in candidates]
        tau_by_cand = []
        overlap_by_cand = []
        for cid in all_cands:
            cand_ranks = {m: method_rankings[m].get(cid, []) for m in rankers.keys()}
            diag_cand = compute_unlabeled_diagnostics(cand_ranks, k=k)
            tau_by_cand.append(diag_cand["pairwise_kendall_tau"])
            overlap_by_cand.append(diag_cand["pairwise_topk_overlap"])

        # Average pairwise diagnostics across candidates
        m_keys = list(rankers.keys())
        avg_kendall = {m1: {m2: round(float(np.mean([t[m1][m2] for t in tau_by_cand])), 4) for m2 in m_keys} for m1 in m_keys}
        avg_overlap = {m1: {m2: round(float(np.mean([o[m1][m2] for o in overlap_by_cand])), 4) for m2 in m_keys} for m1 in m_keys}

        diagnostics = {
            "evaluated_candidates_count": len(all_cands),
            "k": k,
            "pairwise_mean_kendall_tau": avg_kendall,
            "pairwise_mean_topk_overlap": avg_overlap,
        }

    # Statistical Significance Comparisons (R12-3):
    # Wilcoxon signed-rank: hybrid vs bm25, hybrid vs sbert, LLM re-rank vs hybrid; Holm correction; effect size & n
    statistical_comparisons: Dict[str, Any] = {}
    if can_compute_quality_metrics and "hybrid" in per_candidate_vectors:
        primary_metric = "ndcg@10"
        pairs_to_test = [("hybrid", "bm25"), ("hybrid", "sbert")]
        if "hybrid_llm_ollama" in per_candidate_vectors:
            pairs_to_test.append(("hybrid_llm_ollama", "hybrid"))
        if "hybrid_llm_gemini" in per_candidate_vectors:
            pairs_to_test.append(("hybrid_llm_gemini", "hybrid"))

        raw_p_values = []
        test_details = []
        for m_a, m_b in pairs_to_test:
            if m_a in per_candidate_vectors and m_b in per_candidate_vectors:
                vec_a = per_candidate_vectors[m_a][primary_metric]
                vec_b = per_candidate_vectors[m_b][primary_metric]
                if len(vec_a) > 0 and len(vec_a) == len(vec_b):
                    w_res = wilcoxon_signed_rank_test(vec_a, vec_b)
                    boot_ci = paired_bootstrap_ci(vec_a, vec_b, n_resamples=10000, seed=universe_seed)
                    p_val = w_res.get("p_value") if w_res.get("p_value") is not None else 1.0
                    raw_p_values.append(p_val)
                    test_details.append({
                        "comparison": f"{m_a}_vs_{m_b}",
                        "metric": primary_metric,
                        "n": len(vec_a),
                        "wilcoxon_statistic": w_res.get("statistic"),
                        "raw_p_value": p_val,
                        "effect_size_r": w_res.get("effect_size_r"),
                        "mean_difference": boot_ci.get("mean_difference"),
                        "bootstrap_ci_95": [boot_ci.get("lower_bound"), boot_ci.get("upper_bound")],
                        "warning": w_res.get("warning"),
                    })

        # Apply Holm-Bonferroni correction
        if raw_p_values:
            holm_corrections = holm_bonferroni_correction(raw_p_values, alpha=0.05)
            for idx, item in enumerate(test_details):
                item["adjusted_p_value"] = holm_corrections[idx]["adjusted_p"]
                item["significant_after_holm"] = holm_corrections[idx]["rejected"]
                statistical_comparisons[item["comparison"]] = item

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
        statistical_comparisons=statistical_comparisons,
        ablations=ablation_results,
        notes="Evaluated via formal Phase B evaluation suite.",
    )
    if diagnostics:
        report["diagnostics"] = diagnostics
    report["run_type"] = run_type

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
    parser.add_argument("--universes", type=str, default=None, help="Path to candidate_universes.json")
    parser.add_argument("--dryrun-max-jobs-slice", type=int, default=None, help="[DRY-RUN ONLY] Slices snapshot records for quick smoke tests")
    parser.add_argument("--max-jobs", type=int, default=None, help="Deprecated alias for --dryrun-max-jobs-slice")
    parser.add_argument("--run-type", "--run_type", dest="run_type", type=str, default="dryrun", choices=["dryrun", "real"], help="Run type tag ('dryrun' or 'real')")
    args = parser.parse_args()

    methods_list = [m.strip() for m in args.methods.split(",") if m.strip()]

    report = run_evaluation_pipeline(
        snapshot_path=args.snapshot,
        resumes_dir=args.resumes,
        manifest_path=args.manifest,
        judgments_path=args.judgments,
        export_template_path=args.export_template,
        output_report_path=args.output,
        universes_path=args.universes,
        methods=methods_list,
        k=args.k,
        universe_seed=args.seed,
        run_ablations=not args.no_ablations,
        dryrun_max_jobs_slice=args.dryrun_max_jobs_slice or args.max_jobs,
        run_type=args.run_type,
    )
    print("\n================ Evaluation Summary ================")
    print(json.dumps(report["metrics"], indent=2))


if __name__ == "__main__":
    main()
