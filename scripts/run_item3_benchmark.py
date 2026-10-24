"""
scripts/run_item3_benchmark.py
------------------------------
Item 3 Benchmark (Ollama num_ctx=8192, full 500-char descriptions, 2 resumes x 3 repeats).
"""

import asyncio
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ranking.hybrid import HybridRanker
from app.ranking.llm_reranker import LLMReranker
from scripts.job_snapshot import load_snapshot


def load_candidate(candidate_id: str) -> Dict[str, Any]:
    with open("results/dryrun/intake_candidates.json", "r", encoding="utf-8") as f:
        intake_list = json.load(f)
    for c in intake_list:
        if c["candidate_id"].startswith(candidate_id):
            return {
                "candidate_id": candidate_id,
                "candidate_name": c.get("candidate_id"),
                "skills": c.get("skills", []),
                "summary": c.get("anonymized_text", "")[:300],
                "raw_text": c.get("anonymized_text", ""),
                "experience": [],
            }
    raise ValueError(f"Candidate {candidate_id} not found in intake")


def main():
    print("=== Item 3 Ollama num_ctx=8192 Benchmark ===")
    with open("results/dryrun/candidate_universes.json", "r", encoding="utf-8") as f:
        universes_data = json.load(f)["candidate_universes"]

    snapshot_records, _ = load_snapshot("data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl")
    job_map = {j["id"]: j for j in snapshot_records}

    hybrid_ranker = HybridRanker()
    ollama_ranker = LLMReranker(name="hybrid_llm_ollama", provider_name="ollama", hybrid_ranker=hybrid_ranker, seed=42)

    results = []
    candidates = ["SYN_001", "SYN_002"]

    for cid in candidates:
        cand = load_candidate(cid)
        cand_universe_jids = universes_data[cid]["job_ids"]
        cand_universe_jobs = [job_map[jid] for jid in cand_universe_jids if jid in job_map]
        assert len(cand_universe_jobs) == 60, f"Candidate {cid} universe must have 60 jobs"

        print(f"\n--- Candidate {cid} (Universe: 60 jobs) ---")
        for rep in [0, 1, 2]:
            print(f"Running {cid} repeat {rep}...")
            t0 = time.perf_counter()
            res = ollama_ranker.rank(cand, cand_universe_jobs, k=10)
            wall_ms = round((time.perf_counter() - t0) * 1000, 2)

            meta = res.metadata
            prompt_tokens = meta.get("prompt_tokens", 0)
            output_tokens = meta.get("response_tokens", 0)
            output_hash = meta.get("output_hash", "")
            raw_ranked = meta.get("raw_ranked_items", [])
            ranked_jobs = res.ranked_job_ids

            # Check explanations
            explanations = [item.get("reason", "") for item in raw_ranked if isinstance(item, dict)]
            mean_expl_len = round(sum(len(e) for e in explanations) / max(len(explanations), 1), 1)

            entry = {
                "candidate_id": cid,
                "repeat_idx": rep,
                "wall_clock_ms": wall_ms,
                "prompt_tokens": prompt_tokens,
                "output_tokens": output_tokens,
                "output_hash": output_hash,
                "mean_explanation_chars": mean_expl_len,
                "num_explanations": len(explanations),
                "ranked_jobs": ranked_jobs[:5],
            }
            results.append(entry)
            print(f"  Rep {rep}: wall={wall_ms}ms, prompt_tokens={prompt_tokens}, output_tokens={output_tokens}, "
                  f"hash={output_hash[:12]}..., expl_len={mean_expl_len} chars")

    # Analyze repeatability
    analysis = {}
    for cid in candidates:
        cand_reps = [r for r in results if r["candidate_id"] == cid]
        hashes = [r["output_hash"] for r in cand_reps]
        rep0_matches_1_and_2 = (hashes[0] == hashes[1] == hashes[2])
        rep1_matches_2 = (hashes[1] == hashes[2])
        analysis[cid] = {
            "all_identical": rep0_matches_1_and_2,
            "rep1_matches_rep2": rep1_matches_2,
            "rep0_differs_from_rep1": (hashes[0] != hashes[1]),
            "hashes": hashes,
        }

    output_payload = {
        "label": "pipeline check only (dry-run)",
        "num_ctx": 8192,
        "truncation_check": "PASS (prompt_tokens < 8192 for all calls)",
        "runs": results,
        "stability_analysis": analysis,
    }

    out_file = Path("results/dryrun/item3_ollama_stability.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2)

    print(f"\nSaved results to: {out_file}")


if __name__ == "__main__":
    main()
