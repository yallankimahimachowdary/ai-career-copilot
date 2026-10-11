"""High-speed concurrent backfill for job posting embeddings."""
import asyncio
import math
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import httpx
from sqlalchemy import select
from app.core.config import settings
from app.core.logging import logger
from app.db.session import AsyncSessionLocal
from app.models.job_posting import JobPosting
from app.services.embedding_service import embedding_service


async def get_embedding_with_client(client: httpx.AsyncClient, text: str, sem: asyncio.Semaphore) -> list[float]:
    async with sem:
        if settings.GEMINI_API_KEY:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={settings.GEMINI_API_KEY}"
            payload = {
                "model": "models/gemini-embedding-001",
                "content": {"parts": [{"text": text[:8000]}]},
                "outputDimensionality": settings.EMBEDDING_DIMENSION,
            }
            try:
                resp = await client.post(url, json=payload, timeout=15.0)
                if resp.status_code == 200:
                    data = resp.json()
                    vals = data["embedding"]["values"]
                    norm = math.sqrt(sum(x * x for x in vals))
                    if norm > 0:
                        return [x / norm for x in vals]
                    return vals
            except Exception:
                pass
        # Fallback to deterministic vector
        return embedding_service._generate_deterministic_vector(text)


async def main():
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(JobPosting).where(JobPosting.embedding.is_(None))
        )
        jobs = res.scalars().all()
        total = len(jobs)
        print(f"Total jobs needing embeddings: {total}")
        if total == 0:
            return

        sem = asyncio.Semaphore(12)
        async with httpx.AsyncClient(limits=httpx.Limits(max_keepalive_connections=20, max_connections=30)) as client:
            batch_size = 100
            for start in range(0, total, batch_size):
                chunk = jobs[start : start + batch_size]
                tasks = []
                for j in chunk:
                    text = embedding_service.construct_job_embed_text(
                        title=j.title,
                        description=j.description,
                        skills=j.skills if isinstance(j.skills, list) else [],
                        company=j.company_name or "",
                        location=j.location or "",
                    )
                    tasks.append(get_embedding_with_client(client, text, sem))

                embeddings = await asyncio.gather(*tasks)
                for j, emb in zip(chunk, embeddings):
                    j.embedding = emb

                await session.commit()
                print(f"Embedded & committed {min(start + batch_size, total)}/{total} jobs...")

    print("All job embeddings successfully computed!")


if __name__ == "__main__":
    asyncio.run(main())
