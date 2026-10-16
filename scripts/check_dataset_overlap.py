"""
scripts/check_dataset_overlap.py
--------------------------------
Dataset Overlap Verification:
Detects data leakage and dataset contamination between development and test resume sets
by comparing normalized content SHA-256 hashes.

Exits with code 1 if any content hash appears in both splits.
Exits with code 0 if splits are strictly disjoint.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure project root is in sys.path when executed directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pypdf

from scripts.tune_hybrid_weights import prepare_dev_resumes


def compute_content_hash(text: str) -> str:
    """Compute normalized SHA-256 hash of resume content."""
    normalized = " ".join(text.strip().lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def extract_text_from_pdf(pdf_path: Path | str) -> str:
    """Extract raw text from PDF file."""
    path = Path(pdf_path)
    if not path.exists():
        return ""
    try:
        reader = pypdf.PdfReader(path)
        return "\n".join([page.extract_text() or "" for page in reader.pages]).strip()
    except Exception:
        return ""


def load_test_resumes(
    manifest_path: str = "data/gold/gold_resumes_skills.json",
    resumes_dir: str = "uploads/resumes",
) -> List[Dict[str, Any]]:
    """Load test benchmark resumes defined in the gold manifest."""
    man_path = Path(manifest_path)
    if not man_path.exists():
        return []

    with open(man_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    test_resumes: List[Dict[str, Any]] = []
    base_dir = Path(resumes_dir)

    for entry in data.get("resumes", []):
        r_file = entry.get("resume_file", "")
        target_path = Path(r_file)
        if not target_path.exists():
            target_path = base_dir / target_path.name
        if not target_path.exists():
            prefix = Path(r_file).name.split("_")[0]
            matches = list(base_dir.glob(f"{prefix}*"))
            if matches:
                target_path = matches[0]

        raw_text = extract_text_from_pdf(target_path) if target_path.exists() else ""
        if not raw_text:
            # Fallback to skills + candidate name representation
            raw_text = f"{entry.get('candidate_name', '')} " + " ".join(entry.get("skills", []))

        test_resumes.append({
            "candidate_name": entry.get("candidate_name") or target_path.stem,
            "resume_file": str(target_path),
            "text": raw_text,
        })

    return test_resumes


def verify_no_overlap(
    dev_resumes: List[Dict[str, Any]],
    test_resumes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Verify that no resume in the development set shares a content hash with the test set.

    Raises ValueError if overlap / contamination is detected.
    Returns audit report dictionary if clean.
    """
    dev_hashes: Dict[str, List[str]] = {}
    for d in dev_resumes:
        text = d.get("text") or (d.get("summary", "") + " " + " ".join(d.get("skills", [])))
        h = compute_content_hash(text)
        dev_hashes.setdefault(h, []).append(d.get("candidate_name", "unknown_dev"))

    test_hashes: Dict[str, List[str]] = {}
    for t in test_resumes:
        text = t.get("text") or (t.get("summary", "") + " " + " ".join(t.get("skills", [])))
        h = compute_content_hash(text)
        test_hashes.setdefault(h, []).append(t.get("candidate_name", "unknown_test"))

    overlapping_hashes = sorted(list(set(dev_hashes.keys()) & set(test_hashes.keys())))

    report = {
        "dev_count": len(dev_resumes),
        "test_count": len(test_resumes),
        "dev_unique_hashes": len(dev_hashes),
        "test_unique_hashes": len(test_hashes),
        "has_overlap": len(overlapping_hashes) > 0,
        "overlapping_count": len(overlapping_hashes),
        "overlapping_details": [
            {
                "hash": h,
                "dev_candidates": dev_hashes[h],
                "test_candidates": test_hashes[h],
            }
            for h in overlapping_hashes
        ],
    }

    if report["has_overlap"]:
        msg = (
            f"Dataset overlap detected! {len(overlapping_hashes)} resume(s) exist in both "
            f"dev and test splits: {report['overlapping_details']}"
        )
        raise ValueError(msg)

    return report


def main():
    parser = argparse.ArgumentParser(description="Check for dataset overlap between dev and test resumes")
    parser.add_argument("--test-manifest", type=str, default="data/gold/gold_resumes_skills.json", help="Path to test manifest")
    parser.add_argument("--test-resumes", type=str, default="uploads/resumes", help="Path to test resumes dir")
    parser.add_argument("--dev-manifest", type=str, default=None, help="Optional dev manifest")
    parser.add_argument("--dev-resumes", type=str, default=None, help="Optional dev resumes dir")
    args = parser.parse_args()

    dev_resumes = prepare_dev_resumes(resumes_dir=args.dev_resumes, manifest_path=args.dev_manifest)
    test_resumes = load_test_resumes(manifest_path=args.test_manifest, resumes_dir=args.test_resumes)

    try:
        report = verify_no_overlap(dev_resumes, test_resumes)
        print("================ Dataset Overlap Check: PASSED ================")
        print(f"Dev resumes evaluated  : {report['dev_count']}")
        print(f"Test resumes evaluated : {report['test_count']}")
        print(f"Contamination count    : {report['overlapping_count']}")
        print("Zero dataset overlap confirmed between dev and test sets.")
        sys.exit(0)
    except ValueError as err:
        print("================ Dataset Overlap Check: FAILED ================")
        print(str(err))
        sys.exit(1)


if __name__ == "__main__":
    main()
