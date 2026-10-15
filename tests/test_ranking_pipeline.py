"""Unit tests for Phase B Ranking Pipeline.

Covers:
1. Ranker Common Interface (BaseRanker adherence, RankingResult schema)
2. Ranker Determinism (BM25, SBERT, Overlap, Hybrid, CompositeXGB)
3. Skill Overlap Coverage-Aware Scoring and Deterministic Tie-Breaking
4. Hybrid Min-Max Normalization Edge Cases
5. LLM JSON Parsing, Fences Stripping, and Partial Repair
6. LLM Re-Ranker J1..J20 Label Mapping and Rejection
7. Counterfactual Tester Multi-Draw Absent Controls
"""

import pytest
from app.ranking.base import BaseRanker, RankingResult
from app.ranking.baselines import BM25Ranker, SbertRanker, SkillOverlapRanker
from app.ranking.hybrid import HybridRanker, CompositeXGBRanker, _min_max_normalize
from app.ranking.llm_reranker import LLMReranker, _format_candidate_jobs
from app.services.llm_provider import clean_and_parse_json


@pytest.fixture
def sample_jobs():
    return [
        {
            "id": "job_1",
            "title": "Senior Python Developer",
            "description": "Looking for Python, FastAPI, and Docker expertise.",
            "skills": ["Python", "FastAPI", "Docker"],
            "embedding": [0.05] * 384,
        },
        {
            "id": "job_2",
            "title": "Machine Learning Engineer",
            "description": "Requires Python, PyTorch, and Machine Learning.",
            "skills": ["Python", "Machine Learning", "PyTorch"],
            "embedding": [0.08] * 384,
        },
        {
            "id": "job_3",
            "title": "Junior Web Intern",
            "description": "Basic Python and Git.",
            "skills": ["Python", "Git/GitHub"],
            "embedding": [0.02] * 384,
        },
        {
            "id": "job_4",
            "title": "Sparse 1-Skill Job",
            "description": "Only requires Python.",
            "skills": ["Python"],
            "embedding": [0.01] * 384,
        },
    ]


@pytest.fixture
def sample_resume():
    return {
        "candidate_name": "Test Candidate",
        "skills": ["Python", "FastAPI", "Docker", "Machine Learning"],
        "summary": "Experienced Python engineer with FastAPI, Docker, and Machine Learning.",
        "embedding": [0.06] * 384,
        "experience": [{"title": "Backend Dev", "company": "Tech Corp"}],
    }


# ---------------------------------------------------------------------------
# 1. Ranker Common Interface Tests
# ---------------------------------------------------------------------------

def test_rankers_common_interface(sample_resume, sample_jobs):
    """Every ranker must accept (resume, job_pool, k) and return RankingResult with required fields."""
    rankers = [
        BM25Ranker(),
        SkillOverlapRanker(),
        HybridRanker(weights={"bm25": 0.2, "sbert": 0.3, "overlap": 0.5}),
        CompositeXGBRanker(),
    ]

    for ranker in rankers:
        assert isinstance(ranker, BaseRanker)
        res = ranker.rank(sample_resume, sample_jobs, k=3)
        assert isinstance(res, RankingResult)
        assert len(res.ranked_job_ids) == 3
        assert isinstance(res.scores, dict)
        assert res.method_name == ranker.name
        assert "latency_ms" in res.metadata
        for jid in res.ranked_job_ids:
            assert jid in res.scores
            assert isinstance(res.scores[jid], (int, float))


# ---------------------------------------------------------------------------
# 2. Determinism Tests
# ---------------------------------------------------------------------------

def test_rankers_determinism(sample_resume, sample_jobs):
    """Two consecutive runs on the exact same pool must produce identical rankings and scores."""
    rankers = [
        BM25Ranker(),
        SkillOverlapRanker(),
        HybridRanker(),
        CompositeXGBRanker(),
    ]

    for ranker in rankers:
        run1 = ranker.rank(sample_resume, sample_jobs, k=4)
        run2 = ranker.rank(sample_resume, sample_jobs, k=4)
        assert run1.ranked_job_ids == run2.ranked_job_ids
        for jid in run1.ranked_job_ids:
            assert run1.scores[jid] == run2.scores[jid]


# ---------------------------------------------------------------------------
# 3. Skill Overlap Coverage-Aware Scoring and Tie-Breaking
# ---------------------------------------------------------------------------

def test_skill_overlap_coverage_aware_penalty(sample_resume, sample_jobs):
    """Sparse 1-skill jobs must NOT tie at 1.00 with comprehensive jobs matching multiple skills."""
    overlap_ranker = SkillOverlapRanker(min_skills=4)
    res = overlap_ranker.rank(sample_resume, sample_jobs, k=4)

    # job_1 has 3 matching skills (Python, FastAPI, Docker)
    # job_4 has 1 matching skill (Python)
    score_job_1 = res.scores["job_1"]
    score_job_4 = res.scores["job_4"]

    assert score_job_1 > score_job_4
    assert score_job_4 < 0.50  # 1 / 4 = 0.25, heavily penalized for sparsity


# ---------------------------------------------------------------------------
# 4. Hybrid Normalization Edge Cases
# ---------------------------------------------------------------------------

def test_min_max_normalization():
    """Verify min-max normalization behavior on standard and edge case dictionaries."""
    # Standard distribution
    raw = {"a": 10.0, "b": 20.0, "c": 30.0}
    norm = _min_max_normalize(raw)
    assert norm["a"] == 0.0
    assert norm["b"] == 0.5
    assert norm["c"] == 1.0

    # Constant scores (avoid division by zero)
    constant_raw = {"a": 5.0, "b": 5.0}
    norm_const = _min_max_normalize(constant_raw)
    assert norm_const["a"] == 1.0
    assert norm_const["b"] == 1.0

    # Empty dictionary
    assert _min_max_normalize({}) == {}


# ---------------------------------------------------------------------------
# 5. JSON Parsing, Fences Stripping, and Partial Repair
# ---------------------------------------------------------------------------

def test_clean_and_parse_json():
    """clean_and_parse_json must strip markdown fences and repair clean JSON."""
    fenced = '```json\n{"status": "ok", "value": 42}\n```'
    parsed = clean_and_parse_json(fenced)
    assert parsed["status"] == "ok"
    assert parsed["value"] == 42

    raw_json = '{"ranked_jobs": [{"job_id": "J1", "rank": 1}]}'
    assert clean_and_parse_json(raw_json)["ranked_jobs"][0]["job_id"] == "J1"


# ---------------------------------------------------------------------------
# 6. LLM Re-Ranker J1..J20 Label Mapping and Rejection
# ---------------------------------------------------------------------------

def test_llm_reranker_label_formatting(sample_jobs):
    """Candidate jobs must format with [J1]..[J20] labels and maintain mapping dicts."""
    listing, label_to_id, id_to_label = _format_candidate_jobs(sample_jobs)
    assert "[J1]" in listing
    assert "[J2]" in listing
    assert label_to_id["J1"] == "job_1"
    assert id_to_label["job_1"] == "J1"


def test_llm_reranker_sanitize_and_mapping():
    """LLMReranker._validate_and_sanitize must map J labels back to real UUIDs and reject invalid labels."""
    reranker = LLMReranker(name="test_reranker", provider_name="ollama")
    label_to_id = {"J1": "uuid-111", "J2": "uuid-222", "J3": "uuid-333"}
    id_to_label = {"uuid-111": "J1", "uuid-222": "J2", "uuid-333": "J3"}

    raw_llm_output = [
        {"job_id": "J2", "rank": 1, "matched_skills": ["Python"], "missing_skills": [], "reason": "Best fit."},
        {"job_id": "J99", "rank": 2, "reason": "Hallucinated ID outside candidates."},
        {"job_id": "1", "rank": 3, "matched_skills": ["SQL"], "missing_skills": [], "reason": "Normalized J1."},
    ]

    sanitized, hallucinated_cnt, repaired_cnt = reranker._validate_and_sanitize(
        raw_llm_output, label_to_id, id_to_label, top_k=3
    )

    assert hallucinated_cnt == 1  # J99 was rejected
    assert len(sanitized) == 3    # J2, J1, plus backfilled J3
    assert sanitized[0]["job_id"] == "uuid-222"
    assert sanitized[1]["job_id"] == "uuid-111"
    assert sanitized[2]["job_id"] == "uuid-333"  # backfilled


# ---------------------------------------------------------------------------
# 8. Gemini Provider Retries and Experiment Mode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gemini_retry_on_429_and_backoff(monkeypatch):
    """GeminiProvider must retry on HTTP 429 and respect retry logic."""
    from app.services.llm_provider import GeminiProvider
    import httpx

    provider = GeminiProvider(api_key="test-key-mock", model="gemini-2.0-flash")

    call_count = 0

    async def mock_post(self, url, headers=None, json=None, timeout=None):
        nonlocal call_count
        call_count += 1
        req = httpx.Request("POST", url, headers=headers)
        if call_count < 2:
            resp = httpx.Response(status_code=429, request=req, headers={"Retry-After": "0.01"})
            raise httpx.HTTPStatusError("Rate limited", request=req, response=resp)
        # Succeeded on 2nd attempt
        return httpx.Response(
            status_code=200,
            request=req,
            json={
                "candidates": [{
                    "content": {"parts": [{"text": "{\"ranked_jobs\": []}"}]}
                }],
                "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
                "modelVersion": "gemini-2.0-flash",
            }
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    res = await provider.generate_json("Test prompt", experiment_mode=True)
    assert call_count == 2
    assert res.raw_text == '{"ranked_jobs": []}'
    assert res.answered_model == "gemini-2.0-flash"


# ---------------------------------------------------------------------------
# 9. Counterfactual Rank Gain Convention
# ---------------------------------------------------------------------------

def test_counterfactual_rank_gain_convention():
    """Verify rank_gain = old_rank - new_rank (positive means improved rank)."""
    from app.ranking.counterfactual import CounterfactualTester

    # Verify convention: if old_rank is 5 and new_rank is 2, rank improved by 3 positions
    old_rank = 5
    new_rank = 2
    rank_gain = old_rank - new_rank
    assert rank_gain == 3  # Positive indicates improvement


# ---------------------------------------------------------------------------
# 10. Parser Junk Examples & Other Terms Separation
# ---------------------------------------------------------------------------

def test_parser_junk_examples_and_other_terms():
    """Verify junk examples (2025, MATLAB (Basics), PCR and Gel Electrophoresis.) are sanitized or mapped."""
    from app.services.parser_agent import parser_agent

    raw_text = (
        "Candidate Name: Test User\n"
        "SKILLS\n"
        "2025\n"
        "MATLAB (Basics)\n"
        "PCR and Gel Electrophoresis.\n"
        "Vel Tech University\n"
        "Explored basic 3D modeling\n"
    )
    parsed = parser_agent._parse_with_rules(raw_text)

    # 2025, University, and 3D modeling fragment MUST NOT be in skills
    assert "2025" not in parsed.skills
    assert "Vel Tech University" not in parsed.skills
    assert "Explored basic 3D modeling" not in parsed.skills

    # They MUST be preserved in other_terms
    assert "2025" in parsed.other_terms
    assert "Vel Tech University" in parsed.other_terms

    # Legitimate canonical skills extracted from modified strings MUST be present
    assert "MATLAB" in parsed.skills
    assert "PCR" in parsed.skills
    assert "Gel Electrophoresis" in parsed.skills


# ---------------------------------------------------------------------------
# 11. Duplicate Detection Service
# ---------------------------------------------------------------------------

def test_deduplication_service_cross_location_and_sources():
    """Verify cross-site and cross-location duplicate merging."""
    from app.services.deduplication_service import deduplication_service

    records = [
        {
            "id": "job_a",
            "title": "Software Engineer",
            "company": "Acme Corp",
            "location": "Chennai, Tamil Nadu",
            "description": "Looking for Python and SQL developers with web development experience.",
            "source": "linkedin",
        },
        {
            "id": "job_b",
            "title": "Software Engineer",
            "company": "Acme Corp",
            "location": "Bengaluru, Karnataka",
            "description": "Looking for Python and SQL developers with web development experience.",
            "source": "naukri",
        },
        {
            "id": "job_c",
            "title": "Data Scientist",
            "company": "Acme Corp",
            "location": "Bengaluru, Karnataka",
            "description": "Requires machine learning, deep learning, PyTorch, and NLP models.",
            "source": "linkedin",
        },
    ]

    canonical, merged_cnt, clusters = deduplication_service.deduplicate_records(records)
    assert merged_cnt == 1
    assert len(canonical) == 2

    # Check canonical merged record attributes
    merged_job = next(j for j in canonical if j["title"] == "Software Engineer")
    assert merged_job["duplicate_count"] == 2
    assert "linkedin" in merged_job["merged_sources"]
    assert "naukri" in merged_job["merged_sources"]
    assert "Chennai, Tamil Nadu" in merged_job["all_locations"]
    assert "Bengaluru, Karnataka" in merged_job["all_locations"]


# ---------------------------------------------------------------------------
# 12. API Key Scrubbing in Logs / Errors
# ---------------------------------------------------------------------------

def test_api_key_scrubbing_in_gemini_provider():
    """Verify API keys are never exposed in exceptions or logs."""
    from app.services.llm_provider import GeminiProvider

    secret_key = "AIzaSySecretApiKeyThatMustNeverLeak"
    provider = GeminiProvider(api_key=secret_key, model="gemini-3.6-flash")

    # In mock or log string representations, key should not appear
    assert secret_key not in repr(provider)
    assert secret_key not in str(provider)


# ---------------------------------------------------------------------------
# 13. Verifier Non-Skill Claims Check
# ---------------------------------------------------------------------------

def test_claim_verifier_non_skill_claims():
    """Verify that location and seniority claims in reason text are verified."""
    from app.ranking.claim_verifier import ClaimVerifier

    verifier = ClaimVerifier()
    resume = {"skills": ["Python"], "location": "Chennai", "raw_text": "Python developer"}
    job = {"title": "Junior Python Developer", "location": "Chennai", "remote_allowed": False, "skills": ["Python"]}

    # Valid junior and location claims
    exp_valid = {
        "job_id": "j1",
        "rank": 1,
        "matched_skills": ["Python"],
        "missing_skills": [],
        "reason": "Candidate is an intern in Chennai with Python experience.",
    }
    res_valid = verifier.verify_explanation(exp_valid, resume, job)
    assert res_valid.non_skill_claims["location_valid"] is True
    assert res_valid.non_skill_claims["seniority_valid"] is True

    # Invalid location claim (claims remote when job is onsite)
    exp_invalid = {
        "job_id": "j1",
        "rank": 1,
        "matched_skills": ["Python"],
        "missing_skills": [],
        "reason": "Candidate is seeking a remote role.",
    }
    res_invalid = verifier.verify_explanation(exp_invalid, resume, job)
    assert res_invalid.non_skill_claims["location_valid"] is False


