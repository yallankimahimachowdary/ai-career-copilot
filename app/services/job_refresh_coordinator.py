"""
app/services/job_refresh_coordinator.py
----------------------------------------
Coordinates job freshness refresh across multiple providers (Adzuna, etc.) with:
- Non-overlapping execution guard (asyncio.Lock + is_running flag).
- Provider fault isolation: one failing source does not abort others.
- Bounded provider retries with exponential backoff.
- Structured execution auditing and error classification.
- Evaluation of stale and expired listings.
"""

import asyncio
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import traceback
from typing import Any, Callable, Dict, List, Optional
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.db.session import AsyncSessionLocal
from app.services.job_ingestion_service import IngestionBatchResult, job_ingestion_service


@dataclass
class JobRefreshRunRecord:
    """Audit log for a job refresh execution cycle."""
    run_id: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    status: str = "running"  # "running" | "completed" | "partial_success" | "failed" | "skipped"
    sources: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    freshness_summary: Dict[str, int] = field(default_factory=dict)
    error_category: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.started_at:
            data["started_at"] = self.started_at.isoformat()
        if self.finished_at:
            data["finished_at"] = self.finished_at.isoformat()
        return data


class JobRefreshCoordinator:
    """Manages resilient scheduled and manual job refreshes."""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._is_running = False
        self._last_run: Optional[JobRefreshRunRecord] = None
        self._run_history: List[JobRefreshRunRecord] = []
        self._provider_handlers: Dict[str, Callable] = {}

    def is_running(self) -> bool:
        """Check if a refresh cycle is currently in progress."""
        return self._is_running

    def get_last_run(self) -> Optional[JobRefreshRunRecord]:
        """Return the most recent refresh record."""
        return self._last_run

    def register_provider(self, name: str, handler: Callable) -> None:
        """Register a provider handler callable."""
        self._provider_handlers[name] = handler

    async def run_refresh(
        self,
        queries: Optional[List[str]] = None,
        sources: Optional[List[str]] = None,
        max_retries: Optional[int] = None,
        evaluate_freshness: bool = True,
        db_session: Optional[AsyncSession] = None,
    ) -> JobRefreshRunRecord:
        """
        Execute a complete refresh cycle across configured providers:
        - Prevents overlapping execution.
        - Isolates provider failures.
        - Performs bounded retries on transient errors.
        - Evaluates stale listings across all jobs.
        """
        if self._is_running:
            logger.warning("Job refresh requested while another refresh is actively running. Rejecting.")
            skipped_record = JobRefreshRunRecord(
                run_id=str(uuid.uuid4()),
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                status="skipped",
                error_category="concurrency_lock",
                error_message="A refresh job is already in progress.",
            )
            return skipped_record

        async with self._lock:
            self._is_running = True
            run_id = str(uuid.uuid4())
            start_time = datetime.now(timezone.utc)
            record = JobRefreshRunRecord(
                run_id=run_id,
                started_at=start_time,
            )
            self._last_run = record

            target_queries = queries or ["Software Engineer", "Data Scientist", "DevOps"]
            retries = max_retries if max_retries is not None else settings.JOB_INGESTION_MAX_RETRIES

            successful_sources = 0
            failed_sources = 0

            try:
                # 1. Execute Adzuna Provider (if active / requested)
                target_sources = sources or ["adzuna"]
                if "adzuna" in target_sources:
                    adzuna_res = await self._run_provider_with_retries(
                        name="adzuna",
                        coro_fn=self._execute_adzuna_refresh,
                        queries=target_queries,
                        max_retries=retries,
                    )
                    record.sources["adzuna"] = adzuna_res.to_dict()
                    if adzuna_res.failed > 0 and adzuna_res.inserted == 0 and adzuna_res.updated == 0 and adzuna_res.unchanged == 0:
                        failed_sources += 1
                    else:
                        successful_sources += 1

                # 2. Execute any custom registered providers
                for provider_name, handler in self._provider_handlers.items():
                    if sources and provider_name not in sources:
                        continue
                    prov_res = await self._run_provider_with_retries(
                        name=provider_name,
                        coro_fn=handler,
                        queries=target_queries,
                        max_retries=retries,
                    )
                    record.sources[provider_name] = prov_res.to_dict()
                    if prov_res.failed > 0 and prov_res.inserted == 0 and prov_res.updated == 0:
                        failed_sources += 1
                    else:
                        successful_sources += 1

                # 3. Evaluate listing freshness across all stored jobs
                if evaluate_freshness:
                    if db_session:
                        freshness_summary = await job_ingestion_service.evaluate_listing_freshness(db=db_session)
                    else:
                        async with AsyncSessionLocal() as session:
                            freshness_summary = await job_ingestion_service.evaluate_listing_freshness(db=session)
                    record.freshness_summary = freshness_summary

                # 4. Determine overall status
                if failed_sources == 0:
                    record.status = "completed"
                elif successful_sources > 0:
                    record.status = "partial_success"
                    record.error_category = "partial_provider_failure"
                else:
                    record.status = "failed"
                    record.error_category = "all_providers_failed"

            except Exception as exc:
                logger.error(f"Critical error during refresh coordinator run {run_id}: {exc}", exc_info=True)
                record.status = "failed"
                record.error_category = self._classify_error(exc)
                record.error_message = str(exc)
            finally:
                end_time = datetime.now(timezone.utc)
                record.finished_at = end_time
                record.duration_seconds = round((end_time - start_time).total_seconds(), 2)
                self._is_running = False
                self._run_history.append(record)
                # Keep last 50 runs in memory
                if len(self._run_history) > 50:
                    self._run_history.pop(0)

            return record

    async def _run_provider_with_retries(
        self,
        name: str,
        coro_fn: Callable,
        queries: List[str],
        max_retries: int,
    ) -> IngestionBatchResult:
        """Execute a provider with bounded retries and exponential backoff."""
        batch_result = IngestionBatchResult(source=name)
        attempt = 0
        backoff = 1.0

        while attempt <= max_retries:
            attempt += 1
            try:
                res = await coro_fn(queries)
                if isinstance(res, IngestionBatchResult):
                    return res
                batch_result.total_received += len(res) if isinstance(res, list) else 0
                batch_result.finished_at = datetime.now(timezone.utc)
                return batch_result
            except Exception as exc:
                err_category = self._classify_error(exc)
                logger.warning(
                    f"Provider '{name}' attempt {attempt}/{max_retries + 1} failed: {exc} (category={err_category})"
                )
                if attempt > max_retries:
                    batch_result.failed += 1
                    batch_result.error_message = f"Failed after {max_retries + 1} attempts: {exc}"
                    batch_result.finished_at = datetime.now(timezone.utc)
                    return batch_result

                await asyncio.sleep(min(backoff, 5.0))
                backoff *= 2.0

        batch_result.finished_at = datetime.now(timezone.utc)
        return batch_result

    async def _execute_adzuna_refresh(self, queries: List[str]) -> IngestionBatchResult:
        """Internal worker calling AdzunaIngestService for specified queries."""
        from scripts.ingest.adzuna_ingest import adzuna_ingest_service

        combined_result = IngestionBatchResult(source="adzuna")

        # Check if Adzuna credentials exist
        if not adzuna_ingest_service.app_id or not adzuna_ingest_service.app_key:
            logger.info("Adzuna credentials not configured; skipping live Adzuna refresh safely.")
            combined_result.error_message = "Adzuna credentials not configured; skipped."
            combined_result.finished_at = datetime.now(timezone.utc)
            return combined_result

        for query in queries:
            try:
                records = await adzuna_ingest_service.ingest_jobs(query=query, save_to_live=True)
                combined_result.total_received += len(records)
                combined_result.updated += len(records)
            except Exception as exc:
                logger.error(f"Adzuna query '{query}' failed: {exc}", exc_info=True)
                combined_result.failed += 1

        combined_result.finished_at = datetime.now(timezone.utc)
        return combined_result

    def _classify_error(self, exc: Exception) -> str:
        """Classify exception into a structured error category."""
        msg = str(exc).lower()
        if "timeout" in msg or "timed out" in msg:
            return "network_timeout"
        if "429" in msg or "rate limit" in msg or "too many requests" in msg:
            return "rate_limited"
        if "401" in msg or "403" in msg or "auth" in msg or "credential" in msg:
            return "authentication_error"
        if "connection refused" in msg or "connecterror" in msg:
            return "connection_failure"
        if "duplicate" in msg or "integrity" in msg or "foreign key" in msg:
            return "database_integrity_error"
        return "internal_error"


job_refresh_coordinator = JobRefreshCoordinator()
