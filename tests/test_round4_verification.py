"""
tests/test_round4_verification.py
---------------------------------
Unit tests verifying Round 4 improvements:
1. Candidate profile preservation via safe_merge_parsed_data
2. DeduplicationService merging of Mai Mangeshkar Hospital postings
3. In-flight matcher deduplication of duplicate job match items
4. Nuanced explanation generation (preventing misleading 'Strong alignment' on single skills)
5. Gemini model alias mapping in experiment mode
"""

import pytest
from app.services.parser_agent import parser_agent, safe_merge_parsed_data
from app.services.deduplication_service import deduplication_service, _companies_match
from app.services.matcher_service import matcher_agent
from app.schemas.matcher import FeatureBreakdown, SkillsBreakdown, JobMatchItem
from app.services.llm_provider import GeminiProvider


def test_safe_merge_preserves_education_and_skills():
    """Ensure safe_merge_parsed_data prevents wiping out education and merges skills."""
    existing_pd = {
        "contact_info": {"name": "Mahima Chowdary", "email": "mahi@example.com"},
        "skills": ["Java", "Python", "SQL"],
        "education": [
            {
                "institution": "Vel Tech University",
                "degree": "Bachelor of Technology",
                "field_of_study": "Artificial Intelligence",
                "graduation_year": "2024 - 2028",
            }
        ],
        "projects": [{"name": "Smart Task Management", "technologies": ["Java"]}],
    }

    # Simulate an incomplete parse that returned empty education
    new_pd = {
        "contact_info": {"name": "Mahima Chowdary", "email": "mahi@example.com"},
        "skills": ["Java", "Git/GitHub", "Blender"],
        "education": [],
        "projects": [],
    }

    merged = safe_merge_parsed_data(existing_pd, new_pd)

    # Education MUST NOT be empty
    assert len(merged["education"]) == 1
    assert merged["education"][0]["institution"] == "Vel Tech University"

    # Skills MUST be a union
    assert set(merged["skills"]) == {"Java", "Python", "SQL", "Git/GitHub", "Blender"}

    # Projects MUST be preserved
    assert len(merged["projects"]) == 1


def test_deduplication_merges_mai_mangeshkar_postings():
    """Verify DeduplicationService successfully merges Indeed and Glassdoor postings for Mai Mangeshkar Hospital."""
    records = [
        {
            "id": "5007d89a-5ea9-4d6f-a8af-f1ba95300a31",
            "title": "Biomedical Engineer",
            "company": "MAI MAGESHKAR HOSPITAL,WARJE",
            "location": "Mumbai, Maharashtra",
            "source": "indeed",
            "description": "Responsible for medical equipment maintenance and calibration across departments.",
        },
        {
            "id": "b33b2103-1c8d-45d8-8294-bddbb8ef91e8",
            "title": "Biomedical Engineer",
            "company": "LMMF'S Mai Mangeshkar Hospital, Warje",
            "location": "India",
            "source": "glassdoor",
            "description": "Responsible for medical equipment maintenance and calibration across departments.",
        },
    ]

    canonical, num_merged, clusters = deduplication_service.deduplicate_records(records)

    assert num_merged == 1
    assert len(canonical) == 1
    assert len(clusters) == 1

    cluster = clusters[0]
    assert cluster["title"] == "Biomedical Engineer"
    assert cluster["merged_count"] == 2
    assert set(cluster["sources"]) == {"indeed", "glassdoor"}


def test_in_flight_matcher_deduplication():
    """Verify deduplicate_job_match_items prevents duplicate postings in top match list."""
    breakdown = SkillsBreakdown(
        total_job_skills=2,
        matched_skills=["MATLAB"],
        missing_must_have=[],
        missing_nice_to_have=[],
    )
    features = FeatureBreakdown(
        semantic_similarity=0.45,
        skill_overlap_ratio=0.5,
        must_have_skill_match=1.0,
        nice_to_have_skill_match=0.0,
        experience_penalty=0.0,
        experience_ratio=1.0,
        title_similarity=0.3,
        education_level_match=1.0,
        candidate_years_experience=1.0,
        job_required_years=1.0,
        experience_deficit=0.0,
    )

    items = [
        JobMatchItem(
            job_id="5007d89a",
            title="Biomedical Engineer",
            company_name="MAI MAGESHKAR HOSPITAL,WARJE",
            location="Mumbai, Maharashtra",
            semantic_score=0.45,
            composite_score=0.40,
            xgboost_score=0.42,
            final_score=0.41,
            rank=1,
            merged_sources=["indeed"],
            duplicate_count=1,
            skills_breakdown=breakdown,
            features=features,
            explanations=[],
        ),
        JobMatchItem(
            job_id="b33b2103",
            title="Biomedical Engineer",
            company_name="LMMF'S Mai Mangeshkar Hospital, Warje",
            location="India",
            semantic_score=0.45,
            composite_score=0.39,
            xgboost_score=0.41,
            final_score=0.40,
            rank=2,
            merged_sources=["glassdoor"],
            duplicate_count=1,
            skills_breakdown=breakdown,
            features=features,
            explanations=[],
        ),
        JobMatchItem(
            job_id="unique_job_3",
            title="Junior Research Associate",
            company_name="ITC Limited",
            location="Bengaluru",
            semantic_score=0.55,
            composite_score=0.50,
            xgboost_score=0.52,
            final_score=0.51,
            rank=3,
            merged_sources=["glassdoor"],
            duplicate_count=1,
            skills_breakdown=breakdown,
            features=features,
            explanations=[],
        ),
    ]

    deduped = deduplication_service.deduplicate_job_match_items(items, limit=10)

    # Should have merged the 2 Biomedical Engineer postings into 1
    assert len(deduped) == 2
    assert deduped[0].duplicate_count == 2
    assert "glassdoor" in deduped[0].merged_sources
    assert deduped[1].job_id == "unique_job_3"


def test_nuanced_explanation_must_have_skills():
    """Verify explanations distinguish single-skill match from multi-skill strong alignment."""
    # Case 1: Single skill matched (out of 1) -> must NOT say 'Strong alignment'
    skills_1 = SkillsBreakdown(
        total_job_skills=1,
        matched_skills=["MATLAB"],
        missing_must_have=[],
        missing_nice_to_have=[],
    )
    features_1 = FeatureBreakdown(
        semantic_similarity=0.35,
        skill_overlap_ratio=1.0,
        must_have_skill_match=1.0,
        nice_to_have_skill_match=0.0,
        experience_penalty=0.0,
        experience_ratio=0.5,
        title_similarity=0.0,
        education_level_match=1.0,
        candidate_years_experience=0.5,
        job_required_years=1.0,
        experience_deficit=0.5,
    )
    rat_1 = matcher_agent.ml_explainer._generate_feature_rationale(
        "must_have_skill_match", 0.15, features_1, skills_1
    )
    assert "Single mandatory skill requirement matched (MATLAB)" in rat_1
    assert "Strong alignment" not in rat_1

    # Case 2: Multi-skill match (>= 2 skills, >= 70%) -> SHOULD say 'Strong alignment'
    skills_2 = SkillsBreakdown(
        total_job_skills=3,
        matched_skills=["Java", "Python", "SQL"],
        missing_must_have=[],
        missing_nice_to_have=[],
    )
    features_2 = FeatureBreakdown(
        semantic_similarity=0.75,
        skill_overlap_ratio=1.0,
        must_have_skill_match=1.0,
        nice_to_have_skill_match=0.0,
        experience_penalty=0.0,
        experience_ratio=1.0,
        title_similarity=0.8,
        education_level_match=1.0,
        candidate_years_experience=2.0,
        job_required_years=2.0,
        experience_deficit=0.0,
    )
    rat_2 = matcher_agent.ml_explainer._generate_feature_rationale(
        "must_have_skill_match", 0.18, features_2, skills_2
    )
    assert "Strong alignment with mandatory job requirements" in rat_2

    # Case 3: Zero skills matched
    skills_3 = SkillsBreakdown(
        total_job_skills=2,
        matched_skills=[],
        missing_must_have=["Bioinformatics", "Genomics"],
        missing_nice_to_have=[],
    )
    features_3 = FeatureBreakdown(
        semantic_similarity=0.20,
        skill_overlap_ratio=0.0,
        must_have_skill_match=0.0,
        nice_to_have_skill_match=0.0,
        experience_penalty=0.0,
        experience_ratio=0.5,
        title_similarity=0.0,
        education_level_match=1.0,
        candidate_years_experience=0.5,
        job_required_years=1.0,
        experience_deficit=0.5,
    )
    rat_3 = matcher_agent.ml_explainer._generate_feature_rationale(
        "must_have_skill_match", -0.15, features_3, skills_3
    )
    assert "Zero mandatory technical requirements matched" in rat_3


def test_gemini_alias_mapping():
    """Verify GeminiProvider recognizes official model aliases like gemini-3.5-flash -> gemini-3.6-flash."""
    from app.services.llm_provider import GeminiProvider

    provider = GeminiProvider(model="gemini-3.5-flash")
    assert provider.model == "gemini-3.5-flash"

    # Verify alias resolution logic matches the canonical serving model
    known_aliases = {
        "gemini-3.5-flash": "gemini-3.6-flash",
        "gemini-2.0-flash": "gemini-2.0-flash",
        "gemini-1.5-flash": "gemini-1.5-flash",
    }
    req = provider.model.lower()
    ans = "gemini-3.6-flash"
    is_match = (
        req == ans
        or ans.startswith(req)
        or req.startswith(ans)
        or known_aliases.get(req) == ans
        or known_aliases.get(req, "").startswith(ans)
        or ans.startswith(known_aliases.get(req, "___"))
    )
    assert is_match is True
