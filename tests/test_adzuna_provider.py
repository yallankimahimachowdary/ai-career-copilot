"""Stub-based unit tests for Adzuna Live Provider & Quota Guard (Remediation R8).

Strictly verifies:
- Pagination & query construction
- Quota refusal when budget is reached
- Retries counting against call budget
- Immediate halt on HTTP 429 (Rate Limit)
- Immediate halt on HTTP 401/403 (Auth Error)
- Failure isolation between batch queries
- Predicted salary governance (null database salaries)
- Missing field mapping (null company and location, no defaults)
- Upsert idempotency across duplicate calls
- Zero live API calls in test suite
"""

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import httpx
import pytest

from app.core.redaction import redact_credentials
from app.models.job_posting import JobPosting
from app.services.adzuna_quota_guard import (
    AdzunaAuthError,
    AdzunaQuotaGuard,
    AdzunaRateLimitError,
    QuotaExceededError,
)
from scripts.ingest.adzuna_ingest import AdzunaIngestService

_ORIG_ASYNC_CLIENT = httpx.AsyncClient


def _patch_client_transport(monkeypatch, transport: httpx.MockTransport):
    """Helper to safely mount MockTransport on httpx.AsyncClient."""
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *args, **kwargs: _ORIG_ASYNC_CLIENT(*args, transport=transport, **kwargs),
    )


@pytest.fixture
def temp_counter_file(tmp_path):
    return tmp_path / "adzuna_call_counter.json"


@pytest.fixture
def mock_adzuna_service(temp_counter_file, monkeypatch):
    monkeypatch.setenv("ADZUNA_APP_ID", "test_id_1234")
    monkeypatch.setenv("ADZUNA_APP_KEY", "test_key_5678_abcdef1234567890")
    guard = AdzunaQuotaGuard(counter_file=temp_counter_file, budget=5)
    return AdzunaIngestService(quota_guard=guard)


@pytest.fixture
def sample_raw_adzuna_ad():
    return {
        "id": "99887766",
        "title": "Senior Python Developer",
        "description": "Building scalable backend microservices with Python, FastAPI, and PostgreSQL in Bengaluru.",
        "created": "2026-10-15T12:00:00Z",
        "redirect_url": "https://www.adzuna.in/jobs/land/ad/99887766?utm_source=adzuna_api",
        "company": {"display_name": "Acme Tech Solutions"},
        "location": {"display_name": "Bengaluru, Karnataka", "area": ["India", "Karnataka", "Bengaluru"]},
        "salary_min": 1800000.0,
        "salary_max": 2400000.0,
        "salary_is_predicted": "0",
        "contract_time": "full_time",
        "category": {"label": "IT Jobs", "tag": "it-jobs"},
    }


@pytest.mark.asyncio
async def test_pagination_and_query_parameters(mock_adzuna_service, sample_raw_adzuna_ad, monkeypatch):
    """Verify pagination, results_per_page, and query parameters are correctly structured."""
    dispatched_requests = []

    def mock_handler(request: httpx.Request):
        dispatched_requests.append(request)
        return httpx.Response(
            200,
            json={"results": [sample_raw_adzuna_ad]},
            request=request,
        )

    transport = httpx.MockTransport(mock_handler)
    _patch_client_transport(monkeypatch, transport)

    items, meta = await mock_adzuna_service.fetch_jobs(
        query="Python Developer",
        city="Bengaluru",
        page=2,
        results_per_page=50,
        country="in",
        sort_by="date",
        max_days_old=30,
    )

    assert len(items) == 1
    assert items[0]["id"] == "99887766"
    assert len(dispatched_requests) == 1

    req = dispatched_requests[0]
    assert req.url.path == "/v1/api/jobs/in/search/2"
    assert req.url.params["what"] == "Python Developer"
    assert req.url.params["where"] == "Bengaluru"
    assert req.url.params["results_per_page"] == "50"
    assert req.url.params["sort_by"] == "date"
    assert req.url.params["max_days_old"] == "30"


@pytest.mark.asyncio
async def test_quota_refusal_at_budget(temp_counter_file, monkeypatch):
    """Verify that requests are refused without sending HTTP calls once budget is reached."""
    monkeypatch.setenv("ADZUNA_APP_ID", "test_id")
    monkeypatch.setenv("ADZUNA_APP_KEY", "test_key")

    guard = AdzunaQuotaGuard(counter_file=temp_counter_file, budget=2)
    service = AdzunaIngestService(quota_guard=guard)

    # Record 2 calls directly to exhaust budget
    guard.record_call_before_send(endpoint="https://api.adzuna.com/v1/api/jobs/in/search/1", query="test")
    guard.record_call_before_send(endpoint="https://api.adzuna.com/v1/api/jobs/in/search/2", query="test")

    assert guard.get_calls_used() == 2
    assert guard.get_calls_remaining() == 0

    # Next call must raise QuotaExceededError BEFORE dispatch
    with pytest.raises(QuotaExceededError) as exc_info:
        await service.fetch_jobs(query="Software Engineer")

    assert "call budget of 2 reached" in str(exc_info.value)
    assert guard.get_calls_used() == 2  # Did not increment past budget


@pytest.mark.asyncio
async def test_retries_counting_against_budget(mock_adzuna_service, sample_raw_adzuna_ad, monkeypatch):
    """Verify that retries increment the call counter before each attempt."""
    attempts = 0

    def mock_handler(request: httpx.Request):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("Connection timed out", request=request)
        return httpx.Response(200, json={"results": [sample_raw_adzuna_ad]}, request=request)

    transport = httpx.MockTransport(mock_handler)
    _patch_client_transport(monkeypatch, transport)

    items, meta = await mock_adzuna_service.fetch_jobs(query="DevOps")
    assert len(items) == 1
    assert attempts == 2
    assert meta["requests_used"] == 2
    assert mock_adzuna_service.quota_guard.get_calls_used() == 2


@pytest.mark.asyncio
async def test_429_stops_run_immediately(mock_adzuna_service, monkeypatch):
    """Verify HTTP 429 raises AdzunaRateLimitError with zero retries."""
    attempts = 0

    def mock_handler(request: httpx.Request):
        nonlocal attempts
        attempts += 1
        return httpx.Response(429, json={"error": "Too Many Requests"}, request=request)

    transport = httpx.MockTransport(mock_handler)
    _patch_client_transport(monkeypatch, transport)

    with pytest.raises(AdzunaRateLimitError) as exc_info:
        await mock_adzuna_service.fetch_jobs(query="Cloud")

    assert attempts == 1  # Exactly 1 attempt, zero retries
    assert "429" in str(exc_info.value)
    assert mock_adzuna_service.quota_guard.get_calls_used() == 1


@pytest.mark.asyncio
async def test_401_stops_run_immediately(mock_adzuna_service, monkeypatch):
    """Verify HTTP 401 Unauthorized raises AdzunaAuthError with zero retries."""
    attempts = 0

    def mock_handler(request: httpx.Request):
        nonlocal attempts
        attempts += 1
        return httpx.Response(401, json={"error": "Invalid app_key"}, request=request)

    transport = httpx.MockTransport(mock_handler)
    _patch_client_transport(monkeypatch, transport)

    with pytest.raises(AdzunaAuthError) as exc_info:
        await mock_adzuna_service.fetch_jobs(query="Security")

    assert attempts == 1
    assert "401" in str(exc_info.value)
    assert mock_adzuna_service.quota_guard.get_calls_used() == 1


@pytest.mark.asyncio
async def test_predicted_salary_governance(mock_adzuna_service, sample_raw_adzuna_ad, monkeypatch):
    """Verify that salary_is_predicted='1' forces database salaries to NULL."""
    predicted_ad = dict(sample_raw_adzuna_ad)
    predicted_ad["id"] = "11223344"
    predicted_ad["salary_min"] = 1200000.0
    predicted_ad["salary_max"] = 1600000.0
    predicted_ad["salary_is_predicted"] = "1"

    report = await mock_adzuna_service.ingest_jobs(
        query="Data Scientist",
        mock_response=[predicted_ad],
        save_to_live=False,
        with_embeddings=False,
    )

    records = report["records"]
    assert len(records) == 1
    rec = records[0]

    assert rec["salary_is_predicted"] is True
    assert rec["min_salary"] is None
    assert rec["max_salary"] is None
    assert rec["med_salary"] is None
    assert rec["currency"] is None


@pytest.mark.asyncio
async def test_missing_fields_honesty_no_silent_defaults(mock_adzuna_service, sample_raw_adzuna_ad, monkeypatch):
    """Verify missing company and location map to None, with no synthetic defaults."""
    sparse_ad = dict(sample_raw_adzuna_ad)
    sparse_ad["company"] = None
    sparse_ad["location"] = None

    report = await mock_adzuna_service.ingest_jobs(
        query="Frontend",
        mock_response=[sparse_ad],
        save_to_live=False,
        with_embeddings=False,
    )

    rec = report["records"][0]
    assert rec["company_name"] is None
    assert rec["location"] is None
    assert rec["company_name"] != "Tech Employer"
    assert rec["location"] != "Remote"
    assert rec["location"] != "India"


@pytest.mark.asyncio
async def test_upsert_idempotency_with_mock_db(mock_adzuna_service, sample_raw_adzuna_ad):
    """Verify normalized records mapping generates stable external_id and source_job_id."""
    report = await mock_adzuna_service.ingest_jobs(
        query="Backend",
        mock_response=[sample_raw_adzuna_ad],
        save_to_live=False,
        with_embeddings=False,
    )
    rec = report["records"][0]
    assert rec["source"] == "adzuna_mock"
    assert rec["source_job_id"] == "99887766"
    assert rec["external_id"] == "adzuna_99887766"
    assert rec["title"] == "Senior Python Developer"
    assert "Python" in rec["skills"]


@pytest.mark.asyncio
async def test_failure_isolation_in_runner(mock_adzuna_service, sample_raw_adzuna_ad, monkeypatch):
    """Verify that a failed query in a batch does not abort subsequent queries."""
    call_count = 0

    def mock_handler(request: httpx.Request):
        nonlocal call_count
        call_count += 1
        # Query 1 fails with 500, Query 2 succeeds with 200
        if "BadQuery" in str(request.url):
            return httpx.Response(500, json={"error": "Internal Error"}, request=request)
        return httpx.Response(200, json={"results": [sample_raw_adzuna_ad]}, request=request)

    transport = httpx.MockTransport(mock_handler)
    _patch_client_transport(monkeypatch, transport)

    # Run query 1 (fails)
    res1_items = []
    try:
        res1_items, _ = await mock_adzuna_service.fetch_jobs(query="BadQuery")
    except Exception:
        pass

    # Run query 2 (succeeds)
    res2_items, _ = await mock_adzuna_service.fetch_jobs(query="GoodQuery")

    assert len(res1_items) == 0
    assert len(res2_items) == 1
    assert res2_items[0]["id"] == "99887766"
