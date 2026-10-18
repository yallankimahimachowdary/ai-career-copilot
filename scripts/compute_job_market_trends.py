"""Compute skill market trends from PostgreSQL job_postings and load into job_market_trends table.

Idempotent aggregation script that:
1. Inspects job_postings rows, extracts skills per posting.
2. Groups postings by period:
   - month: 2026-10-01 to 2026-10-31 (period_type='month')
   - snapshot: 2026-10-01 to 2026-10-31 (period_type='snapshot')
3. For each canonical skill:
   - postings_with_skill: count of postings mentioning skill
   - total_postings: total postings in period
   - demand_share: percentage (0.0 to 100.0)
   - source: 'derived_postings'
   - source_snapshot_sha256: hash of sorted posting IDs included in calculation
4. Upserts into job_market_trends on conflict (skill_name, period_start, period_end, period_type, source).
5. Reports total trend rows inserted/updated.
"""

import asyncio
import hashlib
import sys
import uuid
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text
from app.db.session import AsyncSessionLocal
from app.models.job_posting import JobPosting
from app.services.coach_service import _SKILL_PATTERNS
from app.services.matcher_service import FeatureExtractor

CANONICAL_SKILLS = set(_SKILL_PATTERNS.keys())


async def compute_and_load_trends():
    print("Computing job market trends from job_postings...")

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(
                JobPosting.id,
                JobPosting.title,
                JobPosting.description,
                JobPosting.skills,
            )
        )
        postings = result.fetchall()

    total_postings = len(postings)
    print(f"Total job_postings retrieved: {total_postings}")
    if total_postings == 0:
        print("No job postings found. Exiting.")
        return

    # Deterministic snapshot SHA-256
    all_pids = sorted(str(p[0]) for p in postings)
    snapshot_sha = hashlib.sha256(",".join(all_pids).encode("utf-8")).hexdigest().upper()

    # Extract posting-level skills
    skill_counts = defaultdict(int)
    for pid, ptitle, pdesc, pskills in postings:
        raw_skills = pskills if isinstance(pskills, list) else []
        extracted = FeatureExtractor.extract_job_skills(
            description=pdesc or "",
            title=ptitle or "",
            raw_job_skills=raw_skills,
        )
        clean_skills = {s for s in extracted if s in CANONICAL_SKILLS}
        for sk in clean_skills:
            skill_counts[sk] += 1

    # Define periods matching check constraint: period_type IN ('snapshot', 'month')
    periods = [
        (date(2026, 10, 1), date(2026, 10, 31), "month"),
        (date(2026, 10, 1), date(2026, 10, 31), "snapshot"),
    ]

    now = datetime.now(timezone.utc)
    upsert_sql = text("""
        INSERT INTO job_market_trends (
            id, skill_name, period_start, period_end, period_type,
            postings_with_skill, total_postings, demand_share,
            source, source_snapshot_sha256, computed_at
        ) VALUES (
            :id, :skill_name, :period_start, :period_end, :period_type,
            :postings_with_skill, :total_postings, :demand_share,
            :source, :source_snapshot_sha256, :computed_at
        )
        ON CONFLICT (skill_name, period_start, period_end, period_type, source) DO UPDATE SET
            postings_with_skill = EXCLUDED.postings_with_skill,
            total_postings = EXCLUDED.total_postings,
            demand_share = EXCLUDED.demand_share,
            source_snapshot_sha256 = EXCLUDED.source_snapshot_sha256,
            computed_at = EXCLUDED.computed_at
    """)

    total_upserted = 0

    async with AsyncSessionLocal() as session:
        for p_start, p_end, p_type in periods:
            for sk in sorted(CANONICAL_SKILLS):
                cnt = skill_counts.get(sk, 0)
                demand_share = round((cnt / total_postings) * 100.0, 2)

                params = {
                    "id": uuid.uuid4(),
                    "skill_name": sk,
                    "period_start": p_start,
                    "period_end": p_end,
                    "period_type": p_type,
                    "postings_with_skill": cnt,
                    "total_postings": total_postings,
                    "demand_share": demand_share,
                    "source": "derived_postings",
                    "source_snapshot_sha256": snapshot_sha,
                    "computed_at": now,
                }
                await session.execute(upsert_sql, params)
                total_upserted += 1

        await session.commit()

        # Check total trends
        count_res = await session.execute(text("SELECT count(*) FROM job_market_trends"))
        total_rows = count_res.scalar()

        # Top 5 by demand
        top_res = await session.execute(
            text("""
                SELECT skill_name, postings_with_skill, total_postings, demand_share
                FROM job_market_trends
                WHERE period_type = 'month'
                ORDER BY postings_with_skill DESC
                LIMIT 5
            """)
        )
        top_rows = top_res.fetchall()

    print("\n--- JOB MARKET TRENDS SUMMARY ---")
    print(f"  Rows upserted      : {total_upserted}")
    print(f"  Total in table     : {total_rows}")
    print(f"  Snapshot SHA-256   : {snapshot_sha}")
    print("\n  Top 5 Skills by Demand (Monthly):")
    for r in top_rows:
        print(f"    - {r[0]}: {r[1]} / {r[2]} postings ({r[3]}% share)")


if __name__ == "__main__":
    asyncio.run(compute_and_load_trends())
