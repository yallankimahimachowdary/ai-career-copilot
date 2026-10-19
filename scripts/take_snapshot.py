"""scripts/take_snapshot.py
-----------------------
Exports frozen job snapshots from Adzuna API with strict quota protection,
SHA-256 verification, read-only file locking, and manifest accounting (Remediation R8).

Usage:
    python scripts/take_snapshot.py --config data/ingest/adzuna_queries_v1.json --label snapshot_1 [--no-fetch] [--max-requests N] [--with-embeddings]
"""

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

import httpx
import numpy as np
import psycopg2
from sqlalchemy import select

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.core.logging import logger
from app.db.session import AsyncSessionLocal
from app.models.job_posting import JobPosting
from app.services.adzuna_quota_guard import (
    AdzunaAuthError,
    AdzunaRateLimitError,
    QuotaExceededError,
    adzuna_quota_guard,
)
from scripts.ingest.adzuna_ingest import adzuna_ingest_service

SNAPSHOT_DIR = Path("data/snapshots")
MANIFEST_FILE = Path("results/snapshots/manifest.jsonl")
TOOL_VERSION = "1.0.0"


def check_services() -> Dict[str, bool]:
    """Verify live status of required services (Postgres, Neo4j, Ollama)."""
    status = {"postgres": False, "neo4j": False, "ollama": False}

    # 1. Postgres
    try:
        db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        conn = psycopg2.connect(db_url, connect_timeout=3)
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        conn.close()
        status["postgres"] = True
    except Exception as e:
        logger.warning(f"Service check failed for PostgreSQL: {e}")

    # 2. Neo4j
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            connection_timeout=3,
        )
        driver.verify_connectivity()
        driver.close()
        status["neo4j"] = True
    except Exception as e:
        logger.warning(f"Service check failed for Neo4j: {e}")

    # 3. Ollama
    try:
        resp = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=3.0)
        if resp.status_code == 200:
            status["ollama"] = True
    except Exception as e:
        logger.warning(f"Service check failed for Ollama: {e}")

    return status


def get_git_commit() -> str:
    """Retrieve current Git commit SHA."""
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "unknown"


def compute_file_sha256(filepath: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()


def set_file_readonly(filepath: Path) -> None:
    """Set file to read-only mode across platforms."""
    try:
        if platform.system() == "Windows":
            subprocess.run(["attrib", "+R", str(filepath)], check=True)
        else:
            filepath.chmod(0o444)
    except Exception as exc:
        logger.warning(f"Failed to set read-only attribute on {filepath}: {exc}")


async def run_adzuna_plan(
    config_data: Dict[str, Any],
    max_requests: Optional[int] = None,
    with_embeddings: bool = False,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Execute Adzuna query allocation plan within quota guard."""
    alloc_rule = config_data.get("allocation_rule", {})
    planned_calls = alloc_rule.get("planned_calls", [])
    country = config_data.get("country", "in")
    results_per_page = config_data.get("results_per_page", 50)
    sort_by = config_data.get("sort_by", "date")
    max_days_old = config_data.get("max_days_old", 30)

    target_calls = planned_calls
    if max_requests is not None and max_requests > 0:
        target_calls = planned_calls[:max_requests]

    all_fetched_records: List[Dict[str, Any]] = []
    run_meta: Dict[str, Any] = {
        "calls_attempted": 0,
        "calls_succeeded": 0,
        "calls_failed": 0,
        "errors": [],
        "stopped_early": False,
        "stop_reason": None,
    }

    print(f"Executing Adzuna plan: {len(target_calls)} calls targeted...")

    for step in target_calls:
        query = step.get("query")
        city = step.get("city")
        family = step.get("family")
        page = step.get("page", 1)

        run_meta["calls_attempted"] += 1
        print(f"  [{run_meta['calls_attempted']}/{len(target_calls)}] Query='{query}', City='{city}', Family='{family}'")

        try:
            report = await adzuna_ingest_service.ingest_jobs(
                query=query,
                city=city,
                page=page,
                results_per_page=results_per_page,
                country=country,
                save_to_live=True,
                with_embeddings=with_embeddings,
            )
            recs = report.get("records", [])
            for r in recs:
                r["role_family"] = family
                r["city"] = city
            all_fetched_records.extend(recs)
            run_meta["calls_succeeded"] += 1

            # Polite spacing between requests
            await asyncio.sleep(adzuna_ingest_service.polite_delay_seconds)

        except (AdzunaRateLimitError, QuotaExceededError, AdzunaAuthError) as fatal_exc:
            run_meta["stopped_early"] = True
            run_meta["stop_reason"] = f"{type(fatal_exc).__name__}: {str(fatal_exc)}"
            run_meta["calls_failed"] += 1
            print(f"    -> CRITICAL: {fatal_exc}. Halting run.")
            break
        except Exception as query_exc:
            run_meta["calls_failed"] += 1
            run_meta["errors"].append({"query": query, "city": city, "error": str(query_exc)})
            print(f"    -> Query failed (non-fatal): {query_exc}")

    return all_fetched_records, run_meta


def compute_metrics(
    records: List[Dict[str, Any]],
    planned_family_map: Dict[str, str],
) -> Dict[str, Any]:
    """Compute data quality, distribution, and null rate statistics across snapshot records."""
    total = len(records)
    if total == 0:
        return {
            "null_rates": {"company": 0.0, "location": 0.0, "published_at": 0.0, "skills": 0.0},
            "skill_distribution": {"min": 0, "p25": 0, "median": 0, "p75": 0, "p90": 0, "max": 0, "share_with_at_least_one": 0.0},
            "description_lengths": {"min": 0, "median": 0, "p90": 0, "max": 0, "share_ge_100": 0.0, "share_ge_500": 0.0, "share_ge_1000": 0.0, "share_ge_2000": 0.0},
            "share_predicted_salary": 0.0,
            "counts": {"fetched": 0, "unique": 0, "after_dedup": 0, "per_family": {}, "per_city": {}},
        }

    # Unique counting by source_job_id
    seen_ids = set()
    unique_records = []
    for r in records:
        jid = r.get("source_job_id")
        if jid not in seen_ids:
            seen_ids.add(jid)
            unique_records.append(r)

    unique_count = len(unique_records)

    # Null rates (on unique postings)
    null_comp = sum(1 for r in unique_records if not r.get("company"))
    null_loc = sum(1 for r in unique_records if not r.get("location"))
    null_pub = sum(1 for r in unique_records if not r.get("posting_date"))
    null_skills = sum(1 for r in unique_records if not r.get("skills"))

    # Skill counts
    skill_counts = [len(r.get("skills") or []) for r in unique_records]
    has_skills = sum(1 for c in skill_counts if c > 0)

    # Description lengths
    desc_lens = [len(r.get("description") or "") for r in unique_records]

    # Predicted salary
    pred_count = sum(1 for r in unique_records if r.get("salary_is_predicted"))

    # Per family and city counts
    family_counts: Dict[str, int] = {}
    city_counts: Dict[str, int] = {}
    for r in unique_records:
        fam = r.get("role_family") or planned_family_map.get(r.get("source_job_id", ""), "unassigned")
        city = r.get("city") or "unassigned"
        family_counts[fam] = family_counts.get(fam, 0) + 1
        city_counts[city] = city_counts.get(city, 0) + 1

    return {
        "counts": {
            "fetched": total,
            "unique": unique_count,
            "after_dedup": unique_count,
            "per_family": family_counts,
            "per_city": city_counts,
        },
        "null_rates": {
            "company": round(null_comp / unique_count, 4),
            "location": round(null_loc / unique_count, 4),
            "published_at": round(null_pub / unique_count, 4),
            "skills": round(null_skills / unique_count, 4),
        },
        "skill_distribution": {
            "min": int(np.min(skill_counts)),
            "p25": int(np.percentile(skill_counts, 25)),
            "median": int(np.median(skill_counts)),
            "p75": int(np.percentile(skill_counts, 75)),
            "p90": int(np.percentile(skill_counts, 90)),
            "max": int(np.max(skill_counts)),
            "share_with_at_least_one": round(has_skills / unique_count, 4),
        },
        "description_lengths": {
            "min": int(np.min(desc_lens)),
            "median": int(np.median(desc_lens)),
            "p90": int(np.percentile(desc_lens, 90)),
            "max": int(np.max(desc_lens)),
            "share_ge_100": round(sum(1 for l in desc_lens if l >= 100) / unique_count, 4),
            "share_ge_500": round(sum(1 for l in desc_lens if l >= 500) / unique_count, 4),
            "share_ge_1000": round(sum(1 for l in desc_lens if l >= 1000) / unique_count, 4),
            "share_ge_2000": round(sum(1 for l in desc_lens if l >= 2000) / unique_count, 4),
        },
        "share_predicted_salary": round(pred_count / unique_count, 4),
    }


async def main_async(args: argparse.Namespace) -> int:
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config file not found at {config_path}")
        return 1

    with open(config_path, "r", encoding="utf-8") as f:
        config_data = json.load(f)

    config_sha256 = compute_file_sha256(config_path)

    # Check services
    services = check_services()
    print("Services Status:", services)
    if not services["postgres"]:
        print("Error: PostgreSQL is required for snapshot export.")
        return 1

    # Check for existing label in manifest or snapshot file
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    target_filename = f"jobs_{args.label}_{today_str}_adzuna.jsonl"
    target_path = SNAPSHOT_DIR / target_filename

    if target_path.exists():
        print(f"Error: Snapshot file already exists at {target_path}. Refusing to overwrite.")
        return 1

    if MANIFEST_FILE.exists():
        with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        entry = json.loads(line)
                        if entry.get("label") == args.label:
                            print(f"Error: Label '{args.label}' already exists in manifest {MANIFEST_FILE}. Refusing overwrite.")
                            return 1
                    except Exception:
                        pass

    # Step 1: Ingestion (unless --no-fetch)
    fetched_records: List[Dict[str, Any]] = []
    plan_meta: Dict[str, Any] = {"stopped_early": False}

    if not args.no_fetch:
        print("\n--- Running Adzuna API Fetch ---")
        fetched_records, plan_meta = await run_adzuna_plan(
            config_data=config_data,
            max_requests=args.max_requests,
            with_embeddings=args.with_embeddings,
        )

    # Step 2: Query database for source="adzuna_api" active postings
    print("\n--- Querying Database for 'adzuna_api' Postings ---")
    async with AsyncSessionLocal() as session:
        stmt = select(JobPosting).where(
            JobPosting.source == "adzuna_api",
            JobPosting.is_active == True,
        ).order_by(JobPosting.source_job_id)
        res = await session.execute(stmt)
        db_jobs = res.scalars().all()

    print(f"Found {len(db_jobs)} active 'adzuna_api' postings in PostgreSQL.")
    if len(db_jobs) == 0:
        print("Warning: Zero 'adzuna_api' records found in database.")

    # Create mapping of source_job_id to role_family/city from fetched records
    id_to_family = {r.get("source_job_id"): r.get("role_family") for r in fetched_records if r.get("source_job_id")}
    id_to_city = {r.get("source_job_id"): r.get("city") for r in fetched_records if r.get("source_job_id")}

    snapshot_records: List[Dict[str, Any]] = []
    for j in db_jobs:
        rec = {
            "id": str(j.id),
            "external_id": j.external_id or f"adzuna_{j.source_job_id}",
            "source_job_id": j.source_job_id,
            "title": j.title,
            "company": j.company_name,
            "location": j.location,
            "description": j.description,
            "posting_date": j.published_at.isoformat() if j.published_at else None,
            "source_url": j.source_url,
            "source": "adzuna_api",
            "work_type": j.work_type,
            "remote_allowed": j.remote_allowed,
            "skills": j.skills if isinstance(j.skills, list) else [],
            "min_salary": j.min_salary,
            "max_salary": j.max_salary,
            "med_salary": j.med_salary,
            "pay_period": j.pay_period,
            "country": j.country,
            "currency": j.currency,
            "salary_is_predicted": (j.min_salary is None and j.max_salary is None),
            "role_family": id_to_family.get(j.source_job_id),
            "city": id_to_city.get(j.source_job_id),
        }
        if args.with_embeddings and j.embedding is not None:
            rec["embedding"] = list(j.embedding)
        snapshot_records.append(rec)

    # Step 3: Write JSONL and set read-only
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        for rec in snapshot_records:
            f.write(json.dumps(rec, default=str) + "\n")

    snapshot_sha256 = compute_file_sha256(target_path)
    set_file_readonly(target_path)
    print(f"Exported snapshot to {target_path} (Read-Only applied).")
    print(f"Snapshot SHA-256: {snapshot_sha256}")

    # Step 4: Compute Metrics & Append Manifest
    metrics = compute_metrics(snapshot_records, id_to_family)
    calls_used = adzuna_quota_guard.get_calls_used()
    call_budget = adzuna_quota_guard.budget
    quota_limited = calls_used >= call_budget or plan_meta.get("stopped_early", False)

    manifest_entry = {
        "label": args.label,
        "date_taken": datetime.now(timezone.utc).isoformat(),
        "source": "adzuna_api",
        "config_sha256": config_sha256,
        "snapshot_sha256": snapshot_sha256,
        "git_commit": get_git_commit(),
        "package_versions": {
            "python": platform.python_version(),
            "httpx": httpx.__version__,
            "sqlalchemy": "2.0.38",
            "sentence-transformers": "3.4.1",
        },
        "quota_limited": quota_limited,
        "call_budget": call_budget,
        "calls_used": calls_used,
        "counts": {
            "requests_used": plan_meta.get("calls_attempted", 0),
            **metrics["counts"],
        },
        "null_rates": metrics["null_rates"],
        "skill_distribution": metrics["skill_distribution"],
        "description_lengths": metrics["description_lengths"],
        "share_predicted_salary": metrics["share_predicted_salary"],
        "terms_url": "https://developer.adzuna.com/docs/terms_of_service",
        "terms_retrieval_date": "2026-10-19",
        "tool_version": TOOL_VERSION,
        "job_text_policy": {
            "adzuna_api_truncation": 500,
            "sbert_ranker_description_cut": 2000,
            "sbert_ranker_resume_cut": 2000,
            "llm_reranker_description_cut": 100,
            "llm_reranker_max_skills_shown": 6,
            "llm_reranker_candidate_pool": 20,
            "chroma_document_cut": 500,
            "embedding_provenance_formula": "Role: {title}\\nCompany: {company}\\nLocation: {location}\\nSkills: {skills}\\nDescription: {description}",
        },
    }

    MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(manifest_entry) + "\n")

    print(f"\nManifest appended to {MANIFEST_FILE}:")
    print(json.dumps(manifest_entry, indent=2))
    adzuna_quota_guard.print_quota_summary()
    return 0


def main():
    parser = argparse.ArgumentParser(description="Adzuna Frozen Job Snapshot Exporter")
    parser.add_argument("--config", type=str, default="data/ingest/adzuna_queries_v1.json", help="Path to queries config JSON")
    parser.add_argument("--label", type=str, required=True, help="Semantic snapshot label (e.g. snapshot_1)")
    parser.add_argument("--no-fetch", action="store_true", help="Skip API fetch and export existing adzuna_api records from DB")
    parser.add_argument("--max-requests", type=int, default=None, help="Maximum API requests to dispatch")
    parser.add_argument("--with-embeddings", action="store_true", help="Include precomputed embeddings in export (opt-in)")

    args = parser.parse_args()
    exit_code = asyncio.run(main_async(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
