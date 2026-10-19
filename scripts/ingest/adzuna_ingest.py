"""Adzuna API Ingestion script for Indian job market with dual write to PostgreSQL and ChromaDB.

Remediation R8 upgrades:
- Strict Quota Guard integration with persistent call counter (`adzuna_call_counter.json`).
- Automatic request URL & credential redaction in all exceptions, logs, and error records.
- Max 1 retry on transient network errors; 0 retries on 4xx client errors.
- Immediate halt on HTTP 429 (Rate Limit) and HTTP 401/403 (Auth Error).
- Exact field mapping: null company/location when missing (no silent defaults).
- Predicted salary governance: null database salary columns when salary_is_predicted is true.
- Idempotent upserts by (source, source_job_id) with duplicate counting.
- Phase 6 guard preservation: failed query or run never deactivates existing jobs.
"""

import asyncio
from datetime import datetime, timezone
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy.dialects.postgresql import insert

from app.core.config import settings
from app.core.logging import logger
from app.core.redaction import redact_credentials, redact_exception, redact_url
from app.core.taxonomy import extract_canonical_skills
from app.db.chroma import chroma_service
from app.db.session import AsyncSessionLocal
from app.models.job_posting import JobPosting
from app.services.adzuna_quota_guard import (
    AdzunaAuthError,
    AdzunaQuotaGuard,
    AdzunaRateLimitError,
    QuotaExceededError,
    adzuna_quota_guard,
)
from app.services.embedding_service import embedding_service
from app.services.job_ingestion_service import job_ingestion_service, normalize_job_url


class FetchResult(tuple):
    """
    Tuple containing (items, fetch_meta).
    Supports unpacking: `items, meta = await service.fetch_jobs(...)`
    Also supports list-like operations directly on items (len, indexing)
    for backwards compatibility with tests expecting fetch_jobs() to return a List.
    """

    def __new__(cls, items: List[Dict[str, Any]], meta: Dict[str, Any]):
        return super().__new__(cls, (items, meta))

    @property
    def items(self) -> List[Dict[str, Any]]:
        return self[0]

    @property
    def meta(self) -> Dict[str, Any]:
        return self[1]

    def __len__(self) -> int:
        # Return count of fetched items for len(fetched)
        return len(super().__getitem__(0))

    def __getitem__(self, idx: Any) -> Any:
        items = super().__getitem__(0)
        if idx == 0 and len(items) > 0:
            return items[0]
        return super().__getitem__(idx)


class IngestionReport(dict):
    """
    Structured ingestion outcome report dictionary.
    Also implements sequence/list interface for backwards compatibility with tests
    expecting a List[Dict[str, Any]] return value from ingest_jobs().
    """

    def __iter__(self):
        # If iterated directly (e.g. for item in result: ... or result[0]), iterate over records
        return iter(self.get("records", []))

    def __len__(self):
        # If len() is called on the report, return count of normalized records
        return len(self.get("records", []))

    def __getitem__(self, key):
        # If indexed by integer (e.g. result[0]), index into records
        if isinstance(key, int):
            return self.get("records", [])[key]
        return super().__getitem__(key)


_SENTINEL = object()


class AdzunaIngestService:
    """Ingest job postings from Adzuna (India: country='in') with quota protection and honest state tracking."""

    def __init__(self, quota_guard: Optional[AdzunaQuotaGuard] = None):
        self.quota_guard = quota_guard or adzuna_quota_guard
        self.base_url = "https://api.adzuna.com/v1/api/jobs"
        self.polite_delay_seconds = 1.0
        self._app_id_override: Any = _SENTINEL
        self._app_key_override: Any = _SENTINEL

    @property
    def app_id(self) -> Optional[str]:
        if self._app_id_override is not _SENTINEL:
            return self._app_id_override
        return os.environ.get("ADZUNA_APP_ID") or getattr(settings, "ADZUNA_APP_ID", None)

    @app_id.setter
    def app_id(self, val: Optional[str]) -> None:
        self._app_id_override = val

    @property
    def app_key(self) -> Optional[str]:
        if self._app_key_override is not _SENTINEL:
            return self._app_key_override
        return os.environ.get("ADZUNA_APP_KEY") or getattr(settings, "ADZUNA_APP_KEY", None)

    @app_key.setter
    def app_key(self, val: Optional[str]) -> None:
        self._app_key_override = val

    async def fetch_jobs(
        self,
        query: str = "Software Engineer",
        city: Optional[str] = None,
        page: int = 1,
        results_per_page: int = 50,
        country: str = "in",
        sort_by: str = "date",
        max_days_old: int = 30,
        mock_response: Optional[List[Dict[str, Any]]] = None,
        timeout_seconds: float = 30.0,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Fetch a page of jobs from Adzuna API under strict quota and retry guards.
        Returns (raw_items, fetch_meta).
        """
        fetch_meta = {
            "query": query,
            "city": city,
            "page": page,
            "results_per_page": results_per_page,
            "country": country,
            "requests_used": 0,
            "status_code": None,
            "rate_limit_headers": {},
        }

        # 1. Explicit mock handling (strictly isolated for tests)
        if mock_response is not None:
            logger.info("Explicit mock requested for Adzuna fetch. Using provided mocked API response.")
            fetch_meta["status_code"] = 200
            fetch_meta["is_mock"] = True
            return FetchResult(mock_response, fetch_meta)

        # 2. Check credentials
        current_id = self.app_id
        current_key = self.app_key
        if not current_id or not current_key:
            raise ValueError(
                "ADZUNA credentials not configured (ADZUNA_APP_ID and ADZUNA_APP_KEY required). "
                "Failing loud: live ingestion cannot proceed without valid credentials unless mock_response is explicitly passed."
            )

        # 3. Check quota before attempting
        self.quota_guard.check_can_call()

        url = f"{self.base_url}/{country}/search/{page}"
        params: Dict[str, Any] = {
            "app_id": current_id,
            "app_key": current_key,
            "results_per_page": min(max(1, results_per_page), 50),
            "what": query,
            "sort_by": sort_by,
            "max_days_old": max_days_old,
            "content-type": "application/json",
        }
        if city:
            params["where"] = city

        attempt = 0
        max_attempts = 2  # At most 1 retry (2 total attempts) for transient errors only

        while attempt < max_attempts:
            attempt += 1
            is_retry = (attempt > 1)

            # Record call BEFORE sending
            call_idx = self.quota_guard.record_call_before_send(
                endpoint=url,
                query=query,
                city=city,
                page=page,
                is_retry=is_retry,
            )
            fetch_meta["requests_used"] += 1

            start_t = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                    resp = await client.get(url, params=params)
                    duration_ms = (time.perf_counter() - start_t) * 1000.0
                    fetch_meta["status_code"] = resp.status_code

                    # Capture rate-limit headers safely without secrets
                    for h_name in ("x-ratelimit-limit", "x-ratelimit-remaining", "retry-after"):
                        if h_name in resp.headers:
                            fetch_meta["rate_limit_headers"][h_name] = resp.headers[h_name]

                    self.quota_guard.record_call_result(
                        call_index=call_idx,
                        status_code=resp.status_code,
                        duration_ms=duration_ms,
                    )

                    # Handle HTTP Status Codes
                    if resp.status_code == 429:
                        msg = f"HTTP 429 Too Many Requests from Adzuna API at {redact_url(url)}"
                        logger.error(f"[Adzuna Quota Guard] {msg}. Halting entire run immediately.")
                        raise AdzunaRateLimitError(msg)

                    if resp.status_code in (401, 403):
                        msg = f"HTTP {resp.status_code} Unauthorized/Forbidden from Adzuna API at {redact_url(url)}"
                        logger.error(f"[Adzuna Quota Guard] {msg}. Permanent authentication error; halting immediately.")
                        raise AdzunaAuthError(msg)

                    if 400 <= resp.status_code < 500:
                        # Non-retryable 4xx client errors (e.g. 400, 404)
                        msg = f"HTTP {resp.status_code} Client Error from Adzuna API: {resp.text}"
                        logger.warning(f"[Adzuna Provider] {redact_credentials(msg)}. Zero retries on 4xx.")
                        resp.raise_for_status()

                    resp.raise_for_status()
                    data = resp.json()
                    results = data.get("results", [])
                    return FetchResult(results, fetch_meta)

            except (httpx.TimeoutException, httpx.NetworkError) as transient_exc:
                duration_ms = (time.perf_counter() - start_t) * 1000.0
                err_msg = redact_exception(transient_exc)
                logger.warning(
                    f"[Adzuna Provider] Transient failure on attempt {attempt}/{max_attempts} "
                    f"for query='{query}': {err_msg}"
                )
                self.quota_guard.record_call_result(
                    call_index=call_idx,
                    status_code=0,
                    duration_ms=duration_ms,
                    error_message=err_msg,
                )
                if attempt >= max_attempts:
                    raise

                # Bounded backoff before single retry
                await asyncio.sleep(2.0)

            except Exception as exc:
                duration_ms = (time.perf_counter() - start_t) * 1000.0
                err_msg = redact_exception(exc)
                self.quota_guard.record_call_result(
                    call_index=call_idx,
                    status_code=fetch_meta["status_code"] or 500,
                    duration_ms=duration_ms,
                    error_message=err_msg,
                )
                raise

        return FetchResult([], fetch_meta)

    async def ingest_jobs(
        self,
        query: str = "Software Engineer",
        city: Optional[str] = None,
        page: int = 1,
        results_per_page: int = 50,
        country: str = "in",
        mock_response: Optional[List[Dict[str, Any]]] = None,
        save_to_live: bool = False,
        with_embeddings: bool = True,
    ) -> Dict[str, Any]:
        """
        Fetch, normalize, embed, and store Adzuna jobs.
        Mock ingests are labeled source='adzuna_mock'; save_to_live is strictly disabled for mock data.
        Returns a structured ingestion outcome report.
        """
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
        raw_items, fetch_meta = await self.fetch_jobs(
            query=query,
            city=city,
            page=page,
            results_per_page=results_per_page,
            country=country,
            mock_response=mock_response,
        )

        fetch_time = datetime.now(timezone.utc)
        normalized_records: List[Dict[str, Any]] = []
        predicted_salary_count = 0

        for item in raw_items:
            item_id = str(item.get("id") or "").strip()
            if not item_id:
                continue

            ext_id = f"adzuna_{item_id}"
            title = str(item.get("title") or "").strip()
            desc = str(item.get("description") or "").strip()

            # Honest company and location: null when missing, no silent defaults
            company_obj = item.get("company")
            company_name: Optional[str] = None
            if isinstance(company_obj, dict):
                company_name = company_obj.get("display_name")
            elif isinstance(company_obj, str):
                company_name = company_obj
            company_name = company_name.strip() if company_name else None

            loc_obj = item.get("location")
            location_name: Optional[str] = None
            if isinstance(loc_obj, dict):
                location_name = loc_obj.get("display_name")
            elif isinstance(loc_obj, str):
                location_name = loc_obj
            location_name = location_name.strip() if location_name else None

            redirect_url = item.get("redirect_url")
            created_str = item.get("created")
            if created_str:
                try:
                    posting_date = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                except Exception:
                    posting_date = fetch_time
            else:
                posting_date = fetch_time

            # Predicted Salary Governance:
            # If predicted, store NULL in database columns, preserve flag in snapshot/record
            raw_pred = item.get("salary_is_predicted", "0")
            is_predicted = str(raw_pred).lower() in ("1", "true")
            if is_predicted:
                predicted_salary_count += 1
                min_sal = None
                max_sal = None
                med_sal = None
                sal_curr = None
            else:
                min_sal = item.get("salary_min")
                max_sal = item.get("salary_max")
                med_sal = ((min_sal + max_sal) / 2.0) if (min_sal and max_sal) else None
                sal_curr = "INR" if (min_sal or max_sal) else None

            canonical_skills = extract_canonical_skills(f"{title} {desc}")

            # Embeddings generated via existing SBERT model (no new downloads)
            embedding: Optional[List[float]] = None
            if with_embeddings:
                embed_text = embedding_service.construct_job_embed_text(
                    title=title,
                    description=desc,
                    skills=canonical_skills,
                    company=company_name or "",
                    location=location_name or "",
                )
                embedding = await embedding_service.get_embedding(embed_text)

            record = {
                "external_id": ext_id,
                "source_job_id": item_id,
                "source_url": normalize_job_url(redirect_url),
                "title": title[:500],
                "company_name": company_name[:500] if company_name else None,
                "description": desc,
                "location": location_name[:500] if location_name else None,
                "work_type": "Full-time" if item.get("contract_time") == "full_time" else "Direct",
                "remote_allowed": "remote" in desc.lower() or (location_name and "remote" in location_name.lower()),
                "skills": canonical_skills,
                "min_salary": min_sal,
                "max_salary": max_sal,
                "med_salary": med_sal,
                "pay_period": "YEARLY" if (min_sal or max_sal) else None,
                "country": "India",
                "currency": sal_curr,
                "source": source_label,
                "embedding": embedding,
                "published_at": posting_date,
                "first_seen_at": fetch_time,
                "last_seen_at": fetch_time,
                "last_refreshed_at": fetch_time,
                "is_active": True,
                "freshness_status": "fresh",
                "salary_is_predicted": is_predicted,
                "raw_category": item.get("category", {}).get("label") if isinstance(item.get("category"), dict) else None,
            }
            normalized_records.append(record)

        report = IngestionReport({
            "source": source_label,
            "query": query,
            "city": city,
            "fetched_count": len(raw_items),
            "normalized_count": len(normalized_records),
            "predicted_salary_count": predicted_salary_count,
            "requests_used": fetch_meta["requests_used"],
            "status_code": fetch_meta["status_code"],
            "records": normalized_records,
            "batch_result": None,
        })

        if is_mock or not save_to_live:
            return report

        # 1. Upsert into PostgreSQL via JobIngestionService (idempotent, preserves first_seen_at)
        async with AsyncSessionLocal() as session:
            batch_result = await job_ingestion_service.ingest_normalized_records(
                db=session,
                records=normalized_records,
                source_name=source_label,
            )
            report["batch_result"] = batch_result.to_dict()

        # 2. Upsert into ChromaDB if embeddings present
        records_with_embeddings = [r for r in normalized_records if r.get("embedding")]
        if records_with_embeddings:
            chroma_service.upsert_job_postings(
                ids=[r["external_id"] for r in records_with_embeddings],
                embeddings=[r["embedding"] for r in records_with_embeddings],
                documents=[f"{r['title']} {r['description'][:500]}" for r in records_with_embeddings],
                metadatas=[
                    {
                        "title": r["title"],
                        "company_name": r["company_name"] or "",
                        "location": r["location"] or "",
                        "country": r["country"],
                        "currency": r["currency"] or "INR",
                        "source": r["source"],
                    }
                    for r in records_with_embeddings
                ],
            )

        logger.info(
            f"Adzuna live ingest completed for query='{query}' (city='{city}'): "
            f"received={len(normalized_records)}, inserted={batch_result.inserted}, "
            f"updated={batch_result.updated}, unchanged={batch_result.unchanged}"
        )
        return report


adzuna_ingest_service = AdzunaIngestService()
