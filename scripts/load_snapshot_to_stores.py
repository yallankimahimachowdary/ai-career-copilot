"""scripts/load_snapshot_to_stores.py
---------------------------------
Loads frozen jobs snapshot (jobs_snapshot_1_20261019_adzuna.jsonl) into:
1. PostgreSQL (job_postings table) with 384-d vector embeddings
2. ChromaDB (job_postings_embeddings collection)
3. Neo4j (JobPosting nodes, Company nodes, Skill nodes, relationships)

Enforces exact counts (432) and source='adzuna_api' with zero mock rows.
"""

import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.abspath("."))

from sqlalchemy import delete, func, select, text
from app.core.logging import logger
from app.db.neo4j import get_neo4j_driver
from app.db.chroma import get_chroma_client, get_job_postings_collection
from app.db.session import AsyncSessionLocal
from app.models.job_posting import JobPosting
from app.services.embedding_service import embedding_service, get_sentence_transformer
from app.services.graph_service import graph_service

SNAPSHOT_PATH = Path("data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl")


def load_snapshot_records(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Snapshot file not found: {path}")
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


async def load_into_postgres(records: List[Dict[str, Any]], embeddings: List[List[float]]) -> int:
    logger.info("Clearing existing job_postings in PostgreSQL...")
    async with AsyncSessionLocal() as session:
        await session.execute(text("TRUNCATE TABLE job_postings RESTART IDENTITY CASCADE;"))
        await session.commit()

        logger.info(f"Inserting {len(records)} job postings into PostgreSQL...")
        for rec, emb in zip(records, embeddings):
            posting_dt = None
            if rec.get("posting_date"):
                try:
                    posting_dt = datetime.fromisoformat(rec["posting_date"])
                except Exception:
                    posting_dt = datetime.now(timezone.utc)
            now = datetime.now(timezone.utc)

            skills = rec.get("skills") or []
            if isinstance(skills, str):
                try:
                    skills = json.loads(skills)
                except Exception:
                    skills = []

            job = JobPosting(
                id=str(rec["id"]),
                external_id=str(rec.get("external_id") or rec["id"]),
                source_job_id=str(rec.get("source_job_id") or ""),
                title=rec.get("title") or "Untitled",
                company_name=rec.get("company"),
                location=rec.get("location"),
                description=rec.get("description") or "",
                skills=skills,
                work_type=rec.get("work_type"),
                remote_allowed=bool(rec.get("remote_allowed", False)),
                min_salary=float(rec["min_salary"]) if rec.get("min_salary") is not None else None,
                max_salary=float(rec["max_salary"]) if rec.get("max_salary") is not None else None,
                med_salary=float(rec["med_salary"]) if rec.get("med_salary") is not None else None,
                pay_period=rec.get("pay_period"),
                country=rec.get("country") or "India",
                currency=rec.get("currency") or "INR",
                source=rec.get("source") or "adzuna_api",
                source_url=rec.get("source_url"),
                embedding=emb,
                is_active=True,
                freshness_status="fresh",
                published_at=posting_dt,
                first_seen_at=now,
                last_seen_at=now,
                last_refreshed_at=now,
                created_at=posting_dt or now,
                updated_at=now,
            )
            session.add(job)

        await session.commit()

        # Count check
        count = await session.scalar(select(func.count(JobPosting.id)))
        return count


def load_into_chromadb(records: List[Dict[str, Any]], embeddings: List[List[float]], embed_texts: List[str]) -> int:
    logger.info("Resetting job_postings_embeddings collection in ChromaDB...")
    client = get_chroma_client()
    try:
        client.delete_collection("job_postings_embeddings")
    except Exception:
        pass

    col = client.get_or_create_collection(
        name="job_postings_embeddings",
        metadata={"hnsw:space": "cosine"},
    )

    ids = [str(r["id"]) for r in records]
    metadatas = [
        {
            "job_id": str(r["id"]),
            "external_id": str(r.get("external_id") or r["id"]),
            "title": str(r.get("title") or "")[:200],
            "company": str(r.get("company") or "")[:200],
            "location": str(r.get("location") or "")[:200],
            "source": str(r.get("source") or "adzuna_api"),
            "role_family": str(r.get("role_family") or "unknown"),
        }
        for r in records
    ]

    batch_size = 100
    for i in range(0, len(ids), batch_size):
        end = i + batch_size
        col.upsert(
            ids=ids[i:end],
            embeddings=embeddings[i:end],
            documents=embed_texts[i:end],
            metadatas=metadatas[i:end],
        )

    return col.count()


async def load_into_neo4j(records: List[Dict[str, Any]]) -> int:
    logger.info("Clearing existing JobPosting nodes and relationships in Neo4j...")
    driver = get_neo4j_driver()
    async with driver.session() as session:
        await session.run("MATCH (j:JobPosting) DETACH DELETE j")

        logger.info(f"Loading {len(records)} JobPosting nodes into Neo4j in batch...")
        batch_data = []
        for r in records:
            skills = r.get("skills") or []
            if isinstance(skills, str):
                try:
                    skills = json.loads(skills)
                except Exception:
                    skills = []
            salary = r.get("med_salary") or r.get("min_salary") or r.get("max_salary")
            batch_data.append({
                "job_id": str(r["id"]),
                "title": r.get("title") or "Untitled",
                "company_name": r.get("company") or "",
                "location": r.get("location") or "",
                "work_type": r.get("work_type") or "",
                "salary": float(salary) if salary is not None else None,
                "skills": [s.strip().title() for s in skills if s and s.strip()],
            })

        query = """
        UNWIND $batch AS item
        MERGE (j:JobPosting {id: item.job_id})
        SET j.title = item.title,
            j.location = item.location,
            j.work_type = item.work_type,
            j.salary = item.salary,
            j.company_name = item.company_name,
            j.source = 'adzuna_api',
            j.updated_at = datetime()
        WITH j, item
        FOREACH (_ IN CASE WHEN item.company_name <> '' THEN [1] ELSE [] END |
            MERGE (comp:Company {name: item.company_name})
            MERGE (j)-[:POSTED_BY]->(comp)
        )
        WITH j, item
        FOREACH (skill_name IN item.skills |
            MERGE (s:Skill {name: skill_name})
            MERGE (j)-[:REQUIRES]->(s)
        )
        """
        await session.run(query, {"batch": batch_data})

        res = await session.run("RETURN count { MATCH (j:JobPosting) } AS count")
        rec = await res.single()
        return rec["count"]


async def main():
    logger.info(f"Loading snapshot from {SNAPSHOT_PATH}...")
    records = load_snapshot_records(SNAPSHOT_PATH)
    logger.info(f"Loaded {len(records)} records from snapshot 1.")

    # Validate all are adzuna_api
    non_adzuna = [r for r in records if r.get("source") != "adzuna_api"]
    if non_adzuna:
        raise ValueError(f"Found {len(non_adzuna)} records with source != 'adzuna_api'!")

    # Precompute rich embed text and embeddings
    logger.info("Computing 384-d embeddings using SentenceTransformer all-MiniLM-L6-v2...")
    model = get_sentence_transformer()
    embed_texts = []
    for r in records:
        skills = r.get("skills") or []
        if isinstance(skills, str):
            try:
                skills = json.loads(skills)
            except Exception:
                skills = []
        text_chunk = embedding_service.construct_job_embed_text(
            title=r.get("title") or "",
            description=r.get("description") or "",
            skills=skills,
            company=r.get("company") or "",
            location=r.get("location") or "",
        )
        embed_texts.append(text_chunk)

    raw_embs = model.encode(embed_texts, batch_size=64, normalize_embeddings=True)
    embeddings = [[float(x) for x in row] for row in raw_embs]
    logger.info(f"Computed {len(embeddings)} embeddings with dimension {len(embeddings[0])}.")

    # 1. PostgreSQL
    pg_count = await load_into_postgres(records, embeddings)

    # 2. ChromaDB
    chroma_count = load_into_chromadb(records, embeddings, embed_texts)

    # 3. Neo4j
    neo4j_count = await load_into_neo4j(records)

    print("\n==================================================")
    print("STORE VERIFICATION COUNTS FOR SNAPSHOT 1:")
    print(f"  PostgreSQL job_postings: {pg_count} (Expected: 432)")
    print(f"  ChromaDB vectors:        {chroma_count} (Expected: 432)")
    print(f"  Neo4j JobPosting nodes:  {neo4j_count} (Expected: 432)")
    print("==================================================")

    # Verify sources in PostgreSQL
    async with AsyncSessionLocal() as session:
        by_source = (await session.execute(text("SELECT source, count(*) FROM job_postings GROUP BY source;"))).fetchall()
        print("Postgres sources breakdown:")
        for s, c in by_source:
            print(f"  - source={s}: {c}")

    if pg_count != 432 or chroma_count != 432 or neo4j_count != 432:
        raise RuntimeError("Store count mismatch! All stores must equal 432.")
    print("\nSUCCESS: All three stores exactly match 432 records, all tagged source='adzuna_api'.")


if __name__ == "__main__":
    asyncio.run(main())
