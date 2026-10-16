"""
scripts/run_ranking_experiment.py
---------------------------------
Experiment runner for Phase B:
Command-line interface executing ranking methods over frozen snapshots:
  python scripts/run_ranking_experiment.py \
    --snapshot data/snapshots/test_snap_1.json \
    --resumes uploads/resumes \
    --manifest data/gold/gold_resumes_skills.json \
    --methods bm25,sbert,overlap,hybrid,composite_xgb \
    --k 10 \
    --repeat 0 \
    --seed 42

Outputs per-resume, per-method top-10 JSON files through the resumable batch runner.
Logs hardware specs, per-method latency, seeds, token counts, and weight hashes.
"""

import argparse
import asyncio
from datetime import datetime, timezone
import glob
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import sys
import time
from typing import Any, Dict, List, Optional
import pypdf

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
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


def get_weights_sha256(config_path: str = "app/ranking/config.json") -> str:
    """Compute SHA-256 hash of ranking weights configuration for provenance."""
    path = Path(config_path)
    if path.exists():
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    return "n/a"


def sanitize_experiment_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize metadata to ensure no API keys or raw error URLs enter run logs."""
    sanitized: Dict[str, Any] = {}

    req_model = meta.get("requested_model") or meta.get("model") or "n/a"
    ans_model = meta.get("answered_model") or meta.get("model") or "n/a"
    status_val = meta.get("status", "completed")
    attempts_val = meta.get("attempts", 1)
    error_type_val = meta.get("error_type") or meta.get("error type")
    if not error_type_val and meta.get("error"):
        error_type_val = "APIError"

    blocked_keys = {"error", "api_key", "key", "authorization", "auth", "token", "password", "secret", "headers"}
    for k, v in meta.items():
        if k in blocked_keys:
            continue
        if isinstance(v, str):
            v = re.sub(r"key=([A-Za-z0-9-_.]+)", "key=[REDACTED_KEY]", v)
            v = re.sub(r"\bAIza[0-9A-Za-z-_]{35}\b", "[REDACTED_KEY]", v)
            v = re.sub(r"\bAQ\.Ab[0-9A-Za-z-_]+\b", "[REDACTED_KEY]", v)
            v = re.sub(r"\bgsk_[0-9A-Za-z]{32,}\b", "[REDACTED_KEY]", v)
        sanitized[k] = v

    # Explicitly enforce provider execution fields
    sanitized["requested_model"] = req_model
    sanitized["answered_model"] = ans_model
    sanitized["status"] = status_val
    sanitized["attempts"] = attempts_val
    sanitized["error_type"] = error_type_val
    sanitized["error type"] = error_type_val

    return sanitized


def load_and_anonymize_resumes(
    resumes_dir: Path | str = "uploads/resumes",
    manifest_path: Optional[Path | str] = None,
    strict_manifest: bool = True,
) -> List[Dict[str, Any]]:
    """Load resumes from directory and/or manifest into anonymized candidate records without hardcoded names.
    When strict_manifest is True:
      - manifest_path must be provided and must point to an existing file.
      - Silent fallback to directory scanning is strictly prohibited.
      - Every resume declared in the manifest must exist and be readable.
    """
    dir_path = Path(resumes_dir)
    candidates: List[Dict[str, Any]] = []

    if strict_manifest:
        if not manifest_path:
            raise ValueError(
                "Strict manifest validation enabled: manifest_path is required. "
                "Silent fallback to directory scanning is prohibited in formal ranking experiments."
            )
        man_file = Path(manifest_path)
        if not man_file.exists():
            raise FileNotFoundError(
                f"Strict manifest validation failed: manifest file '{manifest_path}' does not exist. "
                "Silent fallback to directory scanning is prohibited."
            )
        try:
            with open(man_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            raise ValueError(f"Strict manifest validation failed: could not parse JSON from manifest '{manifest_path}': {e}")

        manifest_entries = data.get("resumes", [])
        if not manifest_entries:
            raise ValueError(f"Strict manifest validation failed: manifest '{manifest_path}' contains zero resumes.")

        for entry in manifest_entries:
            r_file = entry.get("resume_file", "")
            target_path = Path(r_file)
            if not target_path.exists():
                target_path = dir_path / target_path.name
            if not target_path.exists():
                prefix = Path(r_file).name.split("_")[0]
                matches = list(dir_path.glob(f"{prefix}*"))
                if matches:
                    target_path = matches[0]

            if not target_path.exists():
                raise FileNotFoundError(
                    f"Strict manifest validation failed: resume file '{r_file}' declared in manifest '{manifest_path}' "
                    f"was not found in '{dir_path}'."
                )

            cand_name = entry.get("candidate_name")
            cand_id = entry.get("candidate_id") or target_path.stem.split("_")[0]
            try:
                reader = pypdf.PdfReader(target_path)
                raw = "\n".join([p.extract_text() or "" for p in reader.pages])
            except Exception as e:
                raise RuntimeError(f"Strict manifest validation failed: could not read PDF '{target_path}': {e}")

            anon_text = anonymize_resume(raw, candidate_name=cand_name, strip_institutions=True)
            parsed = parser_agent._parse_with_rules(anon_text)

            candidates.append({
                "candidate_id": cand_id,
                "file_name": target_path.name,
                "candidate_name": cand_name or cand_id,
                "raw_text": anon_text,
                "summary": parsed.summary or "",
                "skills": parsed.skills or [],
                "experience": [e.model_dump() for e in parsed.experience],
            })

        if not candidates:
            raise ValueError(f"Strict manifest validation failed: no valid candidate resumes were loaded from '{manifest_path}'.")

        return candidates

    # Non-strict mode: fallback allowed only if explicitly disabled
    manifest_entries: List[Dict[str, Any]] = []
    if manifest_path and Path(manifest_path).exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                manifest_entries = data.get("resumes", [])
        except Exception as e:
            print(f"[WARN] Failed to read manifest {manifest_path}: {e}")

    if manifest_entries:
        for entry in manifest_entries:
            r_file = entry.get("resume_file", "")
            target_path = Path(r_file)
            if not target_path.exists():
                target_path = dir_path / target_path.name
            if not target_path.exists():
                prefix = Path(r_file).name.split("_")[0]
                matches = list(dir_path.glob(f"{prefix}*"))
                if matches:
                    target_path = matches[0]

            if not target_path.exists():
                print(f"[WARN] Resume file from manifest not found: {r_file}. Skipping.")
                continue

            cand_name = entry.get("candidate_name")
            cand_id = entry.get("candidate_id") or target_path.stem.split("_")[0]
            try:
                reader = pypdf.PdfReader(target_path)
                raw = "\n".join([p.extract_text() or "" for p in reader.pages])
            except Exception:
                raw = ""

            anon_text = anonymize_resume(raw, candidate_name=cand_name, strip_institutions=True)
            parsed = parser_agent._parse_with_rules(anon_text)

            candidates.append({
                "candidate_id": cand_id,
                "file_name": target_path.name,
                "candidate_name": cand_name or cand_id,
                "raw_text": anon_text,
                "summary": parsed.summary or "",
                "skills": parsed.skills or [],
                "experience": [e.model_dump() for e in parsed.experience],
            })
    else:
        # Directory scan without manifest (non-strict mode only)
        pdf_files = sorted(list(dir_path.glob("*.pdf")))
        for fpath in pdf_files:
            cand_id = fpath.stem.split("_")[0]
            try:
                reader = pypdf.PdfReader(fpath)
                raw = "\n".join([p.extract_text() or "" for p in reader.pages])
            except Exception:
                continue

            anon_text = anonymize_resume(raw, candidate_name=None, strip_institutions=True)
            parsed = parser_agent._parse_with_rules(anon_text)

            candidates.append({
                "candidate_id": cand_id,
                "file_name": fpath.name,
                "candidate_name": cand_id,
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
        elif m_clean == "hybrid_llm_gemini":
            gemini_key = os.environ.get("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", None)
            if not gemini_key:
                raise RuntimeError("GEMINI_API_KEY is missing; mock fallback is prohibited in experiment runs.")
            rankers["hybrid_llm_gemini"] = LLMReranker(
                name="hybrid_llm_gemini",
                provider_name="gemini",
                hybrid_ranker=hybrid,
            )
        elif m_clean == "hybrid_llm_gemini-mock":
            raise RuntimeError("hybrid_llm_gemini-mock is prohibited in experiment runs; mock fallback is not allowed.")
        else:
            raise ValueError(f"Unknown ranking method requested: '{m}'")
    return rankers


def run_experiment(
    snapshot_path: str,
    resumes_dir: str,
    methods: List[str],
    manifest_path: Optional[str] = "data/gold/gold_resumes_skills.json",
    strict_manifest: bool = True,
    k: int = 10,
    repeat_idx: int = 0,
    universe_seed: int = 42,
    max_snapshot_records: Optional[int] = 100,
) -> None:
    """Run full Phase B ranking experiment with resumable batch logger."""
    hardware_info = get_system_hardware_info()
    weight_hash = get_weights_sha256()
    print("System Hardware:", json.dumps(hardware_info, indent=2))
    print(f"Universe Seed: {universe_seed} | Weight Hash: {weight_hash[:16]}... | Repeat Index: {repeat_idx}")

    snapshot_records, snapshot_meta = load_snapshot(snapshot_path)
    if max_snapshot_records:
        snapshot_records = snapshot_records[:max_snapshot_records]
    print(f"Loaded {len(snapshot_records)} jobs from snapshot (hash: {snapshot_meta.get('sha256_hash', 'N/A')[:12]}...)")

    candidates = load_and_anonymize_resumes(
        resumes_dir,
        manifest_path=manifest_path,
        strict_manifest=strict_manifest,
    )
    print(f"Loaded {len(candidates)} anonymized test resumes.")

    rankers = instantiate_rankers(methods)
    print(f"Initialized {len(rankers)} rankers: {list(rankers.keys())}")

    logger = ExperimentLogger(experiment_name="phase_b_ranking")

    for cand in candidates:
        cand_id = cand["candidate_id"]
        cand_name = cand["candidate_name"]
        print(f"\n================ Running Evaluations for {cand_name} ({cand_id}) [rep={repeat_idx}] ================")

        for method_name, ranker in rankers.items():
            run_key = f"{cand_id}_rep{repeat_idx}_{method_name}"

            if logger.is_completed(run_key):
                print(f"[{run_key}] Already completed. Skipping.")
                continue

            print(f"[{run_key}] Executing {method_name} (k={k}, seed={universe_seed})...")
            t0 = time.time()

            result: RankingResult = ranker.rank(cand, snapshot_records, k=k)

            elapsed_ms = round((time.time() - t0) * 1000, 2)

            sanitized_meta = sanitize_experiment_metadata(result.metadata)
            run_meta = {
                **sanitized_meta,
                "latency_total_ms": elapsed_ms,
                "hardware": hardware_info,
                "snapshot_sha256": snapshot_meta.get("sha256_hash"),
                "weight_hash": weight_hash,
                "universe_seed": universe_seed,
                "candidate_id": cand_id,
                "candidate_name": cand_name,
                "repeat_idx": repeat_idx,
                "k": k,
            }

            output_payload = {
                "method": method_name,
                "candidate_id": cand_id,
                "candidate": cand_name,
                "repeat_idx": repeat_idx,
                "ranked_job_ids": result.ranked_job_ids,
                "scores": {jid: result.scores.get(jid, 0.0) for jid in result.ranked_job_ids},
                "run_metadata": run_meta,
            }

            saved_path = logger.log_run(
                item_id=run_key,
                model=run_meta.get("model", "n/a"),
                prompt_version=run_meta.get("prompt_version", "n/a"),
                seed=universe_seed,
                inputs={"candidate_id": cand_id, "snapshot": snapshot_path, "k": k, "repeat_idx": repeat_idx},
                outputs=output_payload,
                provider=run_meta.get("provider", method_name),
            )

            print(f"[{run_key}] Done in {elapsed_ms}ms -> Saved to {saved_path.name}")


def main():
    parser = argparse.ArgumentParser(description="Phase B Ranking Experiment Runner")
    parser.add_argument("--snapshot", type=str, default="data/snapshots/test_snap_1.json", help="Path to frozen job snapshot")
    parser.add_argument("--resumes", type=str, default="uploads/resumes", help="Path to resumes folder")
    parser.add_argument("--manifest", type=str, default="data/gold/gold_resumes_skills.json", help="Path to resume manifest JSON")
    parser.add_argument(
        "--strict-manifest",
        action="store_true",
        default=True,
        help="Enforce strict manifest validation without falling back to directory scanning (default True)",
    )
    parser.add_argument(
        "--allow-dir-scan",
        dest="strict_manifest",
        action="store_false",
        help="Allow fallback to directory scan if manifest is not provided",
    )
    parser.add_argument(
        "--methods",
        type=str,
        default="bm25,sbert,overlap,hybrid,composite_xgb",
        help="Comma-separated rankers",
    )
    parser.add_argument("--k", type=int, default=10, help="Top k to rank")
    parser.add_argument("--repeat", type=int, default=0, help="Repeat index for experiment replication (default 0)")
    parser.add_argument("--seed", type=int, default=42, help="Universe seed for experiment (default 42)")
    parser.add_argument("--max_jobs", type=int, default=100, help="Max jobs to test from snapshot (default 100)")
    args = parser.parse_args()

    method_list = [m.strip() for m in args.methods.split(",") if m.strip()]
    run_experiment(
        snapshot_path=args.snapshot,
        resumes_dir=args.resumes,
        manifest_path=args.manifest,
        strict_manifest=args.strict_manifest,
        methods=method_list,
        k=args.k,
        repeat_idx=args.repeat,
        universe_seed=args.seed,
        max_snapshot_records=args.max_jobs,
    )


if __name__ == "__main__":
    main()
