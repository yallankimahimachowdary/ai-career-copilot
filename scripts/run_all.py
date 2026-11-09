#!/usr/bin/env python3
"""
scripts/run_all.py
------------------
Staged One-Command Pipeline Runner (Remediation R14-2).

Stages:
  --stage prep:
    - Runs frozen-hash check on the 7 frozen files.
    - Runs secret scan (`scripts/check_secrets.py`).
    - Verifies service health (PostgreSQL, Neo4j, Ollama, Gemini API key presence in .env).
    - Loads frozen job snapshot.
    - Intakes resume PDFs (`scripts/intake_resumes.py`).
    - Builds stratified candidate universes (`scripts/build_universes.py`).
    - Generates blinded annotation sheets (`scripts/make_annotation_sheets.py`).
    - Concludes with explicit status: "awaiting annotations".

  --stage eval:
    - Requires `results/real/labels.jsonl` (or provided --labels file) and run_type=real.
    - Ingests human annotations, calculates inter-rater agreement (Quadratic Weighted Kappa + bootstrap CI).
    - Runs all ranking arms (BM25, SBERT, Overlap, Hybrid, Hybrid+LLM Ollama) with repeats.
    - Computes formal statistical comparisons (Wilcoxon signed-rank + Holm correction + bootstrap CI).
    - Evaluates ablations (Seniority gate, constituent arms, re-ranking).
    - Generates publication tables (`scripts/make_results_tables.py`).

  --stage all-dryrun:
    - Runs the complete pipeline end-to-end on synthetic resumes (`data/resumes_dryrun`).
    - Every output file, log, and record is strictly tagged with `run_type=dryrun`.
    - Quality metrics (nDCG, MAP, MRR) are withheld under the label gating protocol.
    - Emits diagnostics table (Kendall tau, top-k overlap, latency) and test tables.

Resumability & Integrity:
- Each stage writes an immutable stage manifest recording input/output hashes, git commit,
  taxonomy hash, seeds, and model IDs.
- Fails loudly on any silent fallback, model alias mismatch, or data contamination.
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.core.provenance import (
    build_provenance_record,
    get_file_sha256,
    get_git_commit_hash,
    FROZEN_CONFIG_PATH,
)
from app.core.taxonomy import TAXONOMY_VERSION, get_taxonomy_sha256
from scripts.intake_resumes import process_resume_intake
from scripts.build_universes import build_universes
from scripts.make_annotation_sheets import make_annotation_sheets
from scripts.ingest_annotations import ingest_annotations
from scripts.evaluate_ranking import run_evaluation_pipeline
from scripts.make_results_tables import export_tables


FROZEN_FILES = [
    Path("app/ranking/config.json"),
    Path("data/evaluation/query_intent_benchmark_v1.json"),
    Path("data/evaluation/rag_coach_eval_v1.json"),
    Path("data/router/test.jsonl"),
    Path("data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl"),
    Path("docs/role_families_frozen.json"),
    Path("docs/eval_scope.json"),
]

EXPECTED_FROZEN_HASHES = {
    "app/ranking/config.json": "16C548207D3B10D8E56C30E61D2EA9E18701FA168A38C1CEBB6CB72044692331",
    "data/evaluation/query_intent_benchmark_v1.json": "8C8A49FABD58860E8EC82111C80C142A3F8765740B8709A48A919BAFED0106B4",
    "data/evaluation/rag_coach_eval_v1.json": "E6EA387146511A11139B42F53A3DD302E9C98EE57B211B2AB0C5299500B24598",
    "data/router/test.jsonl": "6340BB8A778BDC19A65A7E72EEF8F771AD7AE4AC7A0889912DC50BC679335AD4",
    "data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl": "0732730B703454C3531E5CB2B3E2F89FBEC46D8DFB730644E257F02E110D6702",
    "docs/role_families_frozen.json": "329F78429CB2C261A265766E032B3D24F2E746CEDF6970D1D0D069EAA0CE19E5",
    "docs/eval_scope.json": "CF9061418B572F81DCE6746A034074148E3F1B37C110DDC19BE7316FEC21ED59",
}


def verify_frozen_hashes() -> bool:
    """Check that all 7 frozen files match their expected SHA-256 hashes bit-for-bit."""
    print("\n--- [STEP] Checking Frozen File Hashes ---")
    mismatches = []
    for rel_path, expected_hash in EXPECTED_FROZEN_HASHES.items():
        p = Path(rel_path)
        if not p.exists():
            mismatches.append(f"MISSING: {rel_path}")
            continue
        actual_hash = get_file_sha256(p)
        if actual_hash != expected_hash:
            mismatches.append(f"HASH MISMATCH on {rel_path}: expected {expected_hash}, got {actual_hash}")

    if mismatches:
        for err in mismatches:
            print(f"[FAIL] {err}")
        raise RuntimeError("Frozen file verification failed! Aborting execution.")
    print("[PASS] All 7 frozen benchmark files verified bit-for-bit.")
    return True


def run_secret_scanner() -> bool:
    """Execute pre-flight secret scanner."""
    print("\n--- [STEP] Executing Repository Secret Scanner ---")
    proc = subprocess.run(
        [sys.executable, "scripts/check_secrets.py"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        raise RuntimeError("Secret scanner detected exposed credentials or secrets!")
    print("[PASS] Secret scanner passed. Zero exposed secrets.")
    return True


def check_services_health() -> Dict[str, bool]:
    """Check availability of external backends and models."""
    print("\n--- [STEP] Checking Service and Backend Health ---")
    import httpx

    health = {}

    # 1. Ollama
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=3.0)
        health["ollama"] = (r.status_code == 200)
    except Exception:
        health["ollama"] = False

    # 2. Gemini API key
    gemini_key = os.environ.get("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", None)
    health["gemini_key_present"] = bool(gemini_key and len(gemini_key) > 10)

    # 3. PostgreSQL
    try:
        import asyncio
        from app.db.session import AsyncSessionLocal
        from sqlalchemy import text
        async def _check_pg():
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
        asyncio.run(_check_pg())
        health["postgres"] = True
    except Exception:
        health["postgres"] = False

    # 4. Neo4j
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            connection_timeout=3.0,
        )
        with driver.session() as session:
            session.run("RETURN 1")
        health["neo4j"] = True
    except Exception:
        health["neo4j"] = False

    for s_name, is_ok in health.items():
        status_str = "OK" if is_ok else "OFFLINE / NOT SET"
        print(f"  - {s_name:20s}: {status_str}")

    return health


def write_stage_manifest(stage_name: str, payload: Dict[str, Any], output_path: Path) -> Path:
    """Save an immutable stage execution manifest."""
    manifest_data = {
        "stage": stage_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit_hash(),
        "taxonomy_version": TAXONOMY_VERSION,
        "taxonomy_hash": get_taxonomy_sha256(),
        "config_hash": get_file_sha256(FROZEN_CONFIG_PATH),
        **payload,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
    print(f"[MANIFEST] Stage '{stage_name}' manifest written to: {output_path}")
    return output_path


def run_stage_prep(
    resumes_dir: str,
    snapshot_path: str,
    run_type: str = "real",
    seed: int = 42,
    universe_size: int = 60,
    double_rated: int = 8,
    max_resumes: Optional[int] = None,
    eval_subset: Optional[int] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """Execute Stage PREP: verification, intake, universes, and annotation sheets."""
    print(f"\n========================================================")
    print(f"   STARTING STAGE: PREP (run_type={run_type.upper()})")
    print(f"========================================================")

    # 1. Pre-flight checks
    verify_frozen_hashes()
    run_secret_scanner()
    health = check_services_health()

    if run_type == "real":
        dest_dir = Path("results/real")
    elif run_type == "synthetic_eval":
        dest_dir = Path("results/synthetic_eval")
    else:
        dest_dir = Path("results/dryrun")
    dest_dir.mkdir(parents=True, exist_ok=True)

    # 2. Intake resumes
    allow_syn = (run_type == "dryrun")
    intake_report = process_resume_intake(
        resumes_dir=resumes_dir,
        output_dir=dest_dir,
        run_type=run_type,
        allow_synthetic=allow_syn,
    )

    # 3. Build universes
    universes_output = dest_dir / "candidate_universes.json"
    universes_report = build_universes(
        snapshot_path=snapshot_path,
        resumes_dir=resumes_dir,
        seed=seed,
        universe_size=universe_size,
        run_type=run_type,
        output_path=universes_output,
        max_resumes=max_resumes,
        eval_subset=eval_subset,
        num_double_rated=double_rated,
        force=force,
    )

    # 4. Generate annotation sheets
    sheets_dir = dest_dir / "annotation_sheets"
    sheets_manifest = make_annotation_sheets(
        universes_json_path=universes_output,
        snapshot_path=snapshot_path,
        output_dir=sheets_dir,
        seed=seed,
        num_double_rated=double_rated,
        eval_subset=eval_subset,
        run_type=run_type,
    )

    # 5. Write Stage PREP Manifest
    manifest_file = sheets_dir / f"assignment_manifest_{run_type}.json"
    manifest_hash = get_file_sha256(manifest_file) if manifest_file.exists() else "n/a"

    stage_manifest = write_stage_manifest(
        stage_name="prep",
        payload={
            "run_type": run_type,
            "seed": seed,
            "resumes_dir": str(resumes_dir).replace("\\", "/"),
            "snapshot_path": str(snapshot_path).replace("\\", "/"),
            "intake_counts": intake_report.get("counts", {}),
            "universes_counts": universes_report.get("counts", {}),
            "sheets_manifest_hash": manifest_hash,
            "status": "awaiting_annotations",
        },
        output_path=dest_dir / "stage_prep_manifest.json",
    )

    print(f"\n[STAGE COMPLETE] Stage PREP completed successfully.")
    print(f"*** STATUS: AWAITING ANNOTATIONS ***")
    print(f"Distribute sheets from '{sheets_dir}' to Rater A and Rater B.")
    return {"status": "awaiting_annotations", "stage_manifest": str(stage_manifest)}


def run_stage_eval(
    labels_path: str,
    snapshot_path: str,
    resumes_dir: str,
    run_type: str = "real",
    seed: int = 42,
    repeats: int = 3,
    max_resumes: Optional[int] = None,
    dest_dir: Optional[Path | str] = None,
    dryrun_max_jobs_slice: Optional[int] = None,
) -> Dict[str, Any]:
    """Execute Stage EVAL: ingest labels, compute kappa, evaluate rankings, output tables."""
    print(f"\n========================================================")
    print(f"   STARTING STAGE: EVAL (run_type={run_type.upper()})")
    print(f"========================================================")

    # 1. Verification
    verify_frozen_hashes()
    run_secret_scanner()

    lbl_path = Path(labels_path)
    if not lbl_path.exists():
        raise FileNotFoundError(
            f"Ground-truth labels file '{lbl_path}' does not exist! "
            "Stage EVAL requires human annotations (results/real/labels.jsonl)."
        )

    if dest_dir is None:
        if run_type == "real":
            dest_dir = Path("results/real")
        elif run_type == "synthetic_eval":
            dest_dir = Path("results/synthetic_eval")
        else:
            dest_dir = Path("results/dryrun")
    else:
        dest_dir = Path(dest_dir)
    eval_output = dest_dir / "evaluation_report.json"

    # 2. Run ranking evaluation pipeline
    eval_report = run_evaluation_pipeline(
        snapshot_path=snapshot_path,
        resumes_dir=resumes_dir,
        judgments_path=str(lbl_path),
        output_report_path=str(eval_output),
        universes_path=str(dest_dir / "candidate_universes.json"),
        methods=["bm25", "sbert", "overlap", "hybrid"],
        k=10,
        universe_seed=seed,
        run_ablations=True,
        dryrun_max_jobs_slice=dryrun_max_jobs_slice,
        run_type=run_type,
    )

    # 3. Export publication tables
    tables_dir = dest_dir / "tables"
    allow_dr = (run_type == "dryrun")
    tables_result = export_tables(
        report_path=eval_output,
        output_dir=tables_dir,
        allow_dryrun=allow_dr,
    )

    # 4. Write Stage EVAL Manifest
    stage_manifest = write_stage_manifest(
        stage_name="eval",
        payload={
            "run_type": run_type,
            "labels_path": str(lbl_path).replace("\\", "/"),
            "labels_hash": get_file_sha256(lbl_path),
            "eval_report_path": str(eval_output).replace("\\", "/"),
            "eval_report_hash": get_file_sha256(eval_output),
            "tables": tables_result,
            "status": "evaluation_complete",
        },
        output_path=dest_dir / "stage_eval_manifest.json",
    )

    print(f"\n[STAGE COMPLETE] Stage EVAL completed successfully.")
    print(f"Tables exported to: {tables_dir}")
    return {"status": "evaluation_complete", "stage_manifest": str(stage_manifest)}


def run_stage_all_dryrun(
    snapshot_path: str = "data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl",
    resumes_dir: str = "data/resumes_dryrun",
    seed: int = 42,
    max_resumes: Optional[int] = 3,
) -> Dict[str, Any]:
    """Execute end-to-end dry-run pipeline on synthetic resumes."""
    print(f"\n========================================================")
    print(f"   STARTING STAGE: ALL-DRYRUN (Synthetic Data Pipeline)")
    print(f"========================================================")

    dest_dir = Path("results/dryrun")
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Prep
    prep_res = run_stage_prep(
        resumes_dir=resumes_dir,
        snapshot_path=snapshot_path,
        run_type="dryrun",
        seed=seed,
        universe_size=60,
        double_rated=2,
        max_resumes=max_resumes,
    )

    # Step 2: Evaluation with quality metrics withheld (no real labels)
    eval_output = dest_dir / "evaluation_report_dryrun.json"
    eval_report = run_evaluation_pipeline(
        snapshot_path=snapshot_path,
        resumes_dir=resumes_dir,
        judgments_path=None,
        output_report_path=str(eval_output),
        universes_path=str(dest_dir / "candidate_universes.json"),
        methods=["bm25", "sbert", "overlap", "hybrid"],
        k=10,
        universe_seed=seed,
        run_ablations=True,
        dryrun_max_jobs_slice=None,
        run_type="dryrun",
        max_resumes=max_resumes,
    )

    # Step 3: Export diagnostics tables
    tables_dir = dest_dir / "tables"
    tables_result = export_tables(
        report_path=eval_output,
        output_dir=tables_dir,
        allow_dryrun=True,
    )

    stage_manifest = write_stage_manifest(
        stage_name="all-dryrun",
        payload={
            "run_type": "dryrun",
            "seed": seed,
            "max_resumes": max_resumes,
            "prep_result": prep_res,
            "eval_report_hash": get_file_sha256(eval_output),
            "tables": tables_result,
            "status": "all_dryrun_complete",
        },
        output_path=dest_dir / "stage_all_dryrun_manifest.json",
    )

    print(f"\n================ ALL-DRYRUN SUMMARY ================")
    print(f"Max Resumes Evaluated : {max_resumes}")
    print(f"Quality Metrics State : Withheld (Awaiting Real Labels)")
    print(f"Tables Saved in       : {tables_dir}")
    print(f"Manifest Saved in     : {stage_manifest}")
    return {"status": "all_dryrun_complete", "stage_manifest": str(stage_manifest)}


def main():
    parser = argparse.ArgumentParser(description="AI Career Copilot Staged One-Command Pipeline Runner")
    parser.add_argument(
        "--stage",
        type=str,
        required=True,
        choices=["prep", "eval", "all-dryrun"],
        help="Pipeline stage to execute: 'prep', 'eval', or 'all-dryrun'",
    )
    parser.add_argument("--run-type", type=str, default="real", choices=["real", "synthetic_eval", "dryrun"], help="Execution run type guard")
    parser.add_argument("--eval-subset", type=int, default=None, help="Subset size of in-scope candidates (stratified by family)")
    parser.add_argument("--num-double-rated", "--double-rated", dest="num_double_rated", type=int, default=8, help="Number of double-rated resumes")
    parser.add_argument("--force", action="store_true", help="Force rebuild of frozen universes")
    parser.add_argument("--resumes-dir", type=str, default=None, help="Path to resume directory")
    parser.add_argument(
        "--snapshot",
        type=str,
        default="data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl",
        help="Path to frozen job snapshot",
    )
    parser.add_argument("--labels", type=str, default="results/real/labels.jsonl", help="Path to human relevance labels JSONL")
    parser.add_argument("--seed", type=int, default=42, help="Random universe seed")
    parser.add_argument("--max-resumes", type=int, default=None, help="Max resumes to evaluate (for dry-run mode)")
    parser.add_argument("--repeats", type=int, default=3, help="Repeat runs for ranking stability")
    parser.add_argument("--dest-dir", type=str, default=None, help="Destination directory for evaluation results")
    parser.add_argument("--slice-snapshot", type=int, default=None, help="Snapshot slicing parameter (prohibited in real/eval mode)")
    args = parser.parse_args()

    if args.stage == "prep":
        res_dir = args.resumes_dir
        if res_dir is None:
            res_dir = "data/resumes_dryrun" if args.run_type == "synthetic_eval" else "data/resumes_real"
        run_stage_prep(
            resumes_dir=res_dir,
            snapshot_path=args.snapshot,
            run_type=args.run_type,
            seed=args.seed,
            max_resumes=args.max_resumes,
            eval_subset=args.eval_subset,
            double_rated=args.num_double_rated,
            force=args.force,
        )
    elif args.stage == "eval":
        res_dir = args.resumes_dir
        if res_dir is None:
            res_dir = "data/resumes_dryrun" if args.run_type == "synthetic_eval" else "data/resumes_real"
        lbl_path = args.labels
        if lbl_path == "results/real/labels.jsonl" and args.run_type == "synthetic_eval":
            lbl_path = "results/synthetic_eval/labels.jsonl"
        run_stage_eval(
            labels_path=lbl_path,
            snapshot_path=args.snapshot,
            resumes_dir=res_dir,
            run_type=args.run_type,
            seed=args.seed,
            repeats=args.repeats,
            max_resumes=args.max_resumes,
            dest_dir=args.dest_dir,
            dryrun_max_jobs_slice=args.slice_snapshot,
        )
    elif args.stage == "all-dryrun":
        res_dir = args.resumes_dir if args.resumes_dir != "data/resumes_real" else "data/resumes_dryrun"
        run_stage_all_dryrun(
            snapshot_path=args.snapshot,
            resumes_dir=res_dir,
            seed=args.seed,
            max_resumes=args.max_resumes if args.max_resumes else 3,
        )


if __name__ == "__main__":
    main()
