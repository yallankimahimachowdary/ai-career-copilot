"""
app/services/job_ingestion_service.py
--------------------------------------
Job ingestion, deduplication, URL normalization, and freshness evaluation service (Phase 6).
Provides idempotent ingestion, per-source outcome accounting, and timezone-aware
freshness lifecycle management.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import re
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.models.job_posting import JobPosting
from app.services.deduplication_service import _clean_company_name, _normalize_str


# Tracking query parameters to strip during URL normalization
_TRACKING_QUERY_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "source",
    "fbclid",
    "gclid",
    "trk",
    "trackingId",
}


def normalize_job_url(url: Optional[str]) -> Optional[str]:
    """
    Normalize a job posting URL:
    - Strips query tracking parameters (utm_*, ref, etc.)
    - Lowercases scheme and network location (hostname)
    - Strips fragment and trailing slashes
    """
    if not url or not isinstance(url, str):
        return None

    clean_url = url.strip()
    if not clean_url:
        return None

    try:
        parsed = urlparse(clean_url)
        if not parsed.scheme or not parsed.netloc:
            return clean_url

        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/") if parsed.path != "/" else "/"

        # Filter out tracking query parameters
        filtered_query = []
        if parsed.query:
            query_pairs = parse_qsl(parsed.query, keep_blank_values=False)
            for k, v in query_pairs:
                if k.lower() not in _TRACKING_QUERY_PARAMS and not k.lower().startswith("utm_"):
                    filtered_query.append((k, v))

        new_query = urlencode(filtered_query)
        normalized = urlunparse((scheme, netloc, path, "", new_query, ""))
        return normalized
    except Exception as exc:
        logger.debug(f"Failed to normalize URL '{url}': {exc}")
        return clean_url


def generate_fallback_external_id(
    title: str,
    company: Optional[str],
    location: Optional[str],
    description_snippet: str = "",
) -> str:
    """
    Generate a deterministic fallback external ID when source_job_id is missing.
    Uses normalized title, cleaned company, normalized location, and a 60-char description snippet.
    """
    norm_t = _normalize_str(title)
    norm_c = _clean_company_name(company or "")
    norm_l = _normalize_str(location or "")
    norm_d = _normalize_str(description_snippet[:60])

    content_key = f"{norm_t}|{norm_c}|{norm_l}|{norm_d}"
    digest = hashlib.sha256(content_key.encode("utf-8")).hexdigest()[:16]
    return f"norm_{digest}"


@dataclass
class IngestionBatchResult:
    """Outcome metrics for an ingestion run from a specific provider source."""
    source: str
    total_received: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    rejected: int = 0
    failed: int = 0
    error_message: Optional[str] = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.started_at:
            data["started_at"] = self.started_at.isoformat()
        if self.finished_at:
            data["finished_at"] = self.finished_at.isoformat()
        return data


class JobIngestionService:
    """Service handling idempotent job ingestion, deduplication, and freshness lifecycle."""

    async def ingest_normalized_records(
        self,
        db: AsyncSession,
        records: List[Dict[str, Any]],
        source_name: str,
        now: Optional[datetime] = None,
    ) -> IngestionBatchResult:
        """
        Idempotently ingest a batch of job records into PostgreSQL:
        - Avoids duplicating existing listings.
        - Preserves original publication date (`published_at`) and discovery timestamp (`first_seen_at`).
        - Updates `last_seen_at` and `last_refreshed_at` for existing listings.
        - Reactivates previously inactive listings if re-encountered in active source feed.
        - Tracks inserted, updated, unchanged, rejected, and failed counts.
        """
        current_time = now or datetime.now(timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        result = IngestionBatchResult(
            source=source_name,
            total_received=len(records),
            started_at=current_time,
        )

        if not records:
            result.finished_at = datetime.now(timezone.utc)
            return result

        for item in records:
            try:
                # 1. Validation & normalization
                raw_title = str(item.get("title") or "").strip()
                raw_desc = str(item.get("description") or "").strip()

                if not raw_title or not raw_desc:
                    logger.warning(f"Rejecting job record from '{source_name}': missing title or description.")
                    result.rejected += 1
                    continue

                source_job_id = str(item.get("source_job_id") or item.get("job_id") or "").strip() or None
                raw_url = item.get("source_url") or item.get("redirect_url") or item.get("job_url")
                norm_url = normalize_job_url(raw_url)

                company = item.get("company_name") or item.get("company")
                if isinstance(company, dict):
                    company = company.get("display_name") or company.get("name")
                company = str(company).strip() if company else None

                location = item.get("location")
                if isinstance(location, dict):
                    location = location.get("display_name") or location.get("name")
                location = str(location).strip() if location else None

                # Determine external_id
                if source_job_id:
                    ext_id = item.get("external_id") or f"{source_name}_{source_job_id}"
                else:
                    ext_id = item.get("external_id") or generate_fallback_external_id(
                        title=raw_title,
                        company=company,
                        location=location,
                        description_snippet=raw_desc,
                    )

                # Parse publication date if provided
                published_at = item.get("published_at") or item.get("created")
                if isinstance(published_at, str):
                    try:
                        published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                    except Exception:
                        published_at = current_time
                elif not isinstance(published_at, datetime):
                    published_at = current_time

                if published_at and published_at.tzinfo is None:
                    published_at = published_at.replace(tzinfo=timezone.utc)

                # 2. Check for existing record in database
                stmt = select(JobPosting).where(JobPosting.external_id == ext_id)
                query_res = await db.execute(stmt)
                existing: Optional[JobPosting] = query_res.scalar_one_or_none()

                # Fallback match by source_job_id if external_id differed
                if not existing and source_job_id:
                    stmt_by_src = select(JobPosting).where(
                        JobPosting.source == source_name,
                        JobPosting.source_job_id == source_job_id,
                    )
                    res_by_src = await db.execute(stmt_by_src)
                    existing = res_by_src.scalar_one_or_none()

                if existing:
                    # Idempotent update: update last_seen_at and last_refreshed_at
                    # Preserve original published_at and first_seen_at!
                    existing.last_seen_at = current_time
                    existing.last_refreshed_at = current_time

                    # Reactivate if it was inactive or marked expired
                    was_inactive = not existing.is_active or existing.freshness_status != "fresh"
                    if was_inactive:
                        existing.is_active = True
                        existing.freshness_status = "fresh"

                    # Check if metadata actually changed
                    has_changes = False
                    if existing.title != raw_title[:500]:
                        existing.title = raw_title[:500]
                        has_changes = True
                    if existing.company_name != (company[:500] if company else None):
                        existing.company_name = company[:500] if company else None
                        has_changes = True
                    if existing.description != raw_desc:
                        existing.description = raw_desc
                        has_changes = True
                    if existing.location != (location[:500] if location else None):
                        existing.location = location[:500] if location else None
                        has_changes = True

                    item_skills = item.get("skills") or []
                    if isinstance(item_skills, list) and existing.skills != item_skills:
                        existing.skills = item_skills
                        has_changes = True

                    if norm_url and existing.source_url != norm_url:
                        existing.source_url = norm_url
                        has_changes = True

                    if item.get("embedding") is not None:
                        existing.embedding = item.get("embedding")

                    existing.updated_at = current_time

                    if has_changes or was_inactive:
                        result.updated += 1
                    else:
                        result.unchanged += 1
                else:
                    # New insertion
                    new_job = JobPosting(
                        external_id=ext_id,
                        source_job_id=source_job_id,
                        source=source_name,
                        source_url=norm_url,
                        title=raw_title[:500],
                        company_name=company[:500] if company else None,
                        description=raw_desc,
                        location=location[:500] if location else None,
                        work_type=item.get("work_type"),
                        remote_allowed=bool(item.get("remote_allowed", False)),
                        skills=item.get("skills") or [],
                        min_salary=item.get("min_salary"),
                        max_salary=item.get("max_salary"),
                        med_salary=item.get("med_salary"),
                        pay_period=item.get("pay_period"),
                        country=item.get("country", "India"),
                        currency=item.get("currency", "INR"),
                        embedding=item.get("embedding"),
                        published_at=published_at,
                        first_seen_at=current_time,
                        last_seen_at=current_time,
                        last_refreshed_at=current_time,
                        is_active=True,
                        freshness_status="fresh",
                        created_at=published_at or current_time,
                        updated_at=current_time,
                    )
                    db.add(new_job)
                    result.inserted += 1

            except Exception as exc:
                logger.error(f"Error ingesting item from source '{source_name}': {exc}", exc_info=True)
                result.failed += 1

        try:
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.error(f"Database commit error during ingestion from '{source_name}': {exc}", exc_info=True)
            result.failed += (result.inserted + result.updated)
            result.inserted = 0
            result.updated = 0
            result.error_message = f"Database commit failed: {exc}"

        result.finished_at = datetime.now(timezone.utc)
        return result

    async def evaluate_listing_freshness(
        self,
        db: AsyncSession,
        stale_days: Optional[int] = None,
        expired_days: Optional[int] = None,
        reference_time: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """
        Evaluate freshness of all listings based on time elapsed since `last_seen_at`:
        - < stale_days: 'fresh', is_active=True
        - >= stale_days and < expired_days: 'stale', is_active=True (still visible with stale indicator)
        - >= expired_days: 'expired', is_active=False (excluded from active recommendations)
        Preserves historical records in the database.
        """
        stale_threshold = stale_days if stale_days is not None else settings.JOB_STALE_DAYS_THRESHOLD
        expired_threshold = expired_days if expired_days is not None else settings.JOB_EXPIRED_DAYS_THRESHOLD
        ref_time = reference_time or datetime.now(timezone.utc)
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)

        summary = {"evaluated": 0, "fresh": 0, "stale": 0, "expired": 0, "inactive": 0}

        stmt = select(JobPosting)
        res = await db.execute(stmt)
        postings = res.scalars().all()

        for job in postings:
            summary["evaluated"] += 1
            calculated = job.calculate_freshness(
                reference_time=ref_time,
                stale_days=stale_threshold,
                expired_days=expired_threshold,
            )

            job.freshness_status = calculated
            if calculated == "expired":
                job.is_active = False
                summary["expired"] += 1
            elif calculated == "stale":
                job.is_active = True
                summary["stale"] += 1
            elif calculated == "fresh":
                job.is_active = True
                summary["fresh"] += 1
            else:
                summary["inactive"] += 1

            job.last_refreshed_at = ref_time

        try:
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.error(f"Failed to commit freshness updates: {exc}", exc_info=True)

        return summary


job_ingestion_service = JobIngestionService()
