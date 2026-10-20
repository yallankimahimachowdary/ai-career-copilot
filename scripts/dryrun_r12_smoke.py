"""
scripts/dryrun_r12_smoke.py
---------------------------
Dry-run smoke test runner for R12:
- Evaluates 6 in-scope synthetic resumes (2 Data/AI, 2 Web/Software, 2 Cybersecurity/Cloud)
  across non-LLM arms: bm25, sbert, overlap, hybrid.
- Evaluates 2 resumes across hybrid_llm_ollama.
- Records ranking outputs, wall-clock latency, top-k overlap, and pairwise rank correlation (Kendall tau).
- Strictly enforces run_type=dryrun and zero quality metrics without real labels.
- Outputs diagnostics table to stdout and saves JSON report in results/dryrun/r12_smoke/.
"""

import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ranking.evaluation import (
    calculate_kendall_tau,
    calculate_topk_overlap,
    compute_unlabeled_diagnostics,
)
from scripts.job_snapshot import load_snapshot
from scripts.run_ranking_experiment import (
    instantiate_rankers,
    load_and_anonymize_resumes,
    get_weights_sha256,
)


def run_r12_dryrun_smoke():
    output_dir = Path("results/dryrun/r12_smoke")
    output_dir.mkdir(parents=True, exist_ok=True)

    snapshot_path = "data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl"
    snapshot_records, snapshot_meta = load_snapshot(snapshot_path)
    # Target 60-job universe or full snapshot
    test_jobs = snapshot_records[:60]

    all_candidates = load_and_anonymize_resumes(
        resumes_dir="data/resumes_dryrun",
        strict_manifest=False,
    )
    cand_by_id = {c["candidate_id"]: c for c in all_candidates}

    # 6 selected in-scope resumes: 2 Data/AI, 2 Web/Software, 2 Cybersecurity/Cloud
    non_llm_cands = ["SYN_001", "SYN_002", "SYN_015", "SYN_018", "SYN_027", "SYN_028"]
    llm_cands = ["SYN_001", "SYN_015"]

    non_llm_methods = ["bm25", "sbert", "overlap", "hybrid"]
    rankers_non_llm = instantiate_rankers(non_llm_methods)

    print("================ R12 DRY-RUN SMOKE TEST ================")
    print(f"Non-LLM candidates (6): {non_llm_cands}")
    print(f"Non-LLM arms: {non_llm_methods}")
    print(f"Jobs pool: {len(test_jobs)} jobs from Snapshot 1")

    # Run non-LLM arms
    results_by_cand: Dict[str, Dict[str, List[str]]] = {cid: {} for cid in non_llm_cands}
    latency_by_cand: Dict[str, Dict[str, float]] = {cid: {} for cid in non_llm_cands}

    for cid in non_llm_cands:
        cand = cand_by_id[cid]
        for m_name, ranker in rankers_non_llm.items():
            t0 = time.perf_counter()
            res = ranker.rank(cand, test_jobs, k=10)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            results_by_cand[cid][m_name] = res.ranked_job_ids
            latency_by_cand[cid][m_name] = elapsed_ms

    # Run LLM arm on 2 candidates (1 pass each, plus K=2 stability evaluated on 1 candidate)
    print(f"\nRunning Ollama LLM arm on {llm_cands}...")
    rankers_llm = instantiate_rankers(["hybrid_llm_ollama"])
    ollama_ranker = rankers_llm["hybrid_llm_ollama"]

    llm_results_by_cand: Dict[str, List[List[str]]] = {cid: [] for cid in llm_cands}
    llm_latency_by_cand: Dict[str, List[float]] = {cid: [] for cid in llm_cands}

    # Execute pass on SYN_001 (rep 0 and rep 1 for stability) and SYN_015 (rep 0)
    eval_schedule = [("SYN_001", 0), ("SYN_001", 1), ("SYN_015", 0)]
    for cid, rep in eval_schedule:
        cand = cand_by_id[cid]
        t0 = time.perf_counter()
        try:
            res = ollama_ranker.rank(cand, test_jobs, k=10)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            llm_results_by_cand[cid].append(res.ranked_job_ids)
            llm_latency_by_cand[cid].append(elapsed_ms)
            print(f"  [{cid} rep {rep}] hybrid_llm_ollama completed in {elapsed_ms}ms")
        except Exception as e:
            print(f"  [{cid} rep {rep}] hybrid_llm_ollama error: {e}")

    # Compute diagnostics
    # 1. Non-LLM rank correlations and overlaps
    all_methods = non_llm_methods + (["hybrid_llm_ollama"] if any(llm_results_by_cand.values()) else [])
    
    # Average latency per method
    avg_latencies = {}
    for m in non_llm_methods:
        avg_latencies[m] = round(float(sum(latency_by_cand[cid][m] for cid in non_llm_cands) / len(non_llm_cands)), 2)
    if any(llm_latency_by_cand.values()):
        all_llm_times = [t for times in llm_latency_by_cand.values() for t in times]
        if all_llm_times:
            avg_latencies["hybrid_llm_ollama"] = round(float(sum(all_llm_times) / len(all_llm_times)), 2)

    # Pairwise Kendall tau and top-10 overlap between non-LLM arms
    pairwise_taus: Dict[str, Dict[str, float]] = {m1: {m2: 0.0 for m2 in non_llm_methods} for m1 in non_llm_methods}
    pairwise_overlaps: Dict[str, Dict[str, float]] = {m1: {m2: 0.0 for m2 in non_llm_methods} for m1 in non_llm_methods}

    for m1 in non_llm_methods:
        for m2 in non_llm_methods:
            if m1 == m2:
                pairwise_taus[m1][m2] = 1.0
                pairwise_overlaps[m1][m2] = 1.0
            else:
                taus = [calculate_kendall_tau(results_by_cand[cid][m1], results_by_cand[cid][m2], k=10) for cid in non_llm_cands]
                overlaps = [calculate_topk_overlap(results_by_cand[cid][m1], results_by_cand[cid][m2], k=10) for cid in non_llm_cands]
                pairwise_taus[m1][m2] = round(float(sum(taus) / len(taus)), 4)
                pairwise_overlaps[m1][m2] = round(float(sum(overlaps) / len(overlaps)), 4)

    # LLM repeat stability
    llm_stability = {}
    for cid in llm_cands:
        reps = llm_results_by_cand.get(cid, [])
        if len(reps) >= 2:
            tau = calculate_kendall_tau(reps[0], reps[1], k=10)
            overlap = calculate_topk_overlap(reps[0], reps[1], k=10)
            llm_stability[cid] = {"kendall_tau": round(tau, 4), "top10_overlap": round(overlap, 4)}

    print("\n================ DIAGNOSTICS SUMMARY TABLE ================")
    print("Method Latencies (mean wall-clock ms):")
    for m, lat in avg_latencies.items():
        print(f"  - {m:20s}: {lat:10.2f} ms")

    print("\nPairwise Mean Kendall Tau (Top-10):")
    header = f"{'':15s}" + "".join(f"{m:12s}" for m in non_llm_methods)
    print(header)
    for m1 in non_llm_methods:
        row = f"{m1:15s}" + "".join(f"{pairwise_taus[m1][m2]:12.4f}" for m2 in non_llm_methods)
        print(row)

    print("\nPairwise Mean Top-10 Jaccard Overlap:")
    print(header)
    for m1 in non_llm_methods:
        row = f"{m1:15s}" + "".join(f"{pairwise_overlaps[m1][m2]:12.4f}" for m2 in non_llm_methods)
        print(row)

    if llm_stability:
        print("\nLLM Re-Ranker Run-to-Run Stability (Between Repeat 0 and 1):")
        for cid, stab in llm_stability.items():
            print(f"  - {cid}: Kendall Tau = {stab['kendall_tau']:.4f}, Top-10 Overlap = {stab['top10_overlap']:.4f}")

    # Save summary JSON
    summary_payload = {
        "run_type": "dryrun",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "candidates": non_llm_cands,
        "llm_candidates": llm_cands,
        "latencies_ms": avg_latencies,
        "pairwise_kendall_tau": pairwise_taus,
        "pairwise_top10_overlap": pairwise_overlaps,
        "llm_stability": llm_stability,
    }
    with open(output_dir / "diagnostics_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary_payload, f, indent=2)
    print(f"\nSaved smoke test diagnostics to: {output_dir / 'diagnostics_summary.json'}")


if __name__ == "__main__":
    run_r12_dryrun_smoke()
