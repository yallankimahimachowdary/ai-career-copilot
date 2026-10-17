"""Tests for No-Mock Guards (Prompt P1C).

Verifies:
1. Experiment runner strictly raises RuntimeError when GEMINI_API_KEY is missing (no fallback to mock).
2. Experiment runner strictly rejects 'hybrid_llm_gemini-mock'.
3. Adzuna ingest service strictly raises ValueError when save_to_live=True is attempted with mock data.
4. Adzuna ingest service safely processes mock data in isolated mode when save_to_live=False.
"""

import os
import pytest
from unittest.mock import patch

from scripts.ingest.adzuna_ingest import AdzunaIngestService
from scripts.run_ranking_experiment import instantiate_rankers


def test_runner_raises_when_gemini_api_key_missing(monkeypatch):
    """The experiment runner must raise RuntimeError when GEMINI_API_KEY is missing."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with patch("app.core.config.settings.GEMINI_API_KEY", None):
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY is missing; mock fallback is prohibited"):
            instantiate_rankers(["hybrid_llm_gemini"])


def test_runner_rejects_explicit_gemini_mock():
    """The experiment runner must prohibit hybrid_llm_gemini-mock."""
    with pytest.raises(RuntimeError, match="hybrid_llm_gemini-mock is prohibited in experiment runs"):
        instantiate_rankers(["hybrid_llm_gemini-mock"])


@pytest.mark.asyncio
async def test_adzuna_save_to_live_disabled_for_mock_response():
    """Calling ingest_jobs with mock_response and save_to_live=True must raise ValueError."""
    service = AdzunaIngestService()
    mock_items = [
        {
            "id": "mock_test_01",
            "title": "Software Engineer",
            "company": {"display_name": "Test Company"},
            "location": {"display_name": "Bengaluru"},
            "description": "Python, FastAPI development",
        }
    ]
    with pytest.raises(ValueError, match="save_to_live is strictly disabled for mock Adzuna data"):
        await service.ingest_jobs(query="Software Engineer", mock_response=mock_items, save_to_live=True)


@pytest.mark.asyncio
async def test_adzuna_save_to_live_disabled_when_credentials_missing(monkeypatch):
    """Calling ingest_jobs without credentials and save_to_live=True must raise ValueError."""
    service = AdzunaIngestService()
    service.app_id = None
    service.app_key = None
    with pytest.raises(ValueError, match="ADZUNA credentials not configured"):
        await service.ingest_jobs(query="Software Engineer", save_to_live=True)


@pytest.mark.asyncio
async def test_adzuna_mock_ingest_allowed_when_isolated():
    """Mock ingest is permitted in isolated mode (save_to_live=False) without writing to live stores."""
    service = AdzunaIngestService()
    mock_items = [
        {
            "id": "mock_iso_01",
            "title": "Backend Developer",
            "company": {"display_name": "Isolated Tech"},
            "location": {"display_name": "Remote"},
            "description": "Python, Docker",
        }
    ]
    records = await service.ingest_jobs(query="Backend Developer", mock_response=mock_items, save_to_live=False)
    assert len(records) == 1
    assert records[0]["source"] == "adzuna_mock"
    assert records[0]["external_id"] == "adzuna_mock_iso_01"


def test_strict_manifest_validation_rejects_missing_file(tmp_path):
    """Strict manifest mode must raise FileNotFoundError if manifest file is missing, never falling back to dir scan."""
    from scripts.run_ranking_experiment import load_and_anonymize_resumes
    fake_manifest = tmp_path / "nonexistent_manifest.json"
    with pytest.raises(FileNotFoundError, match="Strict manifest validation failed: manifest file"):
        load_and_anonymize_resumes(
            resumes_dir=tmp_path,
            manifest_path=fake_manifest,
            strict_manifest=True,
        )


def test_strict_manifest_validation_rejects_missing_manifest_argument(tmp_path):
    """Strict manifest mode requires a manifest path; cannot be None."""
    from scripts.run_ranking_experiment import load_and_anonymize_resumes
    with pytest.raises(ValueError, match="manifest_path is required"):
        load_and_anonymize_resumes(
            resumes_dir=tmp_path,
            manifest_path=None,
            strict_manifest=True,
        )


def test_strict_manifest_validation_rejects_missing_resume_entry(tmp_path):
    """If a resume listed in manifest is missing, strict mode must fail loudly."""
    from scripts.run_ranking_experiment import load_and_anonymize_resumes
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text('{"resumes": [{"resume_file": "missing.pdf", "candidate_name": "Test"}]}')
    with pytest.raises(FileNotFoundError, match="resume file 'missing.pdf' declared in manifest"):
        load_and_anonymize_resumes(
            resumes_dir=tmp_path,
            manifest_path=manifest_file,
            strict_manifest=True,
        )


@pytest.mark.asyncio
async def test_gemini_experiment_mode_rejects_mock_response():
    """In experiment mode, supplying mock_response must strictly raise RuntimeError."""
    from app.services.llm_provider import GeminiProvider
    provider = GeminiProvider(api_key="valid-dummy-key")
    with pytest.raises(RuntimeError, match="Mock provider responses are strictly prohibited in experiment mode"):
        await provider.generate_json(
            "Test prompt",
            mock_response={"status": "ok"},
            experiment_mode=True,
        )


@pytest.mark.asyncio
async def test_gemini_request_payload_and_honest_seed_metadata(monkeypatch):
    """Verify Gemini request payload structure via mocked HTTP and confirm honest seed metadata."""
    import httpx
    from app.services.llm_provider import GeminiProvider

    captured_request = {}

    async def mock_post(self, url, headers=None, json=None, timeout=None):
        captured_request["url"] = url
        captured_request["headers"] = headers
        captured_request["json"] = json
        req = httpx.Request("POST", url, headers=headers)
        # Standard Gemini response (does NOT echo seed)
        return httpx.Response(
            status_code=200,
            request=req,
            json={
                "candidates": [{
                    "content": {"parts": [{"text": "{\"ranked_jobs\": []}"}]}
                }],
                "usageMetadata": {"promptTokenCount": 25, "candidatesTokenCount": 12},
                "modelVersion": "gemini-2.0-flash",
            }
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    provider = GeminiProvider(api_key="test-api-key", model="gemini-2.0-flash")
    resp = await provider.generate_json(
        prompt="Rank these candidates",
        temperature=0.0,
        max_tokens=400,
        seed=42,
        experiment_mode=True,
    )

    # 1. Verify HTTP request payload structure
    assert "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent" in captured_request["url"]
    assert captured_request["headers"]["x-goog-api-key"] == "test-api-key"
    assert captured_request["json"]["generationConfig"]["seed"] == 42
    assert captured_request["json"]["generationConfig"]["temperature"] == 0.0
    assert captured_request["json"]["generationConfig"]["maxOutputTokens"] == 400
    assert captured_request["json"]["generationConfig"]["response_mime_type"] == "application/json"
    assert captured_request["json"]["contents"][0]["parts"][0]["text"] == "Rank these candidates"

    # 2. Verify honest metadata: requested/sent seed is recorded, but unverified applied seed is None
    assert resp.seed_requested == 42
    assert resp.seed_sent == 42
    assert resp.seed_applied is None
    res_dict = resp.to_dict()
    assert res_dict["seed_requested"] == 42
    assert res_dict["seed_sent"] == 42
    assert res_dict["seed_applied"] is None
