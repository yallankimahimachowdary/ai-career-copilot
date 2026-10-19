"""scripts/compare_snapshots.py
--------------------------
Compares two frozen job snapshots for turnover, posting age distributions,
and per-skill demand count shifts (Remediation R8).

Usage:
    python scripts/compare_snapshots.py <labelA> <labelB> [--allow-config-diff] [--manifest results/snapshots/manifest.jsonl]
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Set, Tuple

import numpy as np

MANIFEST_DEFAULT = Path("results/snapshots/manifest.jsonl")
SNAPSHOT_DIR_DEFAULT = Path("data/snapshots")


def load_manifest_entry(manifest_path: Path, label: str) -> Dict[str, Any]:
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest file not found at {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if entry.get("label") == label:
                    return entry
            except Exception:
                continue
    raise ValueError(f"Label '{label}' not found in manifest {manifest_path}")


def load_snapshot_records(snapshots_dir: Path, label: str) -> Tuple[List[Dict[str, Any]], Path]:
    matching_files = list(snapshots_dir.glob(f"jobs_{label}_*_adzuna.jsonl"))
    if not matching_files:
        raise FileNotFoundError(f"No snapshot file found for label '{label}' in {snapshots_dir}")

    filepath = matching_files[0]
    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records, filepath


def compare_snapshots(
    label_a: str,
    label_b: str,
    allow_config_diff: bool = False,
    manifest_path: Path = MANIFEST_DEFAULT,
    snapshots_dir: Path = SNAPSHOT_DIR_DEFAULT,
) -> Dict[str, Any]:
    meta_a = load_manifest_entry(manifest_path, label_a)
    meta_b = load_manifest_entry(manifest_path, label_b)

    cfg_a = meta_a.get("config_sha256")
    cfg_b = meta_b.get("config_sha256")

    if cfg_a != cfg_b and not allow_config_diff:
        print(f"\n[ERROR] Configuration SHA-256 hashes differ between snapshots!")
        print(f"  {label_a} config hash: {cfg_a}")
        print(f"  {label_b} config hash: {cfg_b}")
        print("Comparison refused because settings differ. To override, pass --allow-config-diff.")
        sys.exit(2)

    records_a, file_a = load_snapshot_records(snapshots_dir, label_a)
    records_b, file_b = load_snapshot_records(snapshots_dir, label_b)

    map_a = {str(r.get("source_job_id")): r for r in records_a if r.get("source_job_id")}
    map_b = {str(r.get("source_job_id")): r for r in records_b if r.get("source_job_id")}

    ids_a = set(map_a.keys())
    ids_b = set(map_b.keys())

    overlap_ids = ids_a & ids_b
    new_ids = ids_b - ids_a
    disappeared_ids = ids_a - ids_b

    turnover_rate = round(len(disappeared_ids) / len(ids_a), 4) if len(ids_a) > 0 else 0.0

    # Posting-age statistics (days from posting_date to snapshot date_taken)
    def compute_ages(records: List[Dict[str, Any]], snapshot_date_iso: str) -> List[float]:
        try:
            snap_dt = datetime.fromisoformat(snapshot_date_iso.replace("Z", "+00:00"))
        except Exception:
            snap_dt = datetime.now(timezone.utc)

        ages = []
        for r in records:
            p_date_str = r.get("posting_date")
            if p_date_str:
                try:
                    p_dt = datetime.fromisoformat(p_date_str.replace("Z", "+00:00"))
                    age_days = (snap_dt - p_dt).total_seconds() / 86400.0
                    ages.append(max(0.0, age_days))
                except Exception:
                    pass
        return ages

    ages_a = compute_ages(records_a, meta_a.get("date_taken", ""))
    ages_b = compute_ages(records_b, meta_b.get("date_taken", ""))

    age_stats_a = {
        "mean_days": round(float(np.mean(ages_a)), 2) if ages_a else 0.0,
        "median_days": round(float(np.median(ages_a)), 2) if ages_a else 0.0,
        "p90_days": round(float(np.percentile(ages_a, 90)), 2) if ages_a else 0.0,
    }
    age_stats_b = {
        "mean_days": round(float(np.mean(ages_b)), 2) if ages_b else 0.0,
        "median_days": round(float(np.median(ages_b)), 2) if ages_b else 0.0,
        "p90_days": round(float(np.percentile(ages_b, 90)), 2) if ages_b else 0.0,
    }

    # Per-skill demand counts and shifts (strictly counts, no significance claims)
    def count_skills(records: List[Dict[str, Any]]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for r in records:
            for s in (r.get("skills") or []):
                counts[s] = counts.get(s, 0) + 1
        return counts

    skill_counts_a = count_skills(records_a)
    skill_counts_b = count_skills(records_b)

    all_skills = sorted(set(skill_counts_a.keys()) | set(skill_counts_b.keys()))
    skill_shifts: Dict[str, Dict[str, int]] = {}
    for s in all_skills:
        cnt_a = skill_counts_a.get(s, 0)
        cnt_b = skill_counts_b.get(s, 0)
        delta = cnt_b - cnt_a
        skill_shifts[s] = {
            f"count_{label_a}": cnt_a,
            f"count_{label_b}": cnt_b,
            "shift_delta": delta,
        }

    # Top gaining and top declining skills
    sorted_by_shift = sorted(skill_shifts.items(), key=lambda x: x[1]["shift_delta"], reverse=True)
    top_gaining = sorted_by_shift[:10]
    top_declining = sorted_by_shift[-10:]

    report = {
        "comparison": f"{label_a} vs {label_b}",
        "config_hash_match": (cfg_a == cfg_b),
        "snapshot_a": {
            "label": label_a,
            "file": str(file_a),
            "date_taken": meta_a.get("date_taken"),
            "unique_postings": len(ids_a),
            "age_stats": age_stats_a,
        },
        "snapshot_b": {
            "label": label_b,
            "file": str(file_b),
            "date_taken": meta_b.get("date_taken"),
            "unique_postings": len(ids_b),
            "age_stats": age_stats_b,
        },
        "turnover": {
            "overlap_count": len(overlap_ids),
            "new_postings_count": len(new_ids),
            "disappeared_postings_count": len(disappeared_ids),
            "turnover_rate": turnover_rate,
        },
        "top_gaining_skills": {k: v for k, v in top_gaining if v["shift_delta"] > 0},
        "top_declining_skills": {k: v for k, v in top_declining if v["shift_delta"] < 0},
    }

    print(f"\n================ SNAPSHOT COMPARISON REPORT ================")
    print(f"Comparing Snapshot A: {label_a} ({meta_a.get('date_taken')})")
    print(f"       to Snapshot B: {label_b} ({meta_b.get('date_taken')})")
    print(f"Config Match:         {'YES' if (cfg_a == cfg_b) else 'NO (Overridden)'}")
    print(f"-----------------------------------------------------------")
    print(f"Postings in A:        {len(ids_a)}")
    print(f"Postings in B:        {len(ids_b)}")
    print(f"Retained (Overlap):   {len(overlap_ids)}")
    print(f"New Postings (in B):  {len(new_ids)}")
    print(f"Disappeared (from A): {len(disappeared_ids)}")
    print(f"Turnover Rate:        {turnover_rate * 100:.2f}%")
    print(f"-----------------------------------------------------------")
    print(f"Age in A (Median):    {age_stats_a['median_days']} days (Mean: {age_stats_a['mean_days']}d)")
    print(f"Age in B (Median):    {age_stats_b['median_days']} days (Mean: {age_stats_b['mean_days']}d)")
    print(f"===========================================================\n")

    return report


def main():
    parser = argparse.ArgumentParser(description="Compare two frozen job snapshots for turnover and skill count shifts")
    parser.add_argument("label_a", type=str, help="Baseline snapshot label (e.g. snapshot_1)")
    parser.add_argument("label_b", type=str, help="Follow-up snapshot label (e.g. snapshot_2)")
    parser.add_argument("--allow-config-diff", action="store_true", help="Allow comparison even if config hashes differ")
    parser.add_argument("--manifest", type=str, default=str(MANIFEST_DEFAULT), help="Path to manifest.jsonl")

    args = parser.parse_args()
    compare_snapshots(
        label_a=args.label_a,
        label_b=args.label_b,
        allow_config_diff=args.allow_config_diff,
        manifest_path=Path(args.manifest),
    )


if __name__ == "__main__":
    main()
