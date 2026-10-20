"""
scripts/check_dataset_overlap.py
--------------------------------
Dataset Overlap Verification & Role-Family Coverage Audit (R9-5):
1. Detects content contamination between development and test resume sets by comparing SHA-256 hashes.
2. For each resume's 60-job universe, reports overlap with other resumes' universes and with the dev set; flags leakage.
3. Reports per role family (Data/AI, Web/Software, Mobile/UI-UX, Cybersecurity/Cloud,
   Electrical, Mechanical, Civil, Commerce/Finance, Arts/Media) how many snapshot_1 jobs exist
   and whether a 60-job universe can be filled. States plainly which families cannot.
"""

import argparse
from collections import Counter
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
import re

from app.ranking.baselines import BM25Ranker
from scripts.job_snapshot import load_snapshot
from scripts.tune_hybrid_weights import prepare_dev_resumes

ROLE_FAMILIES = {
    "Mobile/UI-UX": ["mobile", "android", "ios", "flutter", "react native", "ui", "ux", "designer", "graphic", "product design"],
    "Cybersecurity/Cloud": ["security", "cyber", "cloud", "aws", "azure", "devops", "linux", "infrastructure", "network"],
    "Electrical": ["electrical", "electronics", "vlsi", "embedded", "hardware", "circuit", "power system"],
    "Mechanical": ["mechanical", "cad", "solidworks", "ansys", "automotive", "manufacturing", "hvac", "thermal"],
    "Civil": ["civil", "structural", "construction", "site engineer", "surveyor", "infrastructure engineer", "autocad civil"],
    "Commerce/Finance": ["finance", "accountant", "accounting", "audit", "banking", "tax", "financial", "commerce"],
    "Arts/Media": ["content", "writer", "copywriter", "media", "video", "editor", "journalist", "creative", "arts"],
    "Data/AI": ["data", "machine learning", "ai", "analytics", "statistic", "deep learning", "nlp", "bi"],
    "Web/Software": ["software", "developer", "full stack", "backend", "frontend", "python", "java", "web", "c++", ".net", "programmer"],
}


def _matches_any_keyword(text: str, kws: List[str]) -> bool:
    for kw in kws:
        if len(kw) <= 3 or " " not in kw:
            if re.search(rf"\b{re.escape(kw)}\b", text, re.IGNORECASE):
                return True
        else:
            if kw in text.lower():
                return True
    return False


def classify_job_family(title: str, description: str = "") -> str:
    """Classify a job title/description into one of the 9 role families."""
    t = (title or "").lower()
    d = (description or "")[:300].lower()
    combined = f"{t} {d}"

    for fam, kws in ROLE_FAMILIES.items():
        if _matches_any_keyword(t, kws):
            return fam
    for fam, kws in ROLE_FAMILIES.items():
        if _matches_any_keyword(combined, kws):
            return fam
    return "Other/Unclassified"


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
            raw_text = f"{entry.get('candidate_name', '')} " + " ".join(entry.get("skills", []))

        test_resumes.append({
            "candidate_name": entry.get("candidate_name") or target_path.stem,
            "resume_file": str(target_path),
            "text": raw_text,
            "skills": entry.get("skills", []),
        })

    return test_resumes


def verify_no_overlap(
    dev_resumes: List[Dict[str, Any]],
    test_resumes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Verify that no resume in the development set shares a content hash with the test set."""
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



def audit_role_family_coverage(jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Report per role family how many snapshot jobs exist and whether a 60-job universe can be filled."""
    counts = Counter()
    for j in jobs:
        fam = classify_job_family(j.get("title", ""), j.get("description", ""))
        counts[fam] += 1

    breakdown = {}
    can_fill = []
    cannot_fill = []

    for fam in list(ROLE_FAMILIES.keys()) + ["Other/Unclassified"]:
        cnt = counts[fam]
        filled = cnt >= 60
        breakdown[fam] = {
            "count": cnt,
            "can_fill_60_universe": filled,
            "deficit": max(0, 60 - cnt),
        }
        if fam != "Other/Unclassified":
            if filled:
                can_fill.append(fam)
            else:
                cannot_fill.append(fam)

    return {
        "total_jobs": len(jobs),
        "breakdown": breakdown,
        "can_fill_families": can_fill,
        "cannot_fill_families": cannot_fill,
    }


def audit_60_job_universe_overlap_and_leakage(
    test_resumes: List[Dict[str, Any]],
    dev_resumes: List[Dict[str, Any]],
    jobs_pool: List[Dict[str, Any]],
    universe_size: int = 60,
) -> Dict[str, Any]:
    """For each resume's 60-job universe, report overlap with other resumes' universes and with dev set."""
    ranker = BM25Ranker()

    def get_universe(resume_dict: Dict[str, Any]) -> Set[str]:
        # Formulate query from text or summary/skills
        res = ranker.rank(resume_dict, jobs_pool, k=min(universe_size, len(jobs_pool)))
        return set(res.ranked_job_ids)

    test_universes: Dict[str, Set[str]] = {}
    for idx, tr in enumerate(test_resumes):
        cand_id = tr.get("candidate_id") or tr.get("candidate_name") or f"test_{idx}"
        test_universes[cand_id] = get_universe(tr)

    dev_universes: Dict[str, Set[str]] = {}
    for idx, dr in enumerate(dev_resumes):
        cand_id = dr.get("candidate_id") or dr.get("candidate_name") or f"dev_{idx}"
        dev_universes[cand_id] = get_universe(dr)

    # Test pairwise overlap
    pairwise = []
    t_ids = list(test_universes.keys())
    for i in range(len(t_ids)):
        for j in range(i + 1, len(t_ids)):
            u_i = test_universes[t_ids[i]]
            u_j = test_universes[t_ids[j]]
            inter = len(u_i & u_j)
            union = len(u_i | u_j)
            pairwise.append({
                "candidate_a": t_ids[i],
                "candidate_b": t_ids[j],
                "shared_job_count": inter,
                "jaccard": round(inter / union, 4) if union else 0.0,
            })

    # Dev leakage check
    dev_checks = []
    leakage_found = False
    for t_id, u_t in test_universes.items():
        for d_id, u_d in dev_universes.items():
            inter = len(u_t & u_d)
            is_leakage = (inter == len(u_t) and len(u_t) > 0)
            if is_leakage:
                leakage_found = True
            dev_checks.append({
                "test_candidate": t_id,
                "dev_candidate": d_id,
                "shared_job_count": inter,
                "jaccard": round(inter / len(u_t | u_d), 4) if (u_t | u_d) else 0.0,
                "leakage_flag": is_leakage,
            })

    return {
        "pairwise_overlaps": pairwise,
        "dev_set_leakage_checks": dev_checks,
        "leakage_detected": leakage_found,
    }


def main():
    parser = argparse.ArgumentParser(description="Audit dataset overlap, role-family coverage, and 60-job universe leakage.")
    parser.add_argument("--test-manifest", type=str, default="data/gold/gold_resumes_skills.json", help="Path to test manifest")
    parser.add_argument("--test-resumes", type=str, default="uploads/resumes", help="Path to test resumes dir")
    parser.add_argument("--dev-manifest", type=str, default=None, help="Optional dev manifest")
    parser.add_argument("--dev-resumes", type=str, default=None, help="Optional dev resumes dir")
    parser.add_argument("--snapshot", type=str, default="data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl", help="Snapshot JSONL path")
    parser.add_argument("--out", type=str, default="results/dataset_overlap_report.json", help="Output report JSON")
    args = parser.parse_args()

    # 1. Content hash overlap check
    dev_resumes = prepare_dev_resumes(resumes_dir=args.dev_resumes, manifest_path=args.dev_manifest)
    test_resumes = load_test_resumes(manifest_path=args.test_manifest, resumes_dir=args.test_resumes)

    print("================ 1. CONTENT HASH OVERLAP CHECK ================")
    overlap_report = verify_no_overlap(dev_resumes, test_resumes)
    print(f"Dev resumes: {overlap_report['dev_count']} | Test resumes: {overlap_report['test_count']}")
    print("Zero content-hash overlap confirmed between dev and test sets.")

    # 2. Role family coverage audit on snapshot
    snapshot_path = Path(args.snapshot)
    if not snapshot_path.exists():
        print(f"[WARN] Snapshot {args.snapshot} not found. Skipping coverage audit.")
        sys.exit(0)

    jobs, snap_meta = load_snapshot(str(snapshot_path))
    cov = audit_role_family_coverage(jobs)
    print("\n================ 2. ROLE FAMILY COVERAGE REPORT (Snapshot 1) ================")
    print(f"Total jobs in snapshot: {cov['total_jobs']}")
    for fam, d in cov["breakdown"].items():
        status = "CAN FILL (>= 60)" if d["can_fill_60_universe"] else f"CANNOT FILL (count: {d['count']}, deficit: {d['deficit']})"
        print(f"  - {fam:22s}: {d['count']:3d} jobs | {status}")

    print("\nPLAIN ENGLISH COVERAGE VERDICT:")
    print(f"  Families that CAN fill a 60-job universe:   {', '.join(cov['can_fill_families'])}")
    print(f"  Families that CANNOT fill a 60-job universe: {', '.join(cov['cannot_fill_families'])}")

    # 3. 60-job universe overlap and leakage audit
    print("\n================ 3. 60-JOB UNIVERSE OVERLAP & LEAKAGE AUDIT ================")
    # Load synthetic/dryrun resumes if available as additional test pool
    synth_path = Path("data/fairness/synthetic_resumes_v1.jsonl")
    extra_test = []
    if synth_path.exists():
        with open(synth_path, "r", encoding="utf-8") as f:
            extra_test = [json.loads(line) for line in f if line.strip()]

    combined_test = test_resumes + extra_test
    universe_audit = audit_60_job_universe_overlap_and_leakage(
        test_resumes=combined_test,
        dev_resumes=dev_resumes,
        jobs_pool=jobs,
        universe_size=60,
    )
    print(f"Total test candidate universes compared: {len(combined_test)}")
    print(f"Pairwise test universe comparisons: {len(universe_audit['pairwise_overlaps'])}")
    print(f"Dev set universe checks: {len(universe_audit['dev_set_leakage_checks'])}")
    print(f"Dev set leakage detected: {universe_audit['leakage_detected']}")

    # Save full report
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    full_report = {
        "content_hash_overlap": overlap_report,
        "role_family_coverage": cov,
        "universe_audit": universe_audit,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=2)
    print(f"\nComplete report saved to {out_path}")


if __name__ == "__main__":
    main()
