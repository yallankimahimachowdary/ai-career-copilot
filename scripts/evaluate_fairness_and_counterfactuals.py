"""
scripts/evaluate_fairness_and_counterfactuals.py
------------------------------------------------
Phase 7 Evaluation Runner: Fairness (Name-Swap Invariance), Counterfactual Interventions,
and Inference Performance Benchmarking.

Preserves frozen ranking weights (BM25: 0.10, SBERT: 0.10, overlap: 0.80).
Outputs machine-readable JSON and CSV with provenance, hashes, and statistical summaries.
Never overwrites existing evaluation artifacts.
"""

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.ranking.baselines import BM25Ranker, SbertRanker, SkillOverlapRanker
from app.ranking.counterfactual import CounterfactualTester
from app.ranking.fairness import NameSwapFairnessEvaluator
from app.ranking.hybrid import HybridRanker
from app.ranking.performance import PerformanceBenchmarkTracker, StageTimer
from scripts.job_snapshot import load_snapshot


def get_git_revision() -> str:
    """Retrieve current Git commit SHA safely."""
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
        return out.decode("utf-8").strip()
    except Exception:
        return "git_unknown"


def compute_file_sha256(filepath: str) -> str:
    """Compute SHA-256 hash of a file for dataset provenance."""
    if not os.path.exists(filepath):
        return "file_not_found"
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_synthetic_benchmark_resumes() -> List[Dict[str, Any]]:
    """Synthetic benchmark resumes with fixed skills and experiences for repeatable evaluation."""
    return [
        {
            "id": "bench_dev_01",
            "candidate_name": "Synthetic Candidate A",
            "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
            "experience": [
                {
                    "title": "Backend Engineer",
                    "company": "Alpha Tech",
                    "description": "Developed microservices with Python and FastAPI.",
                }
            ],
            "education": [{"degree": "B.S. Computer Science", "institution": "State University"}],
            "raw_text": "Experienced Python Backend Engineer with FastAPI, Docker, and PostgreSQL.",
        },
        {
            "id": "bench_ds_02",
            "candidate_name": "Synthetic Candidate B",
            "skills": ["Python", "Machine Learning", "SQL", "Pandas"],
            "experience": [
                {
                    "title": "Data Scientist",
                    "company": "Beta Analytics",
                    "description": "Trained machine learning models using Python and Pandas.",
                }
            ],
            "education": [{"degree": "M.S. Data Science", "institution": "Tech Institute"}],
            "raw_text": "Data Scientist skilled in Python, Machine Learning, SQL, and predictive modeling.",
        },
        {
            "id": "bench_front_03",
            "candidate_name": "Synthetic Candidate C",
            "skills": ["JavaScript", "React", "TypeScript", "HTML/CSS"],
            "experience": [
                {
                    "title": "Frontend Developer",
                    "company": "Gamma Web",
                    "description": "Built reactive interfaces with React and TypeScript.",
                }
            ],
            "education": [{"degree": "B.Tech Information Technology", "institution": "City University"}],
            "raw_text": "Frontend Developer with React, TypeScript, and modern CSS expertise.",
        },
    ]


def run_evaluation(
    snapshot_path: str = "data/snapshots/test_snap_1.json",
    seed: int = 42,
    repetitions: int = 1,
    output_dir: str = "artifacts/evaluation",
    export_csv: bool = True,
) -> Dict[str, Any]:
    """Execute complete Phase 7 evaluation cycle."""
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    git_rev = get_git_revision()
    snapshot_hash = compute_file_sha256(snapshot_path)

    # Load frozen ranking weights
    config_path = Path("app/ranking/config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    frozen_weights = cfg.get("weights", {"bm25": 0.1, "sbert": 0.1, "overlap": 0.8})
    config_hash = hashlib.sha256(json.dumps(frozen_weights, sort_keys=True).encode()).hexdigest()

    # Verify frozen weights have not been altered
    assert frozen_weights.get("bm25") == 0.1, "BM25 weight altered!"
    assert frozen_weights.get("sbert") == 0.1, "SBERT weight altered!"
    assert frozen_weights.get("overlap") == 0.8, "Overlap weight altered!"

    # Load job snapshot
    if os.path.exists(snapshot_path):
        records, _ = load_snapshot(snapshot_path)
        pool = records[:50]
    else:
        # Fallback synthetic pool for testing in environments without snapshot file
        pool = [
            {
                "id": f"job_synth_{i}",
                "title": title,
                "description": desc,
                "skills": skills,
                "company_name": "Tech Corp",
                "location": "Bengaluru",
            }
            for i, (title, desc, skills) in enumerate([
                ("Senior Python Engineer", "FastAPI, PostgreSQL, Kubernetes, Redis", ["Python", "FastAPI", "Docker", "Kubernetes"]),
                ("Data Scientist", "PyTorch, Machine Learning, Deep Learning, SQL", ["Python", "Machine Learning", "SQL", "PyTorch"]),
                ("Frontend Lead", "React, TypeScript, CSS, Node.js", ["JavaScript", "React", "TypeScript", "Node.js"]),
                ("DevOps Engineer", "Terraform, AWS, Docker, Kubernetes, CI/CD", ["AWS", "Docker", "Kubernetes", "Linux"]),
                ("Full Stack Developer", "Python, React, PostgreSQL, Docker", ["Python", "React", "PostgreSQL", "Docker"]),
            ])
        ]

    sbert = SbertRanker()
    hybrid = HybridRanker(sbert_ranker=sbert, weights=frozen_weights)
    bench_resumes = get_synthetic_benchmark_resumes()

    # -------------------------------------------------------------------------
    # 1. Counterfactual Ranking Evaluation
    # -------------------------------------------------------------------------
    cf_tester = CounterfactualTester(hybrid_ranker=hybrid, sbert_ranker=sbert, seed=seed)
    cf_cases: List[Dict[str, Any]] = []

    # Case 1: Python Dev missing Kubernetes and Redis
    cf_cases.append(
        cf_tester.evaluate_counterfactual_case(
            resume=bench_resumes[0],
            target_job=pool[0],
            job_pool=pool,
            suggested_skills=["Kubernetes", "Redis"],
            n_control_draws=10,
        )
    )

    # Case 2: Data Scientist missing PyTorch and Deep Learning
    cf_cases.append(
        cf_tester.evaluate_counterfactual_case(
            resume=bench_resumes[1],
            target_job=pool[1],
            job_pool=pool,
            suggested_skills=["PyTorch", "Deep Learning"],
            n_control_draws=10,
        )
    )

    # Case 3 (Exclusion rule test): Suggest skill candidate already has (Python)
    cf_cases.append(
        cf_tester.evaluate_counterfactual_case(
            resume=bench_resumes[0],
            target_job=pool[0],
            job_pool=pool,
            suggested_skills=["Python"],  # Already present!
            n_control_draws=10,
        )
    )

    cf_summary = CounterfactualTester.aggregate_counterfactual_evaluations(cf_cases)

    # -------------------------------------------------------------------------
    # 2. Fairness & Name-Swap Evaluation
    # -------------------------------------------------------------------------
    fairness_evaluator = NameSwapFairnessEvaluator(ranker=hybrid, seed=seed)
    fairness_summary = fairness_evaluator.evaluate_profiles_batch(
        resumes=bench_resumes,
        job_pool=pool,
    )

    # -------------------------------------------------------------------------
    # 3. Performance & Latency Benchmarking
    # -------------------------------------------------------------------------
    perf_tracker = PerformanceBenchmarkTracker(
        provider="local_hybrid",
        model="HybridRanker(BM25=0.1,SBERT=0.1,Overlap=0.8)",
        prompt_version="v1.0",
    )

    for rep in range(repetitions):
        stage_timer = StageTimer()
        with stage_timer.time_stage("full_ranking"):
            for res in bench_resumes:
                with stage_timer.time_stage("hybrid_scoring"):
                    hybrid.rank(res, pool, k=len(pool))

        total_lat = sum(stage_timer.stage_durations_ms.values())
        perf_tracker.record_run(
            total_latency_ms=total_lat,
            success=True,
            stage_latencies_ms=stage_timer.stage_durations_ms,
        )

    perf_summary = perf_tracker.compute_summary()

    # -------------------------------------------------------------------------
    # 4. Assemble Master Evaluation Report
    # -------------------------------------------------------------------------
    report: Dict[str, Any] = {
        "report_id": f"phase7_eval_{timestamp_str}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_revision": git_rev,
        "seed": seed,
        "repetitions": repetitions,
        "provenance": {
            "snapshot_path": snapshot_path,
            "snapshot_sha256": snapshot_hash,
            "config_sha256": config_hash,
            "frozen_ranking_weights": frozen_weights,
        },
        "counterfactual_evaluation": {
            "summary": cf_summary,
            "cases": cf_cases,
        },
        "fairness_evaluation": fairness_summary,
        "performance_benchmark": perf_summary,
    }

    # Save outputs safely
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / f"phase7_evaluation_report_{timestamp_str}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    if export_csv:
        csv_path = out_dir / f"phase7_counterfactual_cases_{timestamp_str}.csv"
        flat_records = []
        for c in cf_cases:
            for ind in c.get("individual_evaluations", []):
                flat_records.append({
                    "candidate_id": c.get("candidate_id"),
                    "job_id": c.get("job_id"),
                    "intervention_type": "individual",
                    "skill": ind["skill"],
                    "baseline_score": ind["baseline_score"],
                    "counterfactual_score": ind["counterfactual_score"],
                    "score_delta": ind["score_delta"],
                    "rank_gain": ind["rank_gain"],
                    "control_score_delta_mean": ind["control_score_delta_mean"],
                    "lift_over_control_score": ind["lift_over_control_score"],
                })
        if flat_records:
            cf_tester.export_csv(flat_records, csv_path)

    return report


def main():
    parser = argparse.ArgumentParser(description="Phase 7: Fairness, Counterfactual & Performance Evaluation")
    parser.add_argument("--snapshot", type=str, default="data/snapshots/test_snap_1.json", help="Path to job snapshot JSON")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--repetitions", type=int, default=3, help="Benchmark repetitions")
    parser.add_argument("--output-dir", type=str, default="artifacts/evaluation", help="Directory to save report artifacts")
    parser.add_argument("--export-csv", action="store_true", default=True, help="Export counterfactual CSV")

    args = parser.parse_args()
    report = run_evaluation(
        snapshot_path=args.snapshot,
        seed=args.seed,
        repetitions=args.repetitions,
        output_dir=args.output_dir,
        export_csv=args.export_csv,
    )
    print("\n[SUCCESS] Phase 7 Evaluation completed successfully.")
    print(f"Report ID: {report['report_id']}")
    print(f"Valid Counterfactual Cases: {report['counterfactual_evaluation']['summary'].get('valid_cases')}")
    print(f"Excluded Counterfactual Cases: {report['counterfactual_evaluation']['summary'].get('excluded_cases')}")
    print(f"Fairness Name Invariance Rate: {report['fairness_evaluation'].get('aggregate_score_invariance_rate')}")
    print(f"Mean Latency (ms): {report['performance_benchmark']['latency_summary_ms'].get('mean_ms')}")


if __name__ == "__main__":
    main()
