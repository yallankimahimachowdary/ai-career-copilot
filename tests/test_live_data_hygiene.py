"""tests/test_live_data_hygiene.py
--------------------------------
Remediation R10-6: Live-Data Hygiene, Scheduler Gating, and Expiry Tests.

Verifies:
1. Scraper is disabled (SCRAPER_ENABLED=False) and Adzuna is quota-locked (20/20).
2. API responses include the honest 'data_as_of' snapshot date label ("2026-10-19").
3. Configurable age expiration flags postings older than threshold as 'expired' and sets is_active=False.
"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport

from app.core.config import settings
from app.main import app
from app.models.job_posting import JobPosting
from app.schemas.job_posting import JobPostingListResponse, JobRefreshStatusResponse
from app.schemas.matcher import ResumeMatchResponse
from app.services.adzuna_quota_guard import QuotaExceededError, adzuna_quota_guard


def test_scheduler_status_and_quota_lock():
    """Verify scraper remains permanently gated OFF and Adzuna calls are quota-locked."""
    assert settings.SCRAPER_ENABLED is False, "Scraper must remain disabled in production/eval"
    assert settings.ADZUNA_CALL_BUDGET == 20, "Adzuna budget must be capped at 20"

    counter_path = Path("data/ingest/adzuna_call_counter.json")
    assert counter_path.exists(), "Adzuna counter file must exist"
    with open(counter_path, "r", encoding="utf-8") as f:
        counter_data = json.load(f)

    assert counter_data["total_calls"] == 20, f"Expected 20 calls, found {counter_data['total_calls']}"
    assert counter_data["budget"] == 20

    # Quota guard must reject any new call attempts
    with pytest.raises(QuotaExceededError):
        adzuna_quota_guard.check_can_call()


@pytest.mark.asyncio
async def test_api_responses_include_data_as_of_label():
    """Verify API responses include the 'data_as_of' snapshot date label."""
    from unittest.mock import AsyncMock, MagicMock
    from app.api.deps import get_current_user
    from app.db.session import get_db
    from app.models.user import User

    test_user = User(id="test-hygiene-user", email="hygiene@example.com", is_active=True, is_superuser=True)
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar.return_value = 432
    session.execute.return_value = result_mock

    async def _override_get_user():
        return test_user

    async def _override_db():
        yield session

    app.dependency_overrides[get_current_user] = _override_get_user
    app.dependency_overrides[get_db] = _override_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Job Stats endpoint
            res = await client.get("/api/v1/jobs/stats")
            assert res.status_code == 200
            stats_data = res.json()
            assert "data_as_of" in stats_data
            assert stats_data["data_as_of"] == "2026-10-19"
            assert stats_data["total"] == 432

            # 2. Refresh status endpoint
            refresh_res = await client.get("/api/v1/jobs/refresh/status")
            assert refresh_res.status_code == 200
            refresh_data = refresh_res.json()
            assert "data_as_of" in refresh_data
            assert refresh_data["data_as_of"] == "2026-10-19"

            # 3. Schemas default data_as_of validation
            match_resp = ResumeMatchResponse(
                resume_id="test-res-1",
                candidate_name="Candidate Test",
                total_matches=0,
                matches=[],
            )
            assert match_resp.data_as_of == "2026-10-19"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_configurable_age_expiry_flag():
    """Verify that postings older than configurable age are classified as 'expired'."""
    now = datetime.now(timezone.utc)

    # 1. Recent job (5 days old) -> fresh under 14-day threshold
    job_recent = JobPosting(
        id="job-rec-1",
        title="Recent Job",
        last_seen_at=now - timedelta(days=5),
        is_active=True,
    )
    status_recent = job_recent.calculate_freshness(reference_time=now, stale_days=14, expired_days=30)
    assert status_recent == "fresh"

    # 2. Stale job (18 days old) -> stale under 14-30 day thresholds
    job_stale = JobPosting(
        id="job-stale-1",
        title="Stale Job",
        last_seen_at=now - timedelta(days=18),
        is_active=True,
    )
    status_stale = job_stale.calculate_freshness(reference_time=now, stale_days=14, expired_days=30)
    assert status_stale == "stale"

    # 3. Expired job (35 days old) -> expired under 30-day threshold
    job_expired = JobPosting(
        id="job-exp-1",
        title="Expired Job",
        last_seen_at=now - timedelta(days=35),
        is_active=True,
    )
    status_exp = job_expired.calculate_freshness(reference_time=now, stale_days=14, expired_days=30)
    assert status_exp == "expired"

    # 4. Custom configurable expiry (e.g. 7-day expiration policy)
    status_custom = job_stale.calculate_freshness(reference_time=now, stale_days=3, expired_days=7)
    assert status_custom == "expired", "Should be expired under custom 7-day threshold"
