#!/usr/bin/env python3
"""
scripts/make_annotation_sheets.py
---------------------------------
Generates blinded annotation sheets and assignment manifests for human raters (R11-3).

Guarantees:
1. Two raters (A, B). Each in-scope candidate resume gets one primary rater, balanced.
2. A seeded subset of 8 resumes (or fewer if fewer exist) is double-rated (assigned to both A and B).
3. Assignment manifest records resume allocations, seeds, and SHA-256 asset hashes.
4. Per-rater CSV contains:
   - resume_alias
   - anonymized_resume_text_path
   - job_id (shuffled within resume using the seed)
   - title
   - company
   - location
   - description (as stored, note <= 500 chars)
   - rating (BLANK)
   - notes (BLANK)
5. Scale: 0=not relevant, 1=partially relevant, 2=strong fit printed in the sheet.
6. ZERO method scores, ranks, model outputs, or predicted salaries visible.
"""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import random
import sys
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.job_snapshot import load_snapshot

ANNOTATION_SCALE_HEADER = [
    "# ANNOTATION GUIDELINES & RATING SCALE:",
    "# 0 = Not relevant (Irrelevant role, mismatched domain, or incompatible qualifications)",
    "# 1 = Partially relevant (Adjacent domain, partial skill overlap, or potential growth role)",
    "# 2 = Strong fit (Direct qualification match, strong skill overlap, and role alignment)",
    "# Instructions: Enter integer 0, 1, or 2 in the 'rating' column. Leave notes optional.",
    "# Blinded Sheet: No algorithmic ranks, scores, or predicted salaries are included.",
]


def assign_raters(
    candidate_ids: List[str],
    seed: int = 42,
    num_double_rated: int = 8,
) -> Dict[str, Any]:
    """Deterministically assign candidates to Rater A, Rater B, and double-rated overlap."""
    rng = random.Random(seed)
    shuffled_cands = sorted(list(candidate_ids))
    rng.shuffle(shuffled_cands)

    n_double = min(num_double_rated, len(shuffled_cands))
    double_rated = sorted(shuffled_cands[:n_double])
    single_pool = shuffled_cands[n_double:]

    # Balanced split of remaining single-rated resumes
    rater_a_singles = []
    rater_b_singles = []
    for idx, cid in enumerate(single_pool):
        if idx % 2 == 0:
            rater_a_singles.append(cid)
        else:
            rater_b_singles.append(cid)

    rater_a_all = sorted(double_rated + rater_a_singles)
    rater_b_all = sorted(double_rated + rater_b_singles)

    return {
        "seed": seed,
        "double_rated_candidates": double_rated,
        "rater_a_candidates": rater_a_all,
        "rater_b_candidates": rater_b_all,
        "counts": {
            "total_in_scope_candidates": len(candidate_ids),
            "double_rated_count": len(double_rated),
            "rater_a_candidate_count": len(rater_a_all),
            "rater_b_candidate_count": len(rater_b_all),
        },
    }


def make_annotation_sheets(
    universes_json_path: Path | str,
    snapshot_path: Path | str,
    output_dir: Path | str,
    seed: int = 42,
    num_double_rated: int = 8,
    run_type: str = "dryrun",
) -> Dict[str, Any]:
    """Generate blinded per-rater CSV sheets and assignment manifest."""
    univ_p = Path(universes_json_path)
    if not univ_p.exists():
        raise FileNotFoundError(f"Universes JSON not found: {univ_p}")

    with open(univ_p, "r", encoding="utf-8") as f:
        univ_data = json.load(f)

    # Filter strictly in-scope candidates with non-empty universes
    cand_universes = univ_data.get("candidate_universes", {})
    in_scope_map = {
        cid: u for cid, u in cand_universes.items()
        if u.get("is_in_scope") and not u.get("out_of_scope_for_ranking_eval") and u.get("job_ids")
    }

    if not in_scope_map:
        raise ValueError(f"No in-scope candidate universes found in {univ_p}")

    # Load job snapshot details
    jobs, snap_meta = load_snapshot(str(snapshot_path))
    job_map = {j["id"]: j for j in jobs}

    assignments = assign_raters(list(in_scope_map.keys()), seed=seed, num_double_rated=num_double_rated)

    out_d = Path(output_dir)
    out_d.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "resume_alias",
        "anonymized_resume_text_path",
        "job_id",
        "title",
        "company",
        "location",
        "description",
        "rating",
        "notes",
    ]

    rater_loads = {}
    sheet_hashes = {}

    for rater_id in ["rater_a", "rater_b"]:
        cands_for_rater = assignments[f"{rater_id}_candidates"]
        csv_path = out_d / f"annotation_sheet_{rater_id}_{run_type}.csv"
        
        rows_to_write = []
        for cid in cands_for_rater:
            job_ids = list(in_scope_map[cid]["job_ids"])
            # Shuffle jobs within resume deterministically using seed + candidate hash
            job_rng = random.Random(seed + hash(cid) % 1000000)
            job_rng.shuffle(job_ids)

            for jid in job_ids:
                job_rec = job_map.get(jid, {})
                title = job_rec.get("title") or ""
                company = job_rec.get("company") or job_rec.get("company_name") or "Not specified"
                location = job_rec.get("location") or "Not specified"
                desc = (job_rec.get("description") or "").replace("\r", " ").replace("\n", " ")[:500]

                rows_to_write.append({
                    "resume_alias": cid,
                    "anonymized_resume_text_path": f"data/resumes_dryrun/{cid}.txt" if run_type == "dryrun" else f"data/resumes/{cid}.txt",
                    "job_id": jid,
                    "title": title,
                    "company": company,
                    "location": location,
                    "description": desc,
                    "rating": "",  # Strictly BLANK
                    "notes": "",   # Strictly BLANK
                })

        rater_loads[rater_id] = len(rows_to_write)

        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            for comment_line in ANNOTATION_SCALE_HEADER:
                f.write(comment_line + "\n")
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows_to_write)

        # Compute SHA-256 of generated sheet
        sheet_hashes[rater_id] = hashlib.sha256(csv_path.read_bytes()).hexdigest().upper()

    manifest = {
        "run_type": run_type,
        "seed": seed,
        "universes_json_path": str(univ_p),
        "snapshot_path": str(snapshot_path),
        "snapshot_sha256": snap_meta.get("sha256_hash"),
        "assignments": assignments,
        "pairs_per_rater": rater_loads,
        "sheet_sha256": sheet_hashes,
    }

    manifest_path = out_d / f"assignment_manifest_{run_type}.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest().upper()
    manifest["manifest_sha256"] = manifest_sha256

    return manifest


def main():
    parser = argparse.ArgumentParser(description="Make blinded human annotation sheets and assignment manifest.")
    parser.add_argument("--universes", type=str, default="results/dryrun/universes_dryrun.json", help="Path to universes JSON")
    parser.add_argument("--snapshot", type=str, default="data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl", help="Snapshot JSONL path")
    parser.add_argument("--output-dir", type=str, default="results/dryrun/annotations", help="Directory to save sheets")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed")
    parser.add_argument("--double-rated", type=int, default=8, help="Number of double-rated resumes")
    parser.add_argument("--run-type", type=str, default="dryrun", choices=["dryrun", "real"], help="Execution run type")

    args = parser.parse_args()

    manifest = make_annotation_sheets(
        universes_json_path=args.universes,
        snapshot_path=args.snapshot,
        output_dir=args.output_dir,
        seed=args.seed,
        num_double_rated=args.double_rated,
        run_type=args.run_type,
    )

    print("================ ANNOTATION SHEETS GENERATED ================")
    print(f"Run Type            : {manifest['run_type']}")
    print(f"Seed                : {manifest['seed']}")
    print(f"Total Candidates    : {manifest['assignments']['counts']['total_in_scope_candidates']}")
    print(f"Double-Rated Resumes: {manifest['assignments']['counts']['double_rated_count']}")
    print(f"Pairs for Rater A   : {manifest['pairs_per_rater']['rater_a']}")
    print(f"Pairs for Rater B   : {manifest['pairs_per_rater']['rater_b']}")
    print(f"Manifest SHA-256    : {manifest['manifest_sha256']}")
    print(f"Saved in            : {args.output_dir}")


if __name__ == "__main__":
    main()
