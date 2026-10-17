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
from app.services.job_ingestion_service import job_ingestion_service, normalize_job_url


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
        """Fetch jobs from Adzuna API, requiring explicit mock_response if credentials are not configured."""
        if mock_response is not None:
            logger.info("Explicit mock requested for Adzuna fetch. Using provided mocked API response.")
            return mock_response

        if not self.app_id or not self.app_key:
            raise ValueError(
                "ADZUNA credentials not configured (ADZUNA_APP_ID and ADZUNA_APP_KEY required). "
                "Failing loud: live ingestion cannot proceed without valid credentials unless mock_response is explicitly passed."
            )

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
        is_mock = mock_response is not None
        if not is_mock and (not self.app_id or not self.app_key):
            raise ValueError(
                "ADZUNA credentials not configured (ADZUNA_APP_ID and ADZUNA_APP_KEY required). "
                "Failing loud: live ingestion cannot proceed without valid credentials unless mock_response is explicitly passed."
            )
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
                "source_job_id": str(item.get("id") or "") or None,
                "source_url": normalize_job_url(redirect_url),
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
                "published_at": posting_date,
                "first_seen_at": fetch_time,
                "last_seen_at": fetch_time,
                "last_refreshed_at": fetch_time,
                "is_active": True,
                "freshness_status": "fresh",
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

        # 1. Upsert into PostgreSQL via JobIngestionService
        async with AsyncSessionLocal() as session:
            await job_ingestion_service.ingest_normalized_records(
                db=session,
                records=normalized_records,
                source_name=source_label,
            )


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
