import pytest
from app.core.config import settings
from app.schemas.matcher import FeatureBreakdown, SkillsBreakdown
from app.services.matcher_service import CompositeScorer, FeatureExtractor, XGBoostExplainer


def test_extract_candidate_years():
    """Test candidate work experience duration calculation."""
    # 2 years + 3 years = 5 years
    parsed_resume = {
        "experience": [
            {"title": "Dev 1", "start_date": "2018", "end_date": "2020"},
            {"title": "Dev 2", "start_date": "2020", "end_date": "2023"},
        ]
    }
    years = FeatureExtractor.extract_candidate_years(parsed_resume)
    assert years == 5.0

    # No experience entries
    assert FeatureExtractor.extract_candidate_years({}) == 0.0


def test_extract_job_required_years():
    """Test required years extraction from text and title defaults."""
    # Explicit text requirement
    desc = "We are looking for a Senior Engineer with 5+ years of experience in Python."
    years = FeatureExtractor.extract_job_required_years(desc, "Backend Engineer")
    assert years == 5.0

    # Range requirement
    desc_range = "Candidates should possess 3-5 years of industry experience."
    years_range = FeatureExtractor.extract_job_required_years(desc_range, "Software Engineer")
    assert years_range == 3.0

    # Fallback to Senior title default
    years_title = FeatureExtractor.extract_job_required_years("Build great software.", "Senior Cloud Engineer")
    assert years_title == 5.0

    # Fallback to Junior title default
    years_jr = FeatureExtractor.extract_job_required_years("Learn and grow.", "Junior Developer")
    assert years_jr == 1.0


def test_classify_job_skills():
    """Test partitioning of skills into must-have vs nice-to-have."""
    skills = ["Python", "FastAPI", "Docker", "PostgreSQL", "Kubernetes"]
    # Heuristic split (first 60% = 3 skills must-have, rest nice-to-have)
    must, nice = FeatureExtractor.classify_job_skills("General description without sections.", skills)
    assert len(must) == 3
    assert len(nice) == 2
    assert must == ["Python", "FastAPI", "Docker"]
    assert nice == ["PostgreSQL", "Kubernetes"]


def test_composite_scorer_penalty_threshold():
    """Test that experience penalty is applied ONLY when deficit exceeds threshold."""
    threshold = settings.EXPERIENCE_PENALTY_THRESHOLD  # 1.5 years

    # Case 1: Deficit within threshold (e.g. 1.0 year deficit <= 1.5)
    f_no_penalty = FeatureBreakdown(
        semantic_similarity=0.8,
        must_have_skill_match=1.0,
        nice_to_have_skill_match=1.0,
        candidate_years_experience=4.0,
        job_required_years=5.0,
        experience_deficit=1.0,
        experience_penalty=0.0,
        education_level_match=1.0,
        title_similarity=0.8,
    )
    score_no_penalty = CompositeScorer.calculate_score(f_no_penalty)

    # Case 2: Deficit exceeds threshold (e.g. 4.0 years deficit > 1.5)
    penalty_amount = (4.0 - threshold) * settings.EXPERIENCE_PENALTY_FACTOR
    f_penalty = FeatureBreakdown(
        semantic_similarity=0.8,
        must_have_skill_match=1.0,
        nice_to_have_skill_match=1.0,
        candidate_years_experience=1.0,
        job_required_years=5.0,
        experience_deficit=4.0,
        experience_penalty=penalty_amount,
        education_level_match=1.0,
        title_similarity=0.8,
    )
    score_penalty = CompositeScorer.calculate_score(f_penalty)

    assert f_penalty.experience_penalty > 0.0
    assert score_no_penalty > score_penalty
    assert 0.0 <= score_penalty <= 1.0


def test_xgboost_and_shap_explainer():
    """Test XGBoost model initialization, prediction, and SHAP explanation generation."""
    explainer = XGBoostExplainer()

    features = FeatureBreakdown(
        semantic_similarity=0.85,
        must_have_skill_match=0.90,
        nice_to_have_skill_match=0.70,
        candidate_years_experience=5.0,
        job_required_years=4.0,
        experience_deficit=0.0,
        experience_penalty=0.0,
        education_level_match=1.0,
        title_similarity=0.80,
    )
    skills = SkillsBreakdown(
        matched_skills=["Python", "FastAPI", "SQL"],
        missing_must_have=[],
        missing_nice_to_have=["AWS"],
    )

    score, explanations = explainer.predict_and_explain(features, skills)

    # Validate predicted score
    assert 0.0 <= score <= 1.0

    # Validate explanations
    assert len(explanations) == len(XGBoostExplainer.FEATURE_NAMES)
    for exp in explanations:
        assert exp.feature_name in XGBoostExplainer.FEATURE_NAMES
        assert isinstance(exp.shap_value, float)
        assert "%" in exp.impact
        assert len(exp.description) > 5

    # Check that explanations are sorted by absolute impact
    abs_values = [abs(e.shap_value) for e in explanations]
    assert abs_values == sorted(abs_values, reverse=True)
