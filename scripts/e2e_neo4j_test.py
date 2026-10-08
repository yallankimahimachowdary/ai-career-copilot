import sys
import os
sys.path.insert(0, os.path.abspath("."))

import asyncio
import io
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.neo4j import execute_cypher

SAMPLE_RESUME = """Elena Rostova
elena.rostova@example.com | +1 415 555 0199 | San Francisco, CA
linkedin.com/in/elenarostova | github.com/elenarostova

SUMMARY
Senior Distributed Systems and Backend Engineer with 6+ years designing high-scale cloud platforms, event-driven architectures, and microservices in Python, Go, and Kafka.

EXPERIENCE
Senior Backend Engineer | CloudScale Inc | 2021 - Present
- Architected asynchronous event streaming pipeline using Kafka and FastAPI handling 15M events/day.
- Implemented PostgreSQL and Redis caching layers reducing 99th-percentile API latency by 40%.
- Containerized infrastructure on Kubernetes (EKS) and automated CI/CD using GitHub Actions and Docker.

Software Engineer | DataCore Systems | 2018 - 2021
- Developed REST APIs and microservices in Python and PostgreSQL.
- Automated testing with Pytest and integrated AWS S3 for storage.

SKILLS
Python, Go, FastAPI, PostgreSQL, Redis, Kafka, Kubernetes, Docker, AWS, CI/CD, Git, Linux, Distributed Systems

EDUCATION
B.S. in Computer Science | University of Washington | 2018
"""


async def main():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        print("=" * 60)
        print("STEP 1: Uploading Resume through Parser Agent Pipeline")
        print("=" * 60)
        files = {
            "file": ("elena_resume.txt", io.BytesIO(SAMPLE_RESUME.encode("utf-8")), "text/plain")
        }
        resp = await client.post("/api/v1/resumes/upload", files=files)
        print(f"Resume Upload Status: {resp.status_code}")
        assert resp.status_code == 201, resp.text
        upload_data = resp.json()
        resume_id = upload_data["id"]
        cand_name = upload_data["candidate_name"]
        print(f"Candidate: {cand_name} (Resume ID: {resume_id})")

        print("\n" + "=" * 60)
        print("STEP 2: Querying Neo4j Graph for (Candidate)-[:HAS_SKILL]->(Skill)")
        print("=" * 60)
        cand_query = """
        MATCH (c:Candidate {id: $id})-[r:HAS_SKILL]->(s:Skill)
        RETURN c.name AS name, collect(s.name) AS skills
        """
        cand_nodes = await execute_cypher(cand_query, {"id": resume_id})
        print(f"Candidate node in Neo4j: {cand_nodes[0]['name']}")
        print(f"Skills attached in Neo4j ({len(cand_nodes[0]['skills'])} skills): {cand_nodes[0]['skills']}")

        print("\n" + "=" * 60)
        print("STEP 3: Running Matcher Agent Pipeline")
        print("=" * 60)
        match_resp = await client.post(f"/api/v1/matches/resume/{resume_id}?limit=5")
        print(f"Match Response Status: {match_resp.status_code}")
        assert match_resp.status_code == 200, match_resp.text
        matches_data = match_resp.json()
        print(f"Total Matches Found: {matches_data['total_matches']}")
        for m in matches_data["matches"]:
            print(f"  - Rank {m['rank']}: {m['title']} @ {m['company_name']} (Final Score: {m['final_score']})")

        print("\n" + "=" * 60)
        print("STEP 4: Verifying (Candidate)-[:MATCHED_TO]->(JobPosting) in Neo4j")
        print("=" * 60)
        match_edges_query = """
        MATCH (c:Candidate {id: $id})-[r:MATCHED_TO]->(j:JobPosting)
        OPTIONAL MATCH (j)-[:POSTED_BY]->(comp:Company)
        OPTIONAL MATCH (j)-[:REQUIRES]->(s:Skill)
        RETURN j.title AS job_title, comp.name AS company, r.score AS graph_score, r.rank AS rank,
               collect(DISTINCT s.name) AS required_skills
        ORDER BY r.rank ASC
        """
        match_edges = await execute_cypher(match_edges_query, {"id": resume_id})
        print(f"MATCHED_TO edges in Neo4j ({len(match_edges)} edges):")
        for edge in match_edges:
            print(f"  - Rank {edge['rank']}: {edge['job_title']} @ {edge['company']} | Score: {edge['graph_score']}")
            print(f"    Required skills in graph: {edge['required_skills'][:6]}")

        print("\n" + "=" * 60)
        print("STEP 5: Testing Graph Read Queries (Postgres can't easily do)")
        print("=" * 60)
        # 5a. Role Bridge
        bridge_resp = await client.get(
            "/api/v1/graph/bridge-skills",
            params={"from_role": "Software Engineer", "to_role": "Data Scientist"},
        )
        assert bridge_resp.status_code == 200, bridge_resp.text
        b_data = bridge_resp.json()
        print(f"Role Bridge Overlap: {b_data['transition_overlap_pct']}%")
        print(f"Shared Foundation: {b_data['shared_foundation_skills'][:5]}")
        print(f"Stepping Stone Skills: {b_data['stepping_stone_bridge_skills']}")
        print(f"Summary: {b_data['bridge_summary']}")

        # 5b. Candidate 2-Hop Career Pathway
        pathway_resp = await client.get(f"/api/v1/graph/career-pathway/{resume_id}")
        assert pathway_resp.status_code == 200, pathway_resp.text
        p_data = pathway_resp.json()
        print(f"\nCandidate Career Pathway for {p_data['candidate_name']}:")
        print("High-Leverage Bridge Skills:")
        for s in p_data["high_leverage_bridge_skills"][:4]:
            print(f"  * {s['skill']}: unlocks {s['unlocks_postings_count']} jobs (demand weight: {s['demand_weight']})")
        print(f"Graph Insight: {p_data['graph_insight']}")

        print("\n" + "=" * 60)
        print("STEP 6: Overall Neo4j Graph Database Metrics")
        print("=" * 60)
        stats_resp = await client.get("/api/v1/graph/stats")
        print(stats_resp.json())


if __name__ == "__main__":
    asyncio.run(main())
