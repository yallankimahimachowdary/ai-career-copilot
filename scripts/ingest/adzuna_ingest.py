"""Adzuna API Ingestion script for Indian job market with dual write to PostgreSQL and ChromaDB."""

import asyncio
from datetime import datetime, timezone
import hashlib
import os
from typing import Any, Dict, List, Optional
import httpx
from sqlalchemy.dialects.postgresql import insert

from app.core.config import settings
from app.core.logging import logger
from app.core.taxonomy import extract_canonical_skills
from app.db.chroma import chroma_service
from app.db.session import AsyncSessionLocal
from app.models.job_posting import JobPosting
from app.services.embedding_service import embedding_service


class AdzunaIngestService:
    """Ingest job postings from Adzuna (India: country='in') with mock and live support."""

    def __init__(self):
        # Read strictly from environment, never from code
        self.app_id = os.environ.get("ADZUNA_APP_ID")
        self.app_key = os.environ.get("ADZUNA_APP_KEY")
        self.base_url = "https://api.adzuna.com/v1/api/jobs/in/search"

    async def fetch_jobs(
        self,
        query: str = "Software Engineer",
        page: int = 1,
        results_per_page: int = 10,
        mock_response: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch jobs from Adzuna API, with automatic mock fallback when credentials are not present."""
        if not self.app_id or not self.app_key or mock_response is not None:
            logger.info("ADZUNA credentials not configured or mock requested. Using standardized mocked API response.")
            return mock_response or [
                {
                    "id": "adzuna_mock_001",
                    "title": f"Senior {query} - Distributed Cloud",
                    "company": {"display_name": "Adzuna Cloud Partners India"},
                    "location": {"display_name": "Bengaluru, Karnataka"},
                    "description": f"Looking for a {query} skilled in Python, FastAPI, Docker, and Kubernetes. Hands-on experience required.",
                    "created": datetime.now(timezone.utc).isoformat(),
                    "redirect_url": "https://www.adzuna.in/jobs/details/adzuna_mock_001",
                    "salary_min": 1200000.0,
                    "salary_max": 2400000.0,
                    "contract_time": "full_time",
                },
                {
                    "id": "adzuna_mock_002",
                    "title": f"Lead {query} - Biotechnology Informatics",
                    "company": {"display_name": "GeneTech India Ltd"},
                    "location": {"display_name": "Hyderabad, Telangana"},
                    "description": f"Seeking a {query} with Bioinformatics, Python, PCR, NGS, and Clinical Data analysis expertise.",
                    "created": datetime.now(timezone.utc).isoformat(),
                    "redirect_url": "https://www.adzuna.in/jobs/details/adzuna_mock_002",
                    "salary_min": 1000000.0,
                    "salary_max": 1800000.0,
                    "contract_time": "full_time",
                },
            ]

        url = f"{self.base_url}/{page}"
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "results_per_page": results_per_page,
            "what": query,
            "content-type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            return data.get("results", [])

    async def ingest_jobs(
        self,
        query: str = "Software Engineer",
        mock_response: Optional[List[Dict[str, Any]]] = None,
        save_to_live: bool = False,
    ) -> List[Dict[str, Any]]:
        """Fetch, normalize, embed, and store Adzuna jobs. Mock ingests are labeled source='adzuna_mock'; save_to_live is strictly disabled for mock data."""
        is_mock = not self.app_id or not self.app_key or mock_response is not None
        if is_mock and save_to_live:
            raise ValueError(
                "save_to_live is strictly disabled for mock Adzuna data to prevent polluting live storage with mock records."
            )
        source_label = "adzuna_mock" if is_mock else "adzuna_api"
        raw_items = await self.fetch_jobs(query=query, mock_response=mock_response)
        fetch_time = datetime.now(timezone.utc)
        normalized_records: List[Dict[str, Any]] = []

        for item in raw_items:
            ext_id = f"adzuna_{item.get('id', '')}"
            title = item.get("title", "")
            company = item.get("company", {}).get("display_name", "")
            location = item.get("location", {}).get("display_name", "India")
            desc = item.get("description", "")
            redirect_url = item.get("redirect_url")
            created_str = item.get("created")
            posting_date = datetime.fromisoformat(created_str.replace("Z", "+00:00")) if created_str else fetch_time

            canonical_skills = extract_canonical_skills(f"{title} {desc}")
            embed_text = embedding_service.construct_job_embed_text(
                title=title,
                description=desc,
                skills=canonical_skills,
                company=company,
                location=location,
            )
            embedding = await embedding_service.get_embedding(embed_text)

            record = {
                "external_id": ext_id,
                "title": title[:500],
                "company_name": company[:500] if company else None,
                "description": desc,
                "location": location[:500],
                "work_type": "Full-time" if item.get("contract_time") == "full_time" else "Direct",
                "remote_allowed": "remote" in desc.lower() or "remote" in location.lower(),
                "skills": canonical_skills,
                "min_salary": item.get("salary_min"),
                "max_salary": item.get("salary_max"),
                "med_salary": ((item.get("salary_min") + item.get("salary_max")) / 2.0)
                if (item.get("salary_min") and item.get("salary_max"))
                else None,
                "pay_period": "YEARLY",
                "country": "India",
                "currency": "INR",
                "source": source_label,
                "embedding": embedding,
                "created_at": posting_date,
                "updated_at": fetch_time,
            }
            normalized_records.append(record)

        if not normalized_records:
            return []

        # Do not pollute live stores in mock mode
        if is_mock:
            logger.info("Adzuna mock ingest executed in isolated mode. Records labeled source='adzuna_mock' and not written to live stores.")
            return normalized_records

        # 1. Upsert into PostgreSQL
        async with AsyncSessionLocal() as session:
            stmt = insert(JobPosting).values(normalized_records)
            stmt = stmt.on_conflict_do_update(
                index_elements=["external_id"],
                set_={
                    "title": stmt.excluded.title,
                    "company_name": stmt.excluded.company_name,
                    "description": stmt.excluded.description,
                    "location": stmt.excluded.location,
                    "skills": stmt.excluded.skills,
                    "min_salary": stmt.excluded.min_salary,
                    "max_salary": stmt.excluded.max_salary,
                    "med_salary": stmt.excluded.med_salary,
                    "source": source_label,
                    "embedding": stmt.excluded.embedding,
                    "updated_at": fetch_time,
                },
            )
            await session.execute(stmt)
            await session.commit()


        # 2. Upsert into ChromaDB
        chroma_service.upsert_job_postings(
            ids=[r["external_id"] for r in normalized_records],
            embeddings=[r["embedding"] for r in normalized_records],
            documents=[f"{r['title']} {r['description'][:500]}" for r in normalized_records],
            metadatas=[
                {
                    "title": r["title"],
                    "company_name": r["company_name"] or "",
                    "location": r["location"],
                    "country": r["country"],
                    "currency": r["currency"],
                    "source": r["source"],
                }
                for r in normalized_records
            ],
        )

        logger.info(f"Successfully ingested {len(normalized_records)} jobs from Adzuna API.")
        return normalized_records


adzuna_ingest_service = AdzunaIngestService()
