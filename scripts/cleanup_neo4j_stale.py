"""Clean up stale JobPostings in Neo4j that no longer exist in PostgreSQL."""

import sys
sys.path.insert(0, ".")

import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.job_posting import JobPosting
from app.db.neo4j import execute_cypher

async def prune_stale_neo4j_jobs():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(JobPosting.id))
        pg_ids = set(str(r) for r in res.scalars().all())
        print(f"Valid PostgreSQL JobPosting IDs: {len(pg_ids)}")

    r = await execute_cypher("MATCH (j:JobPosting) RETURN j.id AS id")
    neo_ids = set(row["id"] for row in r if row.get("id"))
    print(f"Current Neo4j JobPosting nodes: {len(neo_ids)}")

    stale_ids = list(neo_ids - pg_ids)
    print(f"Stale JobPosting IDs to delete: {len(stale_ids)}")

    if stale_ids:
        # Delete in batches of 200
        batch_size = 200
        for i in range(0, len(stale_ids), batch_size):
            batch = stale_ids[i:i + batch_size]
            await execute_cypher(
                "UNWIND $batch AS sid MATCH (j:JobPosting {id: sid}) DETACH DELETE j",
                {"batch": batch},
                raise_on_error=True
            )
        print("Successfully deleted stale JobPostings.")

    # Remove orphan companies
    await execute_cypher(
        "MATCH (c:Company) WHERE NOT (c)<-[:POSTED_BY]-(:JobPosting) DETACH DELETE c",
        raise_on_error=True
    )
    print("Cleaned orphan Company nodes.")

    # Verify counts
    r_jobs = await execute_cypher("RETURN count { MATCH (j:JobPosting) } AS c")
    r_comps = await execute_cypher("RETURN count { MATCH (c:Company) } AS c")
    r_cands = await execute_cypher("RETURN count { MATCH (c:Candidate) } AS c")
    r_skills = await execute_cypher("RETURN count { MATCH (s:Skill) } AS c")
    r_rels = await execute_cypher("RETURN count { MATCH ()-[r]->() } AS c")

    print("\n=== FINAL NEO4J GRAPH METRICS ===")
    print(f"  JobPostings: {r_jobs[0]['c']} (PostgreSQL: {len(pg_ids)})")
    print(f"  Companies: {r_comps[0]['c']}")
    print(f"  Candidates: {r_cands[0]['c']}")
    print(f"  Skills: {r_skills[0]['c']}")
    print(f"  Total Relationships: {r_rels[0]['c']}")

if __name__ == "__main__":
    asyncio.run(prune_stale_neo4j_jobs())
