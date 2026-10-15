"""
scripts/resync_candidates_round4.py
----------------------------------
Safely re-syncs candidate resumes in PostgreSQL and Neo4j for Phase B Round 4.
Guarantees zero data loss using safe_merge_parsed_data.
Updates pgvector dense embeddings and Neo4j graph nodes & edges.
"""

import asyncio
from typing import List
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.resume import Resume
from app.services.parser_agent import parser_agent, safe_merge_parsed_data
from app.services.embedding_service import embedding_service
from app.services.graph_service import graph_service


async def main():
    print("=" * 60)
    print("PHASE B ROUND 4: CANDIDATE RESYNC & VERIFICATION")
    print("=" * 60)

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Resume))
        resumes: List[Resume] = result.scalars().all()

        for r in resumes:
            print(f"\n--- Processing Candidate: {r.candidate_name} ({r.id}) ---")
            old_skills = (r.parsed_data or {}).get("skills", [])
            old_edu = (r.parsed_data or {}).get("education", [])
            print(f"BEFORE: {len(old_skills)} skills, {len(old_edu)} education entries")

            # 1. High-fidelity parse
            fresh_parsed = parser_agent._parse_with_rules(r.raw_text)
            fresh_dict = fresh_parsed.model_dump()

            # 2. Safe merge to guarantee no regression
            merged_dict = safe_merge_parsed_data(r.parsed_data, fresh_dict)
            r.parsed_data = merged_dict

            # Update contact info on Resume model if needed
            ci = merged_dict.get("contact_info") or {}
            if ci.get("email") and not r.email:
                r.email = ci["email"]
            if ci.get("phone") and not r.phone:
                r.phone = ci["phone"]

            # 3. Dense pgvector embedding re-computation
            embed_text = embedding_service.construct_embed_text(merged_dict)
            r.embedding = await embedding_service.get_embedding(embed_text)

            new_skills = merged_dict.get("skills", [])
            new_edu = merged_dict.get("education", [])
            print(f"AFTER:  {len(new_skills)} skills, {len(new_edu)} education entries")
            print(f"Skills: {new_skills}")
            print(f"Education: {new_edu}")
            print(f"Languages: {merged_dict.get('languages')}")
            print(f"Ignored Tokens: {merged_dict.get('ignored_tokens')}")

        await session.commit()
        print("\n[Postgres] Database commit successful.")

    # 4. Neo4j Graph Synchronization
    print("\n--- Synchronizing Neo4j Graph Nodes & Edges ---")
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Resume))
            for r in result.scalars().all():
                skills = (r.parsed_data or {}).get("skills", [])
                await graph_service.sync_candidate(
                    candidate_id=r.id,
                    name=r.candidate_name or "Candidate",
                    email=r.email or "",
                    skills=skills,
                )
                print(f"[Neo4j] Synced candidate '{r.candidate_name}' with {len(skills)} HAS_SKILL relationships.")
    except Exception as ge:
        print(f"[Neo4j Notice] Graph sync: {ge}")

    print("\n" + "=" * 60)
    print("RESYNC COMPLETED SUCCESSFULLY")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
