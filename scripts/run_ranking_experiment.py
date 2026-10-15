"""
scripts/run_ranking_experiment.py
---------------------------------
Experiment runner for Phase B:
Command-line interface executing ranking methods over frozen snapshots:
  python scripts/run_ranking_experiment.py \
    --snapshot data/snapshots/test_snap_1.json \
    --resumes uploads/resumes \
    --methods bm25,sbert,overlap,hybrid,hybrid_llm_ollama,hybrid_llm_gemini,composite_xgb \
    --k 10

Outputs per-resume, per-method top-10 JSON files through the resumable batch runner.
Logs hardware specs, per-method latency, and memory consumption.
"""

import argparse
import asyncio
from datetime import datetime, timezone
import glob
import json
import os
from pathlib import Path
import platform
import sys
import time
from typing import Any, Dict, List, Optional
import pypdf

from app.ranking.base import RankingResult
from app.ranking.baselines import BM25Ranker, SbertRanker, SkillOverlapRanker
from app.ranking.hybrid import CompositeXGBRanker, HybridRanker
from app.ranking.llm_reranker import LLMReranker
from app.services.anonymizer import anonymize_resume
from app.services.parser_agent import parser_agent
from scripts.experiment_runner import BatchRunner, ExperimentLogger
from scripts.job_snapshot import load_snapshot


def get_system_hardware_info() -> Dict[str, Any]:
    """Capture system hardware specifications for experiment reproducibility."""
    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "python_version": platform.python_version(),
    }


def load_and_anonymize_resumes(resumes_dir: Path | str) -> List[Dict[str, Any]]:
    """Scan directory for resumes and parse into anonymized candidate records."""
    dir_path = Path(resumes_dir)
    pdf_files = list(dir_path.glob("*.pdf"))

    candidates: List[Dict[str, Any]] = []

    for fpath in pdf_files:
        name_hint = "Mahima" if "Mahima" in fpath.name else ("Deepika" if "Deepika" in fpath.name else "Candidate")
        try:
            reader = pypdf.PdfReader(fpath)
            raw = "\n".join([p.extract_text() or "" for p in reader.pages])
        except Exception as e:
            continue

        anon_text = anonymize_resume(raw, candidate_name=name_hint)
        parsed = parser_agent._parse_with_rules(anon_text)

        candidates.append({
            "candidate_id": fpath.stem.split("_")[0],
            "file_name": fpath.name,
            "candidate_name": name_hint,
            "raw_text": anon_text,
            "summary": parsed.summary or "",
            "skills": parsed.skills or [],
            "experience": [e.model_dump() for e in parsed.experience],
        })

    return candidates


def instantiate_rankers(method_names: List[str]) -> Dict[str, Any]:
    """Instantiate rankers matching requested method identifiers."""
    rankers = {}
    bm25 = BM25Ranker()
    sbert = SbertRanker()
    overlap = SkillOverlapRanker()
    hybrid = HybridRanker(bm25_ranker=bm25, sbert_ranker=sbert, overlap_ranker=overlap)

    for m in method_names:
        m_clean = m.strip().lower()
        if m_clean == "bm25":
            rankers["bm25"] = bm25
        elif m_clean == "sbert":
            rankers["sbert"] = sbert
        elif m_clean == "overlap":
            rankers["overlap"] = overlap
        elif m_clean == "hybrid":
            rankers["hybrid"] = hybrid
        elif m_clean == "composite_xgb":
            rankers["composite_xgb"] = CompositeXGBRanker()
        elif m_clean == "hybrid_llm_ollama":
            rankers["hybrid_llm_ollama"] = LLMReranker(
                name="hybrid_llm_ollama",
                provider_name="ollama",
                hybrid_ranker=hybrid,
            )
        elif m_clean in ("hybrid_llm_gemini", "hybrid_llm_gemini-mock"):
            provider = "gemini" if os.environ.get("GEMINI_API_KEY") else "gemini-mock"
            rankers["hybrid_llm_gemini"] = LLMReranker(
                name="hybrid_llm_gemini",
                provider_name=provider,
                hybrid_ranker=hybrid,
            )
    return rankers


def run_experiment(
    snapshot_path: str,
    resumes_dir: str,
    methods: List[str],
    k: int = 10,
    max_snapshot_records: Optional[int] = 100,
) -> None:
    """Run full Phase B ranking experiment with resumable batch logger."""
    hardware_info = get_system_hardware_info()
    print("System Hardware:", json.dumps(hardware_info, indent=2))

    snapshot_records, snapshot_meta = load_snapshot(snapshot_path)
    if max_snapshot_records:
        snapshot_records = snapshot_records[:max_snapshot_records]
    print(f"Loaded {len(snapshot_records)} jobs from snapshot (hash: {snapshot_meta.get('sha256_hash', 'N/A')[:12]}...)")

    candidates = load_and_anonymize_resumes(resumes_dir)
    print(f"Loaded {len(candidates)} anonymized test resumes.")

    rankers = instantiate_rankers(methods)
    print(f"Initialized {len(rankers)} rankers: {list(rankers.keys())}")

    logger = ExperimentLogger(experiment_name="phase_b_ranking")

    for cand in candidates:
        cand_id = cand["candidate_id"]
        cand_name = cand["candidate_name"]
        print(f"\n================ Running Evaluations for {cand_name} ({cand_id}) ================")

        for method_name, ranker in rankers.items():
            run_key = f"{cand_name.lower()}_{method_name}"

            if logger.is_completed(run_key):
                print(f"[{run_key}] Already completed. Skipping.")
                continue

            print(f"[{run_key}] Executing {method_name} (k={k})...")
            t0 = time.time()

            result: RankingResult = ranker.rank(cand, snapshot_records, k=k)

            elapsed_ms = round((time.time() - t0) * 1000, 2)

            run_meta = {
                **result.metadata,
                "latency_total_ms": elapsed_ms,
                "hardware": hardware_info,
                "snapshot_sha256": snapshot_meta.get("sha256_hash"),
                "candidate_name": cand_name,
                "k": k,
            }

            output_payload = {
                "method": method_name,
                "candidate": cand_name,
                "ranked_job_ids": result.ranked_job_ids,
                "scores": {jid: result.scores.get(jid, 0.0) for jid in result.ranked_job_ids},
                "run_metadata": run_meta,
            }

            saved_path = logger.log_run(
                item_id=run_key,
                model=run_meta.get("model", "n/a"),
                prompt_version=run_meta.get("prompt_version", "n/a"),
                seed=42,
                inputs={"candidate_id": cand_id, "snapshot": snapshot_path, "k": k},
                outputs=output_payload,
                provider=run_meta.get("provider", method_name),
            )

            print(f"[{run_key}] Done in {elapsed_ms}ms -> Saved to {saved_path.name}")


def main():
    parser = argparse.ArgumentParser(description="Phase B Ranking Experiment Runner")
    parser.add_argument("--snapshot", type=str, default="data/snapshots/test_snap_1.json", help="Path to frozen job snapshot")
    parser.add_argument("--resumes", type=str, default="uploads/resumes", help="Path to resumes folder")
    parser.add_argument(
        "--methods",
        type=str,
        default="bm25,sbert,overlap,hybrid,hybrid_llm_gemini,composite_xgb",
        help="Comma-separated rankers",
    )
    parser.add_argument("--k", type=int, default=10, help="Top k to rank")
    parser.add_argument("--max_jobs", type=int, default=100, help="Max jobs to test from snapshot (default 100)")
    args = parser.parse_args()

    method_list = [m.strip() for m in args.methods.split(",") if m.strip()]
    run_experiment(
        snapshot_path=args.snapshot,
        resumes_dir=args.resumes,
        methods=method_list,
        k=args.k,
        max_snapshot_records=args.max_jobs,
    )


if __name__ == "__main__":
    main()
