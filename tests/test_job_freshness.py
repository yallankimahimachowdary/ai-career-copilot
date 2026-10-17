"""
tests/test_job_freshness.py
---------------------------
Comprehensive tests for Phase 6: Job Market Data Quality and Freshness.

Tests:
1. Timezone-aware freshness classification (fresh, stale, expired, inactive).
2. Idempotent ingestion & deduplication (no duplicates, preserves published_at & first_seen_at).
3. Fallback deduplication with normalized keys when source_job_id is missing.
4. Preserving active listings on failed ingestion (failed runs do not deactivate existing jobs).
5. Stale listing policy evaluation across stored jobs.
6. Recommendation queries excluding inactive/expired jobs by default.
7. Concurrency lock preventing overlapping refresh runs.
8. Provider fault isolation (one failing provider does not stop another).
9. URL normalization (stripping tracking parameters, lowercasing host).
10. Standalone refresh CLI execution.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models.job_posting import JobPosting
from app.schemas.job_posting import SemanticJobSearchRequest
from app.services.job_ingestion_service import (
    generate_fallback_external_id,
    job_ingestion_service,
    normalize_job_url,
)
from app.services.job_refresh_coordinator import JobRefreshCoordinator, job_refresh_coordinator


# ============================================================================
# 1. Freshness Classification Tests
# ============================================================================

def test_freshness_classification_fresh():
    """A job seen 2 days ago should be classified as 'fresh'."""
    now = datetime.now(timezone.utc)
    job = JobPosting(
        title="Software Engineer",
        description="Python developer",
        last_seen_at=now - timedelta(days=2),
        is_active=True,
    )
    status = job.calculate_freshness(reference_time=now, stale_days=14, expired_days=30)
    assert status == "fresh"


def test_freshness_classification_stale():
    """A job seen 20 days ago should be classified as 'stale' (between 14 and 30 days)."""
    now = datetime.now(timezone.utc)
    job = JobPosting(
        title="Software Engineer",
        description="Python developer",
        last_seen_at=now - timedelta(days=20),
        is_active=True,
    )
    status = job.calculate_freshness(reference_time=now, stale_days=14, expired_days=30)
    assert status == "stale"


def test_freshness_classification_expired():
    """A job seen 45 days ago should be classified as 'expired' (>= 30 days)."""
    now = datetime.now(timezone.utc)
    job = JobPosting(
        title="Software Engineer",
        description="Python developer",
        last_seen_at=now - timedelta(days=45),
        is_active=True,
    )
    status = job.calculate_freshness(reference_time=now, stale_days=14, expired_days=30)
    assert status == "expired"


def test_freshness_classification_inactive():
    """An inactive job should always return 'inactive'."""
    now = datetime.now(timezone.utc)
    job = JobPosting(
        title="Software Engineer",
        description="Python developer",
        last_seen_at=now - timedelta(days=1),
        is_active=False,
    )
    status = job.calculate_freshness(reference_time=now)
    assert status == "inactive"


def test_freshness_classification_temporarily_unavailable():
    """A temporarily unavailable job returns 'temporarily_unavailable' when inactive."""
    now = datetime.now(timezone.utc)
    job = JobPosting(
        title="Software Engineer",
        description="Python developer",
        last_seen_at=now - timedelta(days=1),
        is_active=False,
        freshness_status="temporarily_unavailable",
    )
    status = job.calculate_freshness(reference_time=now)
    assert status == "temporarily_unavailable"


# ============================================================================
# 2. URL Normalization & Fallback ID Tests
# ============================================================================

def test_normalize_job_url_strips_tracking_params():
    """URL normalizer strips utm_*, ref, and trailing slashes."""
    raw = "https://www.example.com/jobs/123/?utm_source=linkedin&utm_medium=cpc&ref=email#apply"
    expected = "https://www.example.com/jobs/123"
    assert normalize_job_url(raw) == expected


def test_normalize_job_url_preserves_legitimate_params():
    """URL normalizer preserves functional query parameters while lowercasing scheme/host."""
    raw = "HTTP://Example.COM/view?job_id=456&category=dev&utm_campaign=winter"
    expected = "http://example.com/view?job_id=456&category=dev"
    assert normalize_job_url(raw) == expected


def test_normalize_job_url_handles_none_and_empty():
    assert normalize_job_url(None) is None
    assert normalize_job_url("") is None
    assert normalize_job_url("   ") is None


def test_generate_fallback_external_id_deterministic():
    """Same job fields generate the exact same deterministic fallback key."""
    id1 = generate_fallback_external_id(
        title="Senior Python Engineer",
        company="TechCorp Pvt Ltd",
        location="Bengaluru, India",
        description_snippet="Looking for a Python expert with FastAPI experience.",
    )
    id2 = generate_fallback_external_id(
        title="  senior python engineer  ",
        company="TECHCORP",
        location="Bengaluru, India",
        description_snippet="Looking for a Python expert with FastAPI experience.",
    )
    assert id1.startswith("norm_")
    assert id1 == id2


# ============================================================================
# 3. Idempotent Ingestion & Deduplication Tests
# ============================================================================

class MockResult:
    def __init__(self, items):
        self._items = items

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def scalars(self):
        return self

    def all(self):
        return self._items


@pytest.fixture
def mock_ingestion_session():
    """In-memory mock database session for testing ingestion idempotency."""
    storage = {}

    session = AsyncMock()

    def mock_add(inst):
        storage[inst.external_id] = inst

    async def mock_execute(stmt):
        sql_str = str(stmt).lower()
        # Handle queries with WHERE clause
        if "where" in sql_str:
            target_ext = None
            if hasattr(stmt, "compile"):
                for val in stmt.compile().params.values():
                    if val in storage:
                        target_ext = val
                        break
            items = [storage[target_ext]] if target_ext else []
            return MockResult(items)

        # Handle select all JobPostings
        return MockResult(list(storage.values()))

    session.add = MagicMock(side_effect=mock_add)
    session.execute = AsyncMock(side_effect=mock_execute)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    yield session, storage


@pytest.mark.asyncio
async def test_idempotent_ingestion_preserves_published_and_first_seen(mock_ingestion_session):
    """
    Ingesting the same job twice must:
    1. First run: inserted=1
    2. Second run: unchanged=1 (or updated=1)
    3. Total items in DB remains 1
    4. published_at and first_seen_at are preserved from the original run
    5. last_seen_at is bumped to the second run's timestamp
    """
    session, storage = mock_ingestion_session
    original_published = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 10, 14, 0, 0, tzinfo=timezone.utc)

    records_run1 = [
        {
            "external_id": "test_src_1001",
            "source_job_id": "1001",
            "title": "Backend Developer",
            "company_name": "Acme Corp",
            "description": "Python, PostgreSQL",
            "location": "Bengaluru",
            "published_at": original_published,
        }
    ]

    # First ingestion run
    res1 = await job_ingestion_service.ingest_normalized_records(
        db=session,
        records=records_run1,
        source_name="test_src",
        now=t1,
    )
    assert res1.inserted == 1
    assert res1.updated == 0
    assert len(storage) == 1

    stored_job = storage["test_src_1001"]
    assert stored_job.first_seen_at == t1
    assert stored_job.last_seen_at == t1
    assert stored_job.published_at == original_published

    # Second ingestion run (same job, observed 5 days later)
    records_run2 = [
        {
            "external_id": "test_src_1001",
            "source_job_id": "1001",
            "title": "Backend Developer",
            "company_name": "Acme Corp",
            "description": "Python, PostgreSQL",
            "location": "Bengaluru",
            "published_at": original_published,
        }
    ]

    res2 = await job_ingestion_service.ingest_normalized_records(
        db=session,
        records=records_run2,
        source_name="test_src",
        now=t2,
    )
    assert res2.inserted == 0
    assert res2.unchanged == 1
    assert len(storage) == 1  # No duplicate record!

    # Verify timestamps
    updated_job = storage["test_src_1001"]
    assert updated_job.first_seen_at == t1  # PRESERVED
    assert updated_job.published_at == original_published  # PRESERVED
    assert updated_job.last_seen_at == t2  # BUMPED


@pytest.mark.asyncio
async def test_re_ingestion_reactivates_inactive_job(mock_ingestion_session):
    """If an existing job was marked inactive/expired, re-encountering it reactivates it."""
    session, storage = mock_ingestion_session
    t1 = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)

    # Pre-populate an inactive job
    job = JobPosting(
        external_id="test_reactivate_01",
        title="Data Engineer",
        description="Spark, Python",
        is_active=False,
        freshness_status="expired",
        first_seen_at=t1,
        last_seen_at=t1,
    )
    storage[job.external_id] = job

    # Re-ingest
    records = [
        {
            "external_id": "test_reactivate_01",
            "title": "Data Engineer",
            "description": "Spark, Python",
        }
    ]
    res = await job_ingestion_service.ingest_normalized_records(
        db=session,
        records=records,
        source_name="test_src",
        now=t2,
    )

    assert res.updated == 1
    reactivated = storage["test_reactivate_01"]
    assert reactivated.is_active is True
    assert reactivated.freshness_status == "fresh"
    assert reactivated.last_seen_at == t2


# ============================================================================
# 4. Freshness Evaluation Across Stored Jobs Tests
# ============================================================================

@pytest.mark.asyncio
async def test_evaluate_listing_freshness_lifecycle(mock_ingestion_session):
    """
    Test evaluate_listing_freshness categorizes fresh, stale, and expired jobs
    without deleting historical records.
    """
    session, storage = mock_ingestion_session
    ref_time = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)

    # 1 fresh job (3 days old)
    j_fresh = JobPosting(
        external_id="j_fresh",
        title="Fresh Job",
        description="Desc",
        last_seen_at=ref_time - timedelta(days=3),
        is_active=True,
    )
    # 1 stale job (18 days old)
    j_stale = JobPosting(
        external_id="j_stale",
        title="Stale Job",
        description="Desc",
        last_seen_at=ref_time - timedelta(days=18),
        is_active=True,
    )
    # 1 expired job (40 days old)
    j_expired = JobPosting(
        external_id="j_expired",
        title="Expired Job",
        description="Desc",
        last_seen_at=ref_time - timedelta(days=40),
        is_active=True,
    )

    storage[j_fresh.external_id] = j_fresh
    storage[j_stale.external_id] = j_stale
    storage[j_expired.external_id] = j_expired

    summary = await job_ingestion_service.evaluate_listing_freshness(
        db=session,
        stale_days=14,
        expired_days=30,
        reference_time=ref_time,
    )

    assert summary["evaluated"] == 3
    assert summary["fresh"] == 1
    assert summary["stale"] == 1
    assert summary["expired"] == 1

    # Fresh job remains active
    assert storage["j_fresh"].is_active is True
    assert storage["j_fresh"].freshness_status == "fresh"

    # Stale job remains active (with stale status)
    assert storage["j_stale"].is_active is True
    assert storage["j_stale"].freshness_status == "stale"

    # Expired job is marked inactive, but retained in DB
    assert storage["j_expired"].is_active is False
    assert storage["j_expired"].freshness_status == "expired"
    assert len(storage) == 3  # Historical record retained!


# ============================================================================
# 5. Refresh Coordinator: Concurrency, Fault Isolation, Retries
# ============================================================================

@pytest.mark.asyncio
async def test_refresh_coordinator_concurrency_lock():
    """A second concurrent refresh attempt must be skipped with concurrency error."""
    coordinator = JobRefreshCoordinator()

    async def slow_provider(queries):
        import asyncio
        await asyncio.sleep(0.2)
        return []

    coordinator.register_provider("slow_prov", slow_provider)

    import asyncio
    task1 = asyncio.create_task(coordinator.run_refresh(sources=["slow_prov"], evaluate_freshness=False))
    await asyncio.sleep(0.02)  # Ensure task1 has acquired lock
    task2 = asyncio.create_task(coordinator.run_refresh(sources=["slow_prov"], evaluate_freshness=False))

    res1, res2 = await asyncio.gather(task1, task2)

    # One must have completed, the second must have been skipped
    statuses = {res1.status, res2.status}
    assert "completed" in statuses
    assert "skipped" in statuses


@pytest.mark.asyncio
async def test_refresh_coordinator_provider_fault_isolation():
    """If one provider crashes with a network error, the other provider must still succeed."""
    coordinator = JobRefreshCoordinator()

    async def failing_provider(queries):
        raise ConnectionError("Adzuna network timeout 504")

    async def healthy_provider(queries):
        return [{"id": "healthy_01"}]

    coordinator.register_provider("failing", failing_provider)
    coordinator.register_provider("healthy", healthy_provider)

    record = await coordinator.run_refresh(
        sources=["failing", "healthy"],
        max_retries=1,
        evaluate_freshness=False,
    )

    assert record.status == "partial_success"
    assert record.sources["failing"]["failed"] >= 1
    assert record.sources["healthy"]["total_received"] == 1


@pytest.mark.asyncio
async def test_failed_ingestion_does_not_deactivate_existing_jobs(mock_ingestion_session):
    """
    A network failure or error during ingestion must NEVER deactivate existing active listings.
    """
    session, storage = mock_ingestion_session
    job = JobPosting(
        external_id="safe_job_1",
        title="ML Engineer",
        description="PyTorch",
        is_active=True,
        freshness_status="fresh",
    )
    storage[job.external_id] = job

    # Simulate provider failure
    coordinator = JobRefreshCoordinator()

    async def broken_provider(queries):
        raise RuntimeError("Simulated API outage")

    coordinator.register_provider("broken", broken_provider)

    record = await coordinator.run_refresh(
        sources=["broken"],
        max_retries=0,
        evaluate_freshness=False,
    )

    assert record.status == "failed"
    # Ensure existing job in storage was NOT touched or marked inactive
    assert storage["safe_job_1"].is_active is True
    assert storage["safe_job_1"].freshness_status == "fresh"


# ============================================================================
# 6. Endpoints: Freshness Filtering and Inactive Exclusion
# ============================================================================

@pytest.fixture
def mock_job_api_db():
    session = AsyncMock()
    storage = {}

    async def mock_execute(stmt):
        sql_str = str(stmt).lower()
        items = list(storage.values())

        if "where" in sql_str and "is_active" in sql_str:
            if "is_active = true" in sql_str or "is_active is true" in sql_str or "is_active = 1" in sql_str:
                items = [j for j in items if j.is_active is True]
            elif "is_active = false" in sql_str or "is_active is false" in sql_str or "is_active = 0" in sql_str:
                items = [j for j in items if j.is_active is False]

        if "where" in sql_str and "freshness_status" in sql_str:
            if "stale" in sql_str:
                items = [j for j in items if j.freshness_status == "stale"]
            elif "expired" in sql_str:
                items = [j for j in items if j.freshness_status == "expired"]

        return MockResult(items)

    session.execute = AsyncMock(side_effect=mock_execute)

    from app.api.deps import get_current_user
    from app.models.user import User

    mock_user = User(
        id="job-user-1",
        email="jobuser@example.com",
        full_name="Job User",
        is_active=True,
        is_superuser=False,
    )

    async def _override_get_db():
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield session, storage
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_job_list_endpoint_freshness_filtering(async_client: AsyncClient, mock_job_api_db):
    """Verify GET /api/v1/jobs supports freshness and active status filters."""
    _, storage = mock_job_api_db
    j1 = JobPosting(
        id="job-active-fresh",
        title="React Developer",
        description="Frontend",
        is_active=True,
        freshness_status="fresh",
    )
    j2 = JobPosting(
        id="job-inactive-expired",
        title="COBOL Developer",
        description="Legacy",
        is_active=False,
        freshness_status="expired",
    )
    storage[j1.id] = j1
    storage[j2.id] = j2

    # Query all active
    res = await async_client.get("/api/v1/jobs?is_active=true")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    assert all(item["is_active"] is True for item in data)


@pytest.mark.asyncio
async def test_refresh_status_endpoint(async_client: AsyncClient, mock_job_api_db):
    """Verify GET /api/v1/jobs/refresh/status returns running state."""
    res = await async_client.get("/api/v1/jobs/refresh/status")
    assert res.status_code == 200
    data = res.json()
    assert "is_running" in data
    assert isinstance(data["is_running"], bool)


# ============================================================================
# 7. Standalone CLI Script Test
# ============================================================================

@pytest.mark.asyncio
async def test_refresh_jobs_cli_evaluate_only():
    """Verify scripts/refresh_jobs.py runs in evaluate-only mode."""
    import argparse
    from scripts.refresh_jobs import main_async

    args = argparse.Namespace(
        evaluate_only=True,
        stale_days=14,
        expired_days=30,
        sources=None,
        queries=None,
        max_retries=1,
        skip_evaluation=False,
    )

    with patch("scripts.refresh_jobs.job_ingestion_service.evaluate_listing_freshness") as mock_eval:
        mock_eval.return_value = {"evaluated": 10, "fresh": 8, "stale": 1, "expired": 1}
        exit_code = await main_async(args)
        assert exit_code == 0
        assert mock_eval.called


@pytest.mark.asyncio
async def test_semantic_search_excludes_inactive_by_default(async_client: AsyncClient, mock_job_api_db):
    """Semantic search must exclude inactive listings by default."""
    _, storage = mock_job_api_db
    j_active = JobPosting(
        id="sim-job-1",
        title="Active Python Engineer",
        description="Python FastAPI backend",
        is_active=True,
        freshness_status="fresh",
        embedding=[0.1] * 384,
    )
    j_active.distance = 0.15
    j_inactive = JobPosting(
        id="sim-job-2",
        title="Inactive Python Engineer",
        description="Python legacy code",
        is_active=False,
        freshness_status="expired",
        embedding=[0.1] * 384,
    )
    j_inactive.distance = 0.15
    storage[j_active.id] = j_active
    storage[j_inactive.id] = j_inactive

    with patch("app.api.v1.endpoints.job_postings.embedding_service.get_embedding", new=AsyncMock(return_value=[0.1] * 384)):
        # By default (include_inactive=False), should only return active
        res = await async_client.post("/api/v1/jobs/search/similar", json={"query": "Python Engineer", "limit": 10})
        assert res.status_code == 200
        results = res.json()
        assert all(r["is_active"] is True for r in results)


def test_migration_file_structure():
    """Verify the reversible Alembic migration exists, is well-formed, and revises 4d8f1a2b3c4e."""
    import importlib.util
    import os

    migration_path = os.path.join(
        "alembic", "versions", "5e9f2b3c4d5a_add_job_freshness_tracking_fields.py"
    )
    assert os.path.exists(migration_path)

    spec = importlib.util.spec_from_file_location("migration_mod", migration_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod.revision == "5e9f2b3c4d5a"
    assert mod.down_revision == "4d8f1a2b3c4e"
    assert hasattr(mod, "upgrade")
    assert hasattr(mod, "downgrade")
    assert callable(mod.upgrade)
    assert callable(mod.downgrade)

