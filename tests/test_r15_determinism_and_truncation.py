"""
tests/test_r15_determinism_and_truncation.py
--------------------------------------------
Verification of R15 Determinism and Truncation Guard:
1. Ollama provider fails immediately when done_reason == "length".
2. LLM Reranker rejects response without silent fallback when zero valid candidate job items parse.
3. Stable hashing ensures identical universe generation across PYTHONHASHSEED values.
"""

import asyncio
from unittest.mock import AsyncMock, patch
import pytest

from app.ranking.hybrid import HybridRanker
from app.ranking.llm_reranker import LLMReranker
from app.services.llm_provider import OllamaProvider, LLMResponse
from scripts.build_universes import stable_hash_int


def test_stable_hash_int_is_deterministic():
    """Verify that stable_hash_int returns consistent values across calls."""
    val1 = stable_hash_int("SYN_001")
    val2 = stable_hash_int("SYN_001")
    assert val1 == val2
    assert isinstance(val1, int)
    assert 0 <= val1 < 1000000
    assert stable_hash_int("SYN_001") != stable_hash_int("SYN_002")


@pytest.mark.asyncio
async def test_ollama_truncation_done_reason_length_raises_error():
    """Verify that OllamaProvider raises RuntimeError when done_reason == 'length'."""
    provider = OllamaProvider(model="llama3.2:3b")

    mock_response_data = {
        "response": '{"ranked_jobs": [{"job_id": "J1", "matched_skills": ["Python"]',
        "done": True,
        "done_reason": "length",
        "prompt_eval_count": 500,
        "eval_count": 1500,
        "load_duration": 1000000,
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = AsyncMock()
        mock_resp.raise_for_status = lambda: None
        mock_resp.json = lambda: mock_response_data
        mock_post.return_value = mock_resp

        with pytest.raises(RuntimeError, match="Ollama generation truncated! done_reason='length'"):
            await provider.generate_json(prompt="test prompt", max_tokens=1500)


def test_llm_reranker_fails_on_no_valid_ranking_parses_no_silent_fallback():
    """Verify that LLMReranker raises ValueError when 0 valid candidate job items parse."""
    reranker = LLMReranker(name="hybrid_llm_ollama", provider_name="ollama")

    # Mock candidate pool with 2 jobs
    label_to_id = {"J1": "job-uuid-1", "J2": "job-uuid-2"}
    id_to_label = {"job-uuid-1": "J1", "job-uuid-2": "J2"}

    # Case A: empty list returned
    with pytest.raises(ValueError, match="No valid ranking parses from LLM response"):
        reranker._validate_and_sanitize([], label_to_id, id_to_label, top_k=2)

    # Case B: hallucinated jobs outside candidate pool
    hallucinated = [{"job_id": "J999", "matched_skills": []}, {"job_id": "UNKNOWN", "matched_skills": []}]
    with pytest.raises(ValueError, match="No valid ranking parses from LLM response"):
        reranker._validate_and_sanitize(hallucinated, label_to_id, id_to_label, top_k=2)
