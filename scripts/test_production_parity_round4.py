"""
scripts/test_production_parity_round4.py
----------------------------------------
Runs production matcher_agent.match_jobs_for_resume for Mahi and Deepika
and prints ranked top 10 results, scores, deduplication status, and explanations.
"""

import asyncio
from app.db.session import AsyncSessionLocal
from app.models.resume import Resume
from app.services.matcher_service import matcher_agent
from sqlalchemy import select


async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Resume))
        for r in result.scalars().all():
            print("=" * 80)
            print(f"PRODUCTION MATCH FOR: {r.candidate_name} ({r.id})")
            print("=" * 80)
            resp = await matcher_agent.match_jobs_for_resume(r.id, session, limit=10)
            print(f"Total matches returned: {len(resp.matches)}")
            for m in resp.matches:
                co = (m.company_name or "")[:25]
                title = (m.title or "")[:35]
                print(f"#{m.rank:2d} | Score: {m.final_score:.4f} | Job: {title:35s} | Co: {co:25s} | Dups: {m.duplicate_count} | Sources: {m.merged_sources}")
                for exp in m.explanations[:2]:
                    print(f"     -> [{exp.feature_name}] ({exp.shap_value:+.3f}): {exp.description}")
            print()


if __name__ == "__main__":
    asyncio.run(main())
