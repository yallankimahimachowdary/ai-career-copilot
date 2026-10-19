"""First Live Adzuna Check (Remediation R8 Stage 4).

Executes 2 live calls via AdzunaIngestService under strict Quota Guard protection.
Reports requests used, status codes, rate-limit headers (no secrets),
3 sample parsed postings (title, company, location only),
and database counts before and after.
"""

import asyncio
import json
import os
from pathlib import Path
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import func, select
from app.db.session import AsyncSessionLocal
from app.models.job_posting import JobPosting
from app.services.adzuna_quota_guard import adzuna_quota_guard
from scripts.ingest.adzuna_ingest import adzuna_ingest_service


async def get_db_counts():
    async with AsyncSessionLocal() as session:
        stmt = select(JobPosting.source, func.count(JobPosting.id)).group_by(JobPosting.source)
        res = await session.execute(stmt)
        return dict(res.all())


async def main():
    print("================== ADZUNA LIVE CHECK (STAGE 4.1) ==================")
    counts_before = await get_db_counts()
    print("Database job_postings counts BEFORE live check:")
    for src, cnt in sorted(counts_before.items()):
        print(f"  {src}: {cnt}")
    print(f"  TOTAL: {sum(counts_before.values())}")

    calls_before = adzuna_quota_guard.get_calls_used()
    budget = adzuna_quota_guard.budget
    print(f"\nQuota status before: {calls_before}/{budget} used ({adzuna_quota_guard.get_calls_remaining()} remaining)")

    # Call 1: Data Scientist in Bengaluru
    print("\n--- Dispatching Live Call 1/2: 'Data Scientist' in Bengaluru ---")
    rep1 = await adzuna_ingest_service.ingest_jobs(
        query="Data Scientist",
        city="Bengaluru",
        page=1,
        results_per_page=50,
        country="in",
        save_to_live=True,
        with_embeddings=True,
    )
    print(f"Call 1 Result: HTTP {rep1['status_code']}, Fetched: {rep1['fetched_count']}, Normalized: {rep1['normalized_count']}")
    if rep1.get("batch_result"):
        print(f"  DB Outcomes: {rep1['batch_result']}")

    # Polite spacing
    await asyncio.sleep(adzuna_ingest_service.polite_delay_seconds)

    # Call 2: Full Stack Developer in Hyderabad
    print("\n--- Dispatching Live Call 2/2: 'Full Stack Developer' in Hyderabad ---")
    rep2 = await adzuna_ingest_service.ingest_jobs(
        query="Full Stack Developer",
        city="Hyderabad",
        page=1,
        results_per_page=50,
        country="in",
        save_to_live=True,
        with_embeddings=True,
    )
    print(f"Call 2 Result: HTTP {rep2['status_code']}, Fetched: {rep2['fetched_count']}, Normalized: {rep2['normalized_count']}")
    if rep2.get("batch_result"):
        print(f"  DB Outcomes: {rep2['batch_result']}")

    counts_after = await get_db_counts()
    print("\nDatabase job_postings counts AFTER live check:")
    for src, cnt in sorted(counts_after.items()):
        print(f"  {src}: {cnt}")
    print(f"  TOTAL: {sum(counts_after.values())}")

    # Display 3 sample parsed postings (title, company, location only)
    all_recs = rep1.get("records", []) + rep2.get("records", [])
    print(f"\nSample Parsed Postings (Showing 3 of {len(all_recs)} total fetched):")
    for i, r in enumerate(all_recs[:3], 1):
        print(f"  [{i}] Title:    {r.get('title')}")
        print(f"      Company:  {r.get('company_name') or 'Not specified'}")
        print(f"      Location: {r.get('location') or 'Not specified'}")
        print(f"      Source:   {r.get('source')}, ID: {r.get('source_job_id')}")

    # Counter file state
    print("\nAdzuna Call Counter File Status:")
    adzuna_quota_guard.print_quota_summary()
    counter_path = Path("data/ingest/adzuna_call_counter.json")
    if counter_path.exists():
        with open(counter_path, "r", encoding="utf-8") as f:
            print("Counter File Content:")
            print(f.read())


if __name__ == "__main__":
    asyncio.run(main())
