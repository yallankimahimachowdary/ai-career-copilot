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
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple
import psutil
import pypdf

class MemorySampler:
    """Samples peak resident set size (RSS) in MB every interval seconds during execution."""
    def __init__(self, interval: float = 0.5, track_ollama: bool = False):
        self.interval = interval
        self.track_ollama = track_ollama
        self.peak_python_mb = 0.0
        self.peak_ollama_mb = 0.0
        self._stop_event = threading.Event()
        self._thread = None

    def _sample_iteration(self):
        try:
            py_proc = psutil.Process()
            py_rss = py_proc.memory_info().rss
            for child in py_proc.children(recursive=True):
                try:
                    py_rss += child.memory_info().rss
                except Exception:
                    pass
            py_mb = py_rss / (1024 * 1024)
            if py_mb > self.peak_python_mb:
                self.peak_python_mb = py_mb
        except Exception:
            pass

        if self.track_ollama:
            try:
                ol_rss = 0
                for p in psutil.process_iter(["name", "memory_info"]):
                    try:
                        p_name = (p.info.get("name") or "").lower()
                        if "ollama" in p_name or "llama" in p_name:
                            ol_rss += p.info["memory_info"].rss
                    except Exception:
                        pass
                ol_mb = ol_rss / (1024 * 1024)
                if ol_mb > self.peak_ollama_mb:
                    self.peak_ollama_mb = ol_mb
            except Exception:
                pass

    def _run_loop(self):
        while not self._stop_event.is_set():
            self._sample_iteration()
            self._stop_event.wait(self.interval)

    def start(self):
        self._sample_iteration()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> Tuple[float, float]:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        self._sample_iteration()
        return round(self.peak_python_mb, 2), round(self.peak_ollama_mb, 2)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.ranking.base import RankingResult
from app.ranking.baselines import BM25Ranker, RandomReorderRanker, SbertRanker, SkillOverlapRanker
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
    max_resumes: Optional[int] = None,
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
        if max_resumes is not None:
            pdf_files = pdf_files[:max_resumes]
        for fpath in pdf_files:
            parts = fpath.stem.split("_")
            cand_id = f"{parts[0]}_{parts[1]}" if len(parts) > 1 and parts[0] == "SYN" else parts[0]
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
        elif m_clean in ("random_reorder", "random"):
            rankers["random_reorder"] = RandomReorderRanker()
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
    max_snapshot_records: Optional[int] = None,
    max_resumes: Optional[int] = None,
    run_type: str = "dryrun",
    universes_path: Optional[str] = None,
) -> None:
    """Run full Phase B ranking experiment with resumable batch logger."""
    hardware_info = get_system_hardware_info()
    weight_hash = get_weights_sha256()
    print("System Hardware:", json.dumps(hardware_info, indent=2))
    print(f"Universe Seed: {universe_seed} | Weight Hash: {weight_hash[:16]}... | Repeat Index: {repeat_idx}")

    if run_type == "real" and max_snapshot_records is not None:
        raise ValueError("Cannot slice snapshot records during real evaluation. max_snapshot_records must be None.")

    snapshot_records, snapshot_meta = load_snapshot(snapshot_path)
    if max_snapshot_records is not None:
        snapshot_records = snapshot_records[:max_snapshot_records]
    print(f"Loaded {len(snapshot_records)} jobs from snapshot (hash: {snapshot_meta.get('sha256_hash', 'N/A')[:12]}...)")

    candidate_universes_map: Dict[str, Set[str]] = {}
    resolved_univ_path = universes_path
    if not resolved_univ_path:
        default_univ = Path("results/real/candidate_universes.json") if run_type == "real" else Path("results/dryrun/candidate_universes.json")
        if default_univ.exists():
            resolved_univ_path = str(default_univ)

    if resolved_univ_path and Path(resolved_univ_path).exists():
        with open(resolved_univ_path, "r", encoding="utf-8") as f:
            u_data = json.load(f)
            for cid, cinfo in u_data.get("candidate_universes", {}).items():
                job_ids = cinfo.get("job_ids") or []
                if job_ids:
                    candidate_universes_map[cid] = set(str(jid) for jid in job_ids)
        print(f"[UNIVERSE] Loaded universe constraints for {len(candidate_universes_map)} candidates from {resolved_univ_path}.")

    if run_type == "real" and not candidate_universes_map:
        raise RuntimeError("Candidate universes are mandatory for real ranking experiments.")

    candidates = load_and_anonymize_resumes(
        resumes_dir,
        manifest_path=manifest_path,
        strict_manifest=strict_manifest,
        max_resumes=max_resumes,
    )
    if max_resumes is not None:
        candidates = candidates[:max_resumes]
    print(f"Loaded {len(candidates)} anonymized test resumes (max_resumes={max_resumes}, run_type={run_type}).")

    rankers = instantiate_rankers(methods)
    print(f"Initialized {len(rankers)} rankers: {list(rankers.keys())}")

    base_dir = Path("results/dryrun") if run_type == "dryrun" else Path("artifacts/experiments/runs")
    logger = ExperimentLogger(experiment_name="phase_b_ranking", base_dir=base_dir, run_type=run_type)

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

            if cand_id in candidate_universes_map:
                cand_job_pool = [
                    j for j in snapshot_records
                    if str(j.get("id") or j.get("external_id") or j.get("job_id") or "") in candidate_universes_map[cand_id]
                ]
            else:
                cand_job_pool = snapshot_records

            sampler = MemorySampler(interval=0.5, track_ollama=("ollama" in method_name.lower()))
            sampler.start()
            try:
                result: RankingResult = ranker.rank(cand, cand_job_pool, k=k)
            finally:
                peak_py_mb, peak_ol_mb = sampler.stop()

            elapsed_ms = round((time.time() - t0) * 1000, 2)

            sanitized_meta = sanitize_experiment_metadata(result.metadata)
            run_meta = {
                **sanitized_meta,
                "latency_total_ms": elapsed_ms,
                "peak_rss_python_mb": peak_py_mb,
                "peak_rss_ollama_mb": peak_ol_mb,
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
                "peak_rss_python_mb": peak_py_mb,
                "peak_rss_ollama_mb": peak_ol_mb,
                "run_metadata": run_meta,
            }

            req_m = run_meta.get("requested_model") or run_meta.get("model") or method_name
            ret_m = run_meta.get("answered_model") or run_meta.get("model") or method_name
            if "gemini" in method_name or run_meta.get("provider") == "gemini":
                req_clean = str(req_m).removeprefix("models/").lower()
                ret_clean = str(ret_m).removeprefix("models/").lower()
                if req_clean != ret_clean and not ret_clean.startswith(req_clean) and not req_clean.startswith(ret_clean):
                    raise RuntimeError(
                        f"Strict model validation failed: requested '{req_m}' != returned '{ret_m}'"
                    )
            saved_path = logger.log_run(
                item_id=run_key,
                requested_model=str(req_m),
                returned_model=str(ret_m),
                seed=universe_seed,
                inputs={"candidate_id": cand_id, "snapshot": snapshot_path, "k": k, "repeat_idx": repeat_idx},
                outputs=output_payload,
                provider=run_meta.get("provider", method_name),
                snapshot_hash=snapshot_meta.get("sha256_hash"),
                gate_flags={"seniority_gate": getattr(settings, "SENIORITY_GATE", True)},
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
    parser.add_argument("--repeats", type=int, default=1, help="Total repeat runs K (default 1, recommended K=3 for LLM stability)")
    parser.add_argument("--confirm", action="store_true", help="Confirm execution when ETA exceeds 2 hours")
    parser.add_argument("--seed", type=int, default=42, help="Universe seed for experiment (default 42)")
    parser.add_argument("--max_jobs", type=int, default=None, help="[DRY-RUN ONLY] Slices snapshot records for quick testing")
    parser.add_argument("--universes", type=str, default=None, help="Path to candidate_universes.json")
    parser.add_argument("--max-resumes", "--max_resumes", dest="max_resumes", type=int, default=None, help="Max resumes to evaluate (for dry-run mode)")
    parser.add_argument("--run-type", "--run_type", dest="run_type", type=str, default="dryrun", choices=["dryrun", "real"], help="Run type tag ('dryrun' or 'real')")
    args = parser.parse_args()

    method_list = [m.strip() for m in args.methods.split(",") if m.strip()]
    # Compute ETA if LLM arm is present
    has_llm = any("llm" in m.lower() for m in method_list)
    k_repeats = args.repeats if args.repeats > 1 else 1
    if has_llm:
        est_cand = args.max_resumes if args.max_resumes else 10
        # Measured warm inference on llama3.2:3b CPU with num_thread=4 is ~11.8 - 15.3s (~0.22 min) per candidate
        est_minutes = est_cand * k_repeats * 0.22
        est_hours = est_minutes / 60.0
        print(f"\n[ETA ESTIMATE] LLM re-ranking detected for ~{est_cand} candidates x {k_repeats} repeat(s).")
        print(f"[ETA ESTIMATE] Estimated duration: {est_minutes:.1f} minutes ({est_hours:.2f} hours).")
        if est_hours > 2.0 and not args.confirm:
            raise RuntimeError(
                f"Execution estimate ({est_hours:.2f} hours) exceeds 2 hours. Pass --confirm to proceed."
            )

    for rep in range(k_repeats):
        current_rep = rep if k_repeats > 1 else args.repeat
        run_experiment(
            snapshot_path=args.snapshot,
            resumes_dir=args.resumes,
            manifest_path=args.manifest,
            strict_manifest=args.strict_manifest,
            methods=method_list,
            k=args.k,
            repeat_idx=current_rep,
            universe_seed=args.seed,
            max_snapshot_records=args.max_jobs,
            max_resumes=args.max_resumes,
            run_type=args.run_type,
            universes_path=args.universes,
        )


if __name__ == "__main__":
    main()
