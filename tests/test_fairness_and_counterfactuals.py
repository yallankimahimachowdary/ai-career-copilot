"""
tests/test_fairness_and_counterfactuals.py
-------------------------------------------
Unit and integration tests for Phase 7:
Fairness, Counterfactual Evaluation & Performance Benchmarking.
"""

import json
from pathlib import Path
import pytest

from app.ranking.baselines import BM25Ranker, SbertRanker, SkillOverlapRanker
from app.ranking.counterfactual import CounterfactualTester
from app.ranking.fairness import DEFAULT_SYNTHETIC_NAMES, NameSwapFairnessEvaluator
from app.ranking.hybrid import HybridRanker
from app.ranking.performance import (
    DEFAULT_PRICING_TABLE,
    PerformanceBenchmarkTracker,
    StageTimer,
    calculate_token_cost,
)


@pytest.fixture
def mock_pool():
    return [
        {
            "id": "job_01",
            "title": "Senior Python Engineer",
            "description": "Looking for Python, FastAPI, Docker, and Kubernetes experience.",
            "skills": ["Python", "FastAPI", "Docker", "Kubernetes"],
        },
        {
            "id": "job_02",
            "title": "Data Scientist",
            "description": "Seeking Python, Machine Learning, SQL, and PyTorch.",
            "skills": ["Python", "Machine Learning", "SQL", "PyTorch"],
        },
        {
            "id": "job_03",
            "title": "Frontend Engineer",
            "description": "Requires React, TypeScript, and CSS styling.",
            "skills": ["JavaScript", "React", "TypeScript"],
        },
    ]


@pytest.fixture
def sample_resume():
    return {
        "id": "cand_sample_123",
        "candidate_name": "Test Candidate",
        "skills": ["Python", "FastAPI"],
        "summary": "Experienced Python Backend developer with FastAPI.",
        "experience": [{"title": "Python Developer", "company": "Tech Corp"}],
    }


# ============================================================================
# 1. Counterfactual Interventions & Exclusion Rules Tests
# ============================================================================

def test_counterfactual_excludes_already_present_skills(mock_pool, sample_resume):
    """When a suggested skill is already present in the resume, it must be excluded."""
    sbert = SbertRanker()
    hybrid = HybridRanker(sbert_ranker=sbert, weights={"bm25": 0.1, "sbert": 0.1, "overlap": 0.8})
    tester = CounterfactualTester(hybrid_ranker=hybrid, sbert_ranker=sbert, seed=42)

    # Resume already has "Python" and "FastAPI". Suggest "Python" (already present) + "Docker" (missing)
    res = tester.evaluate_counterfactual_case(
        resume=sample_resume,
        target_job=mock_pool[0],
        job_pool=mock_pool,
        suggested_skills=["Python", "Docker"],
        n_control_draws=5,
    )

    assert res["is_valid"] is True
    assert "Python" in res["already_present_skills"]
    assert "Docker" in res["valid_skills"]
    assert len(res["valid_skills"]) == 1
    # Only valid missing skills should be evaluated
    assert len(res["individual_evaluations"]) == 1
    assert res["individual_evaluations"][0]["skill"] == "Docker"


def test_counterfactual_excludes_case_when_all_skills_already_present(mock_pool, sample_resume):
    """If all suggested skills are already in the resume, case is excluded as invalid."""
    sbert = SbertRanker()
    hybrid = HybridRanker(sbert_ranker=sbert, weights={"bm25": 0.1, "sbert": 0.1, "overlap": 0.8})
    tester = CounterfactualTester(hybrid_ranker=hybrid, sbert_ranker=sbert, seed=42)

    res = tester.evaluate_counterfactual_case(
        resume=sample_resume,
        target_job=mock_pool[0],
        job_pool=mock_pool,
        suggested_skills=["Python", "FastAPI"],  # Both already present!
        n_control_draws=5,
    )

    assert res["is_valid"] is False
    assert res["exclusion_reason"] == "all_target_skills_already_present"
    assert len(res["individual_evaluations"]) == 0


def test_counterfactual_evaluates_individual_and_combinations(mock_pool, sample_resume):
    """Counterfactual evaluation tests individual skills as well as combinations."""
    sbert = SbertRanker()
    hybrid = HybridRanker(sbert_ranker=sbert, weights={"bm25": 0.1, "sbert": 0.1, "overlap": 0.8})
    tester = CounterfactualTester(hybrid_ranker=hybrid, sbert_ranker=sbert, seed=42)

    res = tester.evaluate_counterfactual_case(
        resume=sample_resume,
        target_job=mock_pool[0],
        job_pool=mock_pool,
        suggested_skills=["Docker", "Kubernetes"],
        n_control_draws=5,
        evaluate_individual=True,
        evaluate_combinations=True,
    )

    assert res["is_valid"] is True
    # Individual: Docker, Kubernetes
    assert len(res["individual_evaluations"]) == 2
    # Combination: Docker + Kubernetes
    assert len(res["combination_evaluations"]) == 1
    assert res["combination_evaluations"][0]["skills_combo"] == ["Docker", "Kubernetes"]

    # Verify lift over control is recorded
    combo = res["combination_evaluations"][0]
    assert "lift_over_control_score" in combo
    assert "lift_over_control_rank" in combo


def test_counterfactual_aggregation_and_disclaimer(mock_pool, sample_resume):
    """Aggregate statistics must include valid/excluded counts, paired lifts, and disclaimer."""
    sbert = SbertRanker()
    hybrid = HybridRanker(sbert_ranker=sbert, weights={"bm25": 0.1, "sbert": 0.1, "overlap": 0.8})
    tester = CounterfactualTester(hybrid_ranker=hybrid, sbert_ranker=sbert, seed=42)

    c1 = tester.evaluate_counterfactual_case(
        resume=sample_resume,
        target_job=mock_pool[0],
        job_pool=mock_pool,
        suggested_skills=["Docker"],
        n_control_draws=5,
    )
    c2 = tester.evaluate_counterfactual_case(
        resume=sample_resume,
        target_job=mock_pool[0],
        job_pool=mock_pool,
        suggested_skills=["Python"],  # Excluded
        n_control_draws=5,
    )

    summary = CounterfactualTester.aggregate_counterfactual_evaluations([c1, c2])

    assert summary["total_cases"] == 2
    assert summary["valid_cases"] == 1
    assert summary["excluded_cases"] == 1
    assert "all_target_skills_already_present" in summary["exclusion_breakdown"]
    assert "causal_claim_disclaimer" in summary
    assert "algorithmic matcher score sensitivity" in summary["causal_claim_disclaimer"]


# ============================================================================
# 2. Fairness and Name-Swap Invariance Tests
# ============================================================================

def test_name_swap_evaluation_score_invariance(mock_pool, sample_resume):
    """
    On identical qualification inputs, substituting candidate names must not
    alter algorithmic ranking scores or recommendations.
    """
    sbert = SbertRanker()
    hybrid = HybridRanker(sbert_ranker=sbert, weights={"bm25": 0.1, "sbert": 0.1, "overlap": 0.8})

    evaluator = NameSwapFairnessEvaluator(
        ranker=hybrid,
        synthetic_names=["Alice Smith", "Bob Jones", "Carlos Gomez", "Fatima Al-Mansoor"],
        seed=42,
    )

    report = evaluator.evaluate_profile(
        base_resume=sample_resume,
        job_pool=mock_pool,
    )

    assert report["pairwise_comparisons"] == 6  # 4 choose 2 = 6
    assert report["score_invariance_rate"] == 1.0
    assert report["max_abs_score_difference"] < 1e-4
    assert report["mean_rank_displacement"] == 0.0
    assert report["mean_top5_jaccard_similarity"] == 1.0


def test_name_swap_batch_evaluation_and_limitations(mock_pool, sample_resume):
    """Batch fairness evaluation must document methodology and distinctions from demographic audits."""
    sbert = SbertRanker()
    hybrid = HybridRanker(sbert_ranker=sbert, weights={"bm25": 0.1, "sbert": 0.1, "overlap": 0.8})

    evaluator = NameSwapFairnessEvaluator(
        ranker=hybrid,
        synthetic_names=["Name 1", "Name 2", "Name 3"],
    )

    batch_report = evaluator.evaluate_profiles_batch(
        resumes=[sample_resume],
        job_pool=mock_pool,
    )

    assert batch_report["total_profiles_evaluated"] == 1
    assert "methodology_and_limitations" in batch_report
    lims = batch_report["methodology_and_limitations"]
    assert "does not infer real demographic traits" in lims["distinction"]


# ============================================================================
# 3. Performance, Latency, Token & Cost Measurement Tests
# ============================================================================

def test_latency_aggregation_and_percentiles():
    """Performance tracker accurately computes mean, median, and percentiles."""
    tracker = PerformanceBenchmarkTracker(provider="test_provider", model="test_model")

    latencies = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    for lat in latencies:
        tracker.record_run(total_latency_ms=lat, success=True)

    summary = tracker.compute_summary()
    lat_summary = summary["latency_summary_ms"]

    assert summary["total_runs"] == 10
    assert summary["error_rate"] == 0.0
    assert lat_summary["mean_ms"] == 55.0
    assert lat_summary["median_ms"] == 55.0
    assert lat_summary["min_ms"] == 10.0
    assert lat_summary["max_ms"] == 100.0
    assert lat_summary["p95_ms"] == 95.5 or lat_summary["p95_ms"] >= 90.0


def test_token_and_cost_calculation():
    """Cost calculations accurately use the pricing model and handle missing values honestly."""
    # Gemini 2.0 Flash pricing: $0.10/M in, $0.40/M out
    # 100,000 prompt tokens = 0.01 USD
    # 50,000 completion tokens = 0.02 USD
    # Total = 0.03 USD
    cost = calculate_token_cost("gemini-2.0-flash", prompt_tokens=100_000, completion_tokens=50_000)
    assert cost == 0.03

    # Local Ollama must be 0.0 USD
    cost_ollama = calculate_token_cost("ollama/llama3.2:3b", prompt_tokens=5000, completion_tokens=1000)
    assert cost_ollama == 0.0

    # Missing token metadata must return None (not falsely 0.0 USD for commercial APIs!)
    cost_missing = calculate_token_cost("gpt-4o", prompt_tokens=None, completion_tokens=None)
    assert cost_missing is None


def test_stage_timer_tracks_discrete_stages():
    """StageTimer accurately records named stages."""
    timer = StageTimer()
    with timer.time_stage("data_prep"):
        x = sum(range(1000))
    with timer.time_stage("scoring"):
        y = sum(range(2000))

    assert "data_prep" in timer.stage_durations_ms
    assert "scoring" in timer.stage_durations_ms
    assert timer.stage_durations_ms["data_prep"] >= 0.0
    assert timer.stage_durations_ms["scoring"] >= 0.0


# ============================================================================
# 4. Safeguards & Frozen Weights Preservation Tests
# ============================================================================

def test_frozen_ranking_weights_unaltered():
    """
    Verify ranking weights in app/ranking/config.json remain frozen
    at BM25: 0.10, SBERT: 0.10, overlap: 0.80.
    """
    cfg_file = Path("app/ranking/config.json")
    assert cfg_file.exists(), "app/ranking/config.json must exist"

    with open(cfg_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("status") == "frozen"
    weights = data.get("weights", {})
    assert weights.get("bm25") == 0.10
    assert weights.get("sbert") == 0.10
    assert weights.get("overlap") == 0.80
