#!/usr/bin/env python3
"""
scripts/build_universes.py
---------------------------
Constructs evaluation job universes and seeded dev/test resume splits (R11-2).

Policy:
- Role Family Scope: Read from docs/eval_scope.json. Only candidates in EVAL_ROLE_FAMILIES
  are in-scope for ranking evaluation. Candidates from deficit families are parsed and
  flagged out_of_scope_for_ranking_eval=True.
- Universe sampling: Seeded sample from the candidate's role family job pool,
  stratified by job seniority bucket (intern, junior, mid, senior, lead).
  If pool < universe_size, universe_truncated=True and actual_size=len(pool).
  (Seniority gating is NOT applied here; all family postings are eligible).
- Split by resume: Seeded 20/80 dev/test split across in-scope resumes.
- Disjointness guarantee: No candidate resume can exist in both dev and test.
- Provenance: Full provenance record included in output metadata.
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pypdf

from app.core.provenance import build_provenance_record
from app.core.seniority import classify_job_seniority
from app.services.anonymizer import anonymize_resume
from app.services.parser_agent import parser_agent
from scripts.check_dataset_overlap import ROLE_FAMILIES, classify_job_family
from scripts.job_snapshot import load_snapshot


def load_eval_scope(scope_path: Path | str = "docs/eval_scope.json") -> Tuple[Set[str], Set[str]]:
    """Load evaluation scope families from docs/eval_scope.json."""
    p = Path(scope_path)
    if not p.exists():
        # Default fallback if file is missing
        return {"Data/AI", "Web/Software", "Cybersecurity/Cloud"}, {
            "Mobile/UI-UX", "Electrical", "Mechanical", "Civil", "Commerce/Finance", "Arts/Media"
        }
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    return set(data.get("eval_role_families", [])), set(data.get("deficit_families_excluded_from_ranking_eval", []))


def classify_resume_family(resume_text: str, parsed_skills: List[str]) -> str:
    """Classify candidate resume into one of the 9 role families using text and skills."""
    t_lower = (resume_text or "").lower()
    
    # Priority matching on profile/title tokens
    scores = Counter()
    for fam, kws in ROLE_FAMILIES.items():
        for kw in kws:
            if len(kw) <= 3 or " " not in kw:
                if re.search(rf"\b{re.escape(kw)}\b", t_lower):
                    scores[fam] += 1
            else:
                if kw in t_lower:
                    scores[fam] += 1
                    
    if scores:
        return scores.most_common(1)[0][0]
    return "Other/Unclassified"


def stable_hash_int(s: str, max_val: int = 1000000) -> int:
    """Deterministic integer hash independent of PYTHONHASHSEED."""
    h_bytes = hashlib.sha256(s.encode("utf-8")).digest()
    val = int.from_bytes(h_bytes[:4], byteorder="big")
    return val % max_val


def sample_stratified_universe(
    jobs_pool: List[Dict[str, Any]],
    universe_size: int,
    rng: random.Random,
) -> Tuple[List[Dict[str, Any]], bool]:
    """Sample jobs stratified across seniority buckets (intern, junior, mid, senior, lead)."""
    if len(jobs_pool) <= universe_size:
        # If pool <= size, use entire pool and mark truncated
        # Sort deterministically by id before returning
        shuffled = sorted(list(jobs_pool), key=lambda x: str(x.get("id") or ""))
        rng.shuffle(shuffled)
        return shuffled, True

    # Group jobs by seniority bucket
    by_bucket: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for j in sorted(jobs_pool, key=lambda x: str(x.get("id") or "")):
        sen = classify_job_seniority(j.get("title", ""), j.get("description", ""))
        by_bucket[sen].append(j)

    bucket_names = sorted(by_bucket.keys())
    # Shuffle each bucket deterministically
    for b_name in bucket_names:
        rng.shuffle(by_bucket[b_name])

    selected: List[Dict[str, Any]] = []
    
    # Proportional allocation across buckets
    total_pool = len(jobs_pool)
    remaining_slots = universe_size

    # First pass: allocate floor proportion to each bucket with jobs
    allocations = {}
    for b_name in bucket_names:
        b_len = len(by_bucket[b_name])
        prop = int((b_len / total_pool) * universe_size)
        alloc = min(max(prop, 1 if b_len > 0 else 0), b_len)
        allocations[b_name] = alloc
        remaining_slots -= alloc

    # Second pass: distribute remaining slots to largest remainder buckets
    idx = 0
    while remaining_slots > 0 and idx < len(bucket_names) * 3:
        b_name = bucket_names[idx % len(bucket_names)]
        if len(by_bucket[b_name]) > allocations[b_name]:
            allocations[b_name] += 1
            remaining_slots -= 1
        idx += 1

    for b_name in bucket_names:
        n_take = allocations[b_name]
        selected.extend(by_bucket[b_name][:n_take])

    # Final shuffle of selected universe
    rng.shuffle(selected)
    return selected[:universe_size], False


def compute_pairwise_universe_overlap(universes: Dict[str, List[str]]) -> Dict[str, float]:
    """Compute mean, min, max pairwise Jaccard overlap across candidate universes."""
    cand_ids = list(universes.keys())
    if len(cand_ids) < 2:
        return {"mean_jaccard": 0.0, "max_jaccard": 0.0, "min_jaccard": 0.0, "num_pairs": 0}

    jaccards = []
    for i in range(len(cand_ids)):
        set_a = set(universes[cand_ids[i]])
        for j in range(i + 1, len(cand_ids)):
            set_b = set(universes[cand_ids[j]])
            if not set_a and not set_b:
                continue
            intersection = len(set_a.intersection(set_b))
            union = len(set_a.union(set_b))
            jaccard = intersection / union if union > 0 else 0.0
            jaccards.append(jaccard)

    if not jaccards:
        return {"mean_jaccard": 0.0, "max_jaccard": 0.0, "min_jaccard": 0.0, "num_pairs": 0}

    return {
        "mean_jaccard": round(sum(jaccards) / len(jaccards), 4),
        "max_jaccard": round(max(jaccards), 4),
        "min_jaccard": round(min(jaccards), 4),
        "num_pairs": len(jaccards),
    }


def build_universes(
    snapshot_path: Path | str,
    resumes_dir: Path | str,
    seed: int = 42,
    universe_size: int = 60,
    dev_ratio: float = 0.20,
    run_type: str = "dryrun",
    max_resumes: Optional[int] = None,
    output_path: Optional[Path | str] = None,
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Build evaluation universes and dev/test resume split with full determinism."""
    rng = random.Random(seed)
    in_scope_families, deficit_families = load_eval_scope()

    # 1. Load jobs snapshot
    jobs, snap_meta = load_snapshot(str(snapshot_path))
    
    # Group jobs by family
    jobs_by_family: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for j in jobs:
        fam = classify_job_family(j.get("title", ""), j.get("description", ""))
        jobs_by_family[fam].append(j)

    # 2. Load candidate resumes
    res_dir = Path(resumes_dir)
    pdf_files = sorted(list(res_dir.glob("*.pdf")))
    if max_resumes is not None:
        pdf_files = pdf_files[:max_resumes]

    candidates = []
    for pdf_path in pdf_files:
        try:
            reader = pypdf.PdfReader(pdf_path)
            raw_text = "\n".join([p.extract_text() or "" for p in reader.pages])
        except Exception:
            raw_text = ""

        anon_text = anonymize_resume(raw_text, strip_institutions=True)
        parsed = parser_agent._parse_with_rules(anon_text)
        
        # ID extraction
        parts = pdf_path.stem.split("_")
        cand_id = f"{parts[0]}_{parts[1]}" if len(parts) > 1 and parts[0] == "SYN" else parts[0]
        
        family = classify_resume_family(raw_text, parsed.skills or [])
        is_in_scope = family in in_scope_families

        candidates.append({
            "candidate_id": cand_id,
            "file_name": pdf_path.name,
            "role_family": family,
            "is_in_scope": is_in_scope,
            "skills": parsed.skills or [],
            "raw_text_length": len(raw_text),
        })

    # 3. Partition in-scope candidates into dev and test (seeded by resume)
    in_scope_candidates = [c for c in candidates if c["is_in_scope"]]
    out_of_scope_candidates = [c for c in candidates if not c["is_in_scope"]]

    # Shuffle in-scope candidates deterministically before splitting
    shuffled_in_scope = list(in_scope_candidates)
    rng.shuffle(shuffled_in_scope)

    n_dev = int(len(shuffled_in_scope) * dev_ratio)
    dev_candidates = shuffled_in_scope[:n_dev]
    test_candidates = shuffled_in_scope[n_dev:]

    dev_ids = {c["candidate_id"] for c in dev_candidates}
    test_ids = {c["candidate_id"] for c in test_candidates}
    
    # Assert disjointness guarantee
    intersection = dev_ids.intersection(test_ids)
    if intersection:
        raise ValueError(f"Split violation: candidates appear in both dev and test sets: {intersection}")

    # 4. Build universe per candidate
    candidate_universes: Dict[str, Dict[str, Any]] = {}
    universe_job_id_map: Dict[str, List[str]] = {}
    total_pairs_to_annotate = 0

    for cand in candidates:
        cid = cand["candidate_id"]
        fam = cand["role_family"]
        is_in_scope = cand["is_in_scope"]

        split_assignment = "dev" if cid in dev_ids else ("test" if cid in test_ids else "out_of_scope")

        if not is_in_scope:
            continue

        family_pool = jobs_by_family.get(fam, [])
        cand_rng = random.Random(seed + stable_hash_int(cid))
        selected_jobs, is_truncated = sample_stratified_universe(family_pool, universe_size, cand_rng)
        
        job_ids = [j["id"] for j in selected_jobs]
        candidate_universes[cid] = {
            "candidate_id": cid,
            "role_family": fam,
            "is_in_scope": True,
            "out_of_scope_for_ranking_eval": False,
            "split": split_assignment,
            "universe_truncated": is_truncated,
            "universe_size": len(selected_jobs),
            "job_ids": job_ids,
        }
        universe_job_id_map[cid] = job_ids
        total_pairs_to_annotate += len(selected_jobs)

    # 5. Overlap stats
    overlap_stats = compute_pairwise_universe_overlap(universe_job_id_map)

    # 6. Provenance Record
    provenance = build_provenance_record(
        requested_model="deterministic_sampler",
        returned_model="deterministic_sampler",
        seed=seed,
        run_type=run_type,
        snapshot_hash=snap_meta.get("sha256_hash"),
        strict_model_match=False,
    )
    if timestamp:
        provenance["timestamp"] = timestamp

    summary = {
        "metadata": {
            "seed": seed,
            "universe_size_target": universe_size,
            "dev_ratio": dev_ratio,
            "run_type": run_type,
            "snapshot_path": str(snapshot_path),
            "snapshot_sha256": snap_meta.get("sha256_hash"),
            "provenance": provenance,
        },
        "counts": {
            "total_candidates_processed": len(candidates),
            "in_scope_candidates": len(in_scope_candidates),
            "out_of_scope_candidates": len(out_of_scope_candidates),
            "dev_candidates_count": len(dev_candidates),
            "test_candidates_count": len(test_candidates),
            "total_pairs_to_annotate": total_pairs_to_annotate,
        },
        "in_scope_families": sorted(list(in_scope_families)),
        "deficit_families_excluded": sorted(list(deficit_families)),
        "overlap_stats": overlap_stats,
        "candidate_universes": candidate_universes,
    }

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

    return summary


def main():
    parser = argparse.ArgumentParser(description="Build evaluation universes and dev/test splits.")
    parser.add_argument("--snapshot", type=str, default="data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl", help="Snapshot JSONL path")
    parser.add_argument("--resumes-dir", type=str, default="data/resumes_dryrun", help="Resumes directory")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed")
    parser.add_argument("--universe-size", type=int, default=60, help="Target universe size")
    parser.add_argument("--dev-ratio", type=float, default=0.20, help="Dev split proportion")
    parser.add_argument("--run-type", type=str, default="dryrun", choices=["dryrun", "real"], help="Execution run type")
    parser.add_argument("--max-resumes", type=int, default=None, help="Maximum resumes to load")
    parser.add_argument("--timestamp", type=str, default=None, help="Fixed timestamp for deterministic test reproducibility")
    parser.add_argument("--output", type=str, default=None, help="Output JSON path")

    args = parser.parse_args()

    out = args.output
    if not out:
        base = "results/dryrun" if args.run_type == "dryrun" else "results/real"
        out = f"{base}/universes_{args.run_type}.json"

    res = build_universes(
        snapshot_path=args.snapshot,
        resumes_dir=args.resumes_dir,
        seed=args.seed,
        universe_size=args.universe_size,
        dev_ratio=args.dev_ratio,
        run_type=args.run_type,
        max_resumes=args.max_resumes,
        output_path=out,
        timestamp=args.timestamp,
    )

    print("================ UNIVERSE BUILDER SUMMARY ================")
    print(f"Total Candidates Loaded : {res['counts']['total_candidates_processed']}")
    print(f"In-Scope Candidates     : {res['counts']['in_scope_candidates']}")
    print(f"Out-of-Scope Candidates : {res['counts']['out_of_scope_candidates']}")
    print(f"Dev Split Candidates    : {res['counts']['dev_candidates_count']}")
    print(f"Test Split Candidates   : {res['counts']['test_candidates_count']}")
    print(f"Total Pairs to Annotate : {res['counts']['total_pairs_to_annotate']}")
    print(f"Mean Pairwise Overlap   : {res['overlap_stats']['mean_jaccard']:.4f}")
    print(f"Saved to                : {out}")


if __name__ == "__main__":
    main()
