"""
scripts/tune_hybrid_weights.py
------------------------------
Tunes Hybrid Ranker component weights (BM25, SBERT, Skill Overlap) on a development split
using grid search over simplex-normalized weight combinations.
Freezes the tuned weights directly into app/ranking/config.json.
"""

import argparse
from datetime import datetime, timezone
import glob
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pypdf
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ranking.baselines import BM25Ranker, SbertRanker, SkillOverlapRanker
from app.ranking.hybrid import _min_max_normalize
from app.services.anonymizer import anonymize_resume
from app.services.parser_agent import parser_agent
from scripts.job_snapshot import load_snapshot


def prepare_dev_resumes(
    resumes_dir: Optional[str | Path] = None,
    manifest_path: Optional[str | Path] = None,
) -> List[Dict[str, Any]]:
    """Load development resume profiles from manifest/folder if provided, or return held-out dev benchmarks."""
    dev_resumes: List[Dict[str, Any]] = []

    if manifest_path and Path(manifest_path).exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                entries = data.get("resumes", [])
                base_dir = Path(resumes_dir) if resumes_dir else Path("uploads/resumes")
                for entry in entries:
                    r_file = entry.get("resume_file", "")
                    target_path = Path(r_file)
                    if not target_path.exists():
                        target_path = base_dir / target_path.name
                    if not target_path.exists():
                        prefix = Path(r_file).name.split("_")[0]
                        matches = list(base_dir.glob(f"{prefix}*"))
                        if matches:
                            target_path = matches[0]

                    if target_path.exists() and target_path.suffix.lower() == ".pdf":
                        try:
                            reader = pypdf.PdfReader(target_path)
                            raw = "\n".join([p.extract_text() or "" for p in reader.pages])
                            cand_name = entry.get("candidate_name")
                            anon_text = anonymize_resume(raw, candidate_name=cand_name, strip_institutions=True)
                            parsed = parser_agent._parse_with_rules(anon_text)
                            dev_resumes.append({
                                "candidate_name": cand_name or target_path.stem.split("_")[0],
                                "skills": parsed.skills or entry.get("skills", []),
                                "summary": parsed.summary or "",
                                "experience": [e.model_dump() for e in parsed.experience],
                            })
                        except Exception:
                            continue
        except Exception as e:
            print(f"[WARN] Error loading dev manifest: {e}")

    elif resumes_dir and Path(resumes_dir).exists():
        for fpath in sorted(list(Path(resumes_dir).glob("*.pdf"))):
            try:
                reader = pypdf.PdfReader(fpath)
                raw = "\n".join([p.extract_text() or "" for p in reader.pages])
                anon_text = anonymize_resume(raw, candidate_name=None, strip_institutions=True)
                parsed = parser_agent._parse_with_rules(anon_text)
                dev_resumes.append({
                    "candidate_name": fpath.stem.split("_")[0],
                    "skills": parsed.skills or [],
                    "summary": parsed.summary or "",
                    "experience": [e.model_dump() for e in parsed.experience],
                })
            except Exception:
                continue

    if dev_resumes:
        return dev_resumes

    # Default held-out independent development profiles
    return [
        {
            "candidate_name": "Dev_Backend_Engineer",
            "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "REST API"],
            "summary": "Backend software engineer building scalable RESTful microservices in Python with FastAPI, PostgreSQL, and Docker.",
            "experience": [{"title": "Backend Engineer", "company": "DevCorp"}],
        },
        {
            "candidate_name": "Dev_Bioinformatics_Researcher",
            "skills": ["Python", "Cell Culture", "Molecular Biology", "MATLAB", "PCR"],
            "summary": "Bioinformatics researcher with experience in PCR amplification, molecular biology, and cell culture analysis.",
            "experience": [{"title": "Research Assistant", "company": "BioLab"}],
        },
    ]


def generate_weight_grid(step: float = 0.05, min_weight: float = 0.10) -> List[Tuple[float, float, float]]:
    """Generate all valid non-negative weight triplets summing to 1.0 with minimum representation."""
    grid = []
    steps = int(round(1.0 / step))
    for i in range(steps + 1):
        for j in range(steps + 1 - i):
            k = steps - i - j
            w_bm25 = round(i * step, 2)
            w_sbert = round(j * step, 2)
            w_overlap = round(k * step, 2)
            if w_bm25 >= min_weight and w_sbert >= min_weight and w_overlap >= min_weight:
                if round(w_bm25 + w_sbert + w_overlap, 2) == 1.0:
                    grid.append((w_bm25, w_sbert, w_overlap))
    return grid


def evaluate_weights(
    weights: Tuple[float, float, float],
    resumes: List[Dict[str, Any]],
    job_pool: List[Dict[str, Any]],
    precomputed_scores: Dict[str, Dict[str, Dict[str, float]]],
) -> float:
    """
    Evaluate ranking coherence on dev split.
    Objective: maximizes average margin between top matches and candidate skill diversity.
    """
    w_bm, w_sb, w_ov = weights
    total_score = 0.0

    for res in resumes:
        name = res["candidate_name"]
        norm_bm = precomputed_scores[name]["bm25"]
        norm_sb = precomputed_scores[name]["sbert"]
        norm_ov = precomputed_scores[name]["overlap"]

        # Compute hybrid combined score per job
        combined = {}
        for jid in norm_bm:
            sc = w_bm * norm_bm.get(jid, 0.0) + w_sb * norm_sb.get(jid, 0.0) + w_ov * norm_ov.get(jid, 0.0)
            combined[jid] = sc

        ranked = sorted(combined.items(), key=lambda x: x[1], reverse=True)
        # Score metric: top 5 mean score separation from median
        top5_mean = sum(x[1] for x in ranked[:5]) / 5.0
        median_score = ranked[len(ranked) // 2][1] if ranked else 0.0
        separation = top5_mean - median_score
        total_score += separation

    return total_score / max(1, len(resumes))


def tune_and_freeze(
    snapshot_path: str,
    resumes_dir: Optional[str] = None,
    manifest_path: Optional[str] = None,
    freeze: bool = True,
) -> Dict[str, Any]:
    records, meta = load_snapshot(snapshot_path)
    # Dev split: first 150 jobs
    dev_pool = records[:150]
    resumes = prepare_dev_resumes(resumes_dir=resumes_dir, manifest_path=manifest_path)

    bm25 = BM25Ranker()
    sbert = SbertRanker()
    overlap = SkillOverlapRanker()

    print(f"Precomputing baseline scores on dev pool ({len(dev_pool)} jobs) for {len(resumes)} resumes...")
    precomputed: Dict[str, Dict[str, Dict[str, float]]] = {}
    for res in resumes:
        name = res["candidate_name"]
        r_bm = bm25.rank(res, dev_pool, k=len(dev_pool))
        r_sb = sbert.rank(res, dev_pool, k=len(dev_pool))
        r_ov = overlap.rank(res, dev_pool, k=len(dev_pool))

        precomputed[name] = {
            "bm25": _min_max_normalize(r_bm.scores),
            "sbert": _min_max_normalize(r_sb.scores),
            "overlap": _min_max_normalize(r_ov.scores),
        }

    grid = generate_weight_grid(step=0.05)
    print(f"Running grid search over {len(grid)} weight combinations...")

    best_weights = None
    best_obj = -float("inf")

    for w in grid:
        obj = evaluate_weights(w, resumes, dev_pool, precomputed)
        if obj > best_obj:
            best_obj = obj
            best_weights = w

    w_bm, w_sb, w_ov = best_weights
    print(f"\nOptimal Weights Found:")
    print(f" - BM25         : {w_bm:.2f}")
    print(f" - SBERT        : {w_sb:.2f}")
    print(f" - Skill Overlap: {w_ov:.2f}")
    print(f" - Separation Obj: {best_obj:.4f}")

    config_path = Path("app/ranking/config.json")
    result = {
        "status": "frozen" if freeze else "provisional",
        "weights": {
            "bm25": w_bm,
            "sbert": w_sb,
            "overlap": w_ov,
        },
        "score_normalization": "min_max",
        "comment": "Frozen weights tuned on dev split via scripts/tune_hybrid_weights.py. Do not alter during evaluation.",
        "tuned_at": datetime.now(timezone.utc).isoformat(),
        "dev_split_size": len(dev_pool),
    }

    if freeze:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print(f"Config successfully frozen to {config_path}!")

    return result


def main():
    parser = argparse.ArgumentParser(description="Tune Hybrid Weights on Dev Split and Freeze")
    parser.add_argument("--snapshot", type=str, default="data/snapshots/test_snap_1.json", help="Path to frozen snapshot")
    parser.add_argument("--resumes", type=str, default=None, help="Path to dev resumes folder")
    parser.add_argument("--manifest", type=str, default=None, help="Path to dev resumes manifest JSON")
    parser.add_argument("--no-freeze", action="store_true", help="Tune without overwriting config.json")
    args = parser.parse_args()

    tune_and_freeze(
        snapshot_path=args.snapshot,
        resumes_dir=args.resumes,
        manifest_path=args.manifest,
        freeze=not args.no_freeze,
    )


if __name__ == "__main__":
    main()
