"""Unit tests for R6 Fairness Evaluation Harness and Positive Controls.

Verifies:
1. Anonymizer masks names and educational institutions.
2. Positive Control A (DemographicBiasedRanker) intentionally introduces bias and can fail fairness checks.
3. Positive Control B (InstitutionPrestigeBiasedRanker) intentionally boosts Tier 1 and penalizes Tier 3.
4. Ranking invariance helpers (Jaccard, Kendall Tau) correctly handle equal and divergent rankings.
"""

import pytest
from app.services.anonymizer import anonymize_resume
from scripts.evaluate_fairness_v2 import (
    BaseRanker,
    DemographicBiasedRanker,
    InstitutionPrestigeBiasedRanker,
    RankingResult,
    calculate_kendall_tau,
    calculate_topk_jaccard,
)


class MockBaseRanker(BaseRanker):
    def __init__(self, name: str = "mock_base"):
        super().__init__(name)

    def rank(self, resume, job_pool, k=10, base_res=None):
        job_ids = [j["id"] for j in job_pool[:k]]
        scores = {jid: 0.75 for jid in job_ids}
        return RankingResult(
            ranked_job_ids=job_ids,
            scores=scores,
            method_name="mock_base",
        )


@pytest.fixture
def sample_jobs():
    return [
        {"id": f"job_{i:03d}", "title": f"Software Engineer {i}", "skills": ["Python", "SQL"]}
        for i in range(10)
    ]


@pytest.fixture
def sample_resume():
    return {
        "candidate_name": "Alex Smith",
        "contact_info": {"name": "Alex Smith", "email": "alex@example.com"},
        "summary": "Software engineer with 5 years experience at Stanford University.",
        "skills": ["Python", "SQL", "Docker"],
        "education": [{"institution": "Stanford University", "degree": "BS"}],
    }


def test_anonymizer_institution_and_name_masking():
    raw_text = "Alex Smith graduated from Stanford University with a degree in CS."
    masked = anonymize_resume(raw_text, strip_institutions=True)
    assert "[INSTITUTION]" in masked or "Stanford" not in masked
    assert "Alex Smith" not in masked


def test_ranking_invariance_helpers():
    ranking_a = ["job_001", "job_002", "job_003"]
    ranking_b = ["job_001", "job_002", "job_003"]
    ranking_c = ["job_003", "job_002", "job_001"]

    assert calculate_topk_jaccard(ranking_a, ranking_b, k=3) == 1.0
    assert calculate_kendall_tau(ranking_a, ranking_b, k=3) == 1.0

    # Inverted ranking
    tau_inv = calculate_kendall_tau(ranking_a, ranking_c, k=3)
    assert tau_inv < 0.0


def test_positive_control_a_demographic_bias(sample_jobs, sample_resume):
    base_ranker = MockBaseRanker()
    biased_ranker = DemographicBiasedRanker(base_ranker=base_ranker)

    # Candidate with White demographic group
    res_white = {**sample_resume, "demographic_group": "White / Caucasian", "candidate_name": "Brad Miller"}
    res_black = {**sample_resume, "demographic_group": "Black / African American", "candidate_name": "Jamal Jackson"}

    res_white_out = biased_ranker.rank(res_white, sample_jobs, k=5)
    res_black_out = biased_ranker.rank(res_black, sample_jobs, k=5)

    white_score = list(res_white_out.scores.values())[0]
    black_score = list(res_black_out.scores.values())[0]

    # White candidate gets boost, Black candidate gets penalty
    assert white_score > black_score
    assert (white_score - black_score) >= 0.50


def test_positive_control_b_prestige_bias(sample_jobs, sample_resume):
    base_ranker = MockBaseRanker()
    biased_ranker = InstitutionPrestigeBiasedRanker(base_ranker=base_ranker)

    res_t1 = {**sample_resume, "institution_tier": "tier_1_elite"}
    res_t3 = {**sample_resume, "institution_tier": "tier_3_regional_community"}

    res_t1_out = biased_ranker.rank(res_t1, sample_jobs, k=5)
    res_t3_out = biased_ranker.rank(res_t3, sample_jobs, k=5)

    t1_score = list(res_t1_out.scores.values())[0]
    t3_score = list(res_t3_out.scores.values())[0]

    # Tier 1 gets boost, Tier 3 gets penalty
    assert t1_score > t3_score
    assert (t1_score - t3_score) >= 0.50
