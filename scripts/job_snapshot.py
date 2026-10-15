"""Frozen Job Snapshot Exporter and Loader."""

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.job_posting import JobPosting

SNAPSHOT_DIR = Path("data/snapshots")
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)


def compute_snapshot_hash(records: List[Dict[str, Any]]) -> str:
    """Compute deterministic SHA-256 hash over normalized records."""
    # Sort by external_id or title to guarantee deterministic ordering
    sorted_recs = sorted(records, key=lambda r: (r.get("external_id") or "", r.get("title") or ""))
    canonical_json = json.dumps(sorted_recs, sort_keys=True, default=str)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


async def export_snapshot(output_filename: str | None = None) -> Tuple[Path, str, int]:
    """Export current PostgreSQL job postings into a frozen dated snapshot file with SHA-256 verification."""
    async with AsyncSessionLocal() as db:
        jobs = (await db.execute(select(JobPosting))).scalars().all()
        records: List[Dict[str, Any]] = []
        for j in jobs:
            records.append({
                "id": str(j.id),
                "external_id": j.external_id or str(j.id),
                "title": j.title,
                "company": j.company_name,
                "location": j.location,
                "description": j.description,
                "posting_date": j.created_at.isoformat() if j.created_at else None,
                "source_url": j.external_id if (j.external_id and str(j.external_id).startswith("http")) else None,
                "fetch_time": j.updated_at.isoformat() if j.updated_at else datetime.now(timezone.utc).isoformat(),
                "source": j.source or "scraper",
                "work_type": j.work_type,
                "remote_allowed": j.remote_allowed,
                "skills": j.skills if isinstance(j.skills, list) else [],
                "min_salary": j.min_salary,
                "max_salary": j.max_salary,
                "med_salary": j.med_salary,
                "pay_period": j.pay_period,
                "country": j.country or "India",
                "currency": j.currency or "INR",
            })

    sha256_hash = compute_snapshot_hash(records)
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    target_path = SNAPSHOT_DIR / (output_filename or f"jobs_snapshot_{today_str}.json")

    snapshot_payload = {
        "metadata": {
            "snapshot_version": "1.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "record_count": len(records),
            "sha256_hash": sha256_hash,
        },
        "records": records,
    }

    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(snapshot_payload, f, indent=2, default=str)

    return target_path, sha256_hash, len(records)


def load_snapshot(snapshot_path: Path | str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Load a frozen snapshot file and verify its SHA-256 integrity."""
    path = Path(snapshot_path)
    if not path.exists():
        raise FileNotFoundError(f"Snapshot not found at {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    meta = data.get("metadata", {})
    records = data.get("records", [])
    expected_hash = meta.get("sha256_hash")

    actual_hash = compute_snapshot_hash(records)
    if expected_hash and actual_hash != expected_hash:
        raise ValueError(f"Snapshot hash mismatch! Expected {expected_hash}, calculated {actual_hash}")

    return records, meta


def run_matching_on_snapshot(
    snapshot_records: List[Dict[str, Any]],
    resume_parsed_data: Dict[str, Any],
    resume_embedding: List[float],
    top_k: int = 10,
) -> List[Dict[str, Any]]:
    """
    Run deterministic Matcher ranking pipeline directly on frozen snapshot records.
    Computes cosine distance, feature extraction, and composite/XGBoost scores without DB access.
    """
    import numpy as np
    from app.services.matcher_service import FeatureExtractor, CompositeScorer, matcher_agent

    cand_emb = np.array(resume_embedding, dtype=np.float32)
    norm_cand = np.linalg.norm(cand_emb)
    if norm_cand > 0:
        cand_emb = cand_emb / norm_cand

    scored_candidates = []

    for rec in snapshot_records:
        job_id = rec.get("id") or rec.get("external_id")
        title = rec.get("title") or ""
        desc = rec.get("description") or ""
        skills = rec.get("skills") or []
        if isinstance(skills, str):
            try:
                skills = json.loads(skills)
            except Exception:
                skills = []

        # If job has precomputed embedding in record, use it; otherwise compute title+desc similarity
        if "embedding" in rec and rec["embedding"]:
            job_emb = np.array(rec["embedding"], dtype=np.float32)
            norm_j = np.linalg.norm(job_emb)
            if norm_j > 0:
                job_emb = job_emb / norm_j
            cos_sim = float(np.dot(cand_emb, job_emb))
            cos_dist = max(0.0, 1.0 - cos_sim)
        else:
            # Deterministic semantic distance proxy from keyword/title overlap when raw vector is absent
            cand_skills = resume_parsed_data.get("skills", [])
            shared = sum(1 for s in cand_skills if FeatureExtractor.is_skill_match(s, title) or s.lower() in desc.lower())
            cos_sim = min(0.95, 0.40 + 0.05 * shared)
            cos_dist = 1.0 - cos_sim

        final_score, composite_score, xgb_score, features, skills_breakdown, explanations = (
            matcher_agent.score_job(
                parsed_resume=resume_parsed_data,
                job_title=title,
                job_description=desc,
                job_skills=skills,
                semantic_distance=cos_dist,
            )
        )

        scored_candidates.append({
            "job_id": str(job_id),
            "external_id": rec.get("external_id"),
            "title": title,
            "company": rec.get("company"),
            "final_score": round(final_score, 4),
            "composite_score": round(composite_score, 4),
            "xgboost_score": round(xgb_score, 4),
            "matched_skills": skills_breakdown.matched_skills,
        })

    # Sort descending by final_score, breaking ties deterministically by composite_score and job_id
    scored_candidates.sort(key=lambda x: (x["final_score"], x["composite_score"], str(x["job_id"])), reverse=True)
    return scored_candidates[:top_k]
