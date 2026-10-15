"""Unit tests for ClaimVerifier (Phase B5).

Covers:
1. Perfect explanation verification
2. Matched-skill errors (candidate does not possess claimed matched skill)
3. Missing-skill errors (job does not require claimed missing skill)
4. Missing-skill errors (candidate actually has the skill, so it is not missing)
5. Reason errors (reason cites an unverified/hallucinated skill)
6. Multiple simultaneous error combinations
7. Boundary conditions (empty claims, verify_all aggregation)
"""

import pytest
from app.ranking.claim_verifier import ClaimVerifier, ExplanationVerification


@pytest.fixture
def verifier():
    return ClaimVerifier()


def test_claim_verifier_perfect_explanation(verifier):
    """All matched skills exist in resume, missing skill is required by job and absent from resume."""
    resume = {
        "skills": ["Python", "SQL", "Docker"],
        "summary": "Experienced Python engineer with SQL and Docker background.",
    }
    job = {
        "title": "Backend Engineer",
        "description": "Requires Python, SQL, and AWS. Docker is a plus.",
        "skills": ["Python", "SQL", "AWS", "Docker"],
    }
    explanation = {
        "job_id": "job_1",
        "rank": 1,
        "matched_skills": ["Python", "SQL", "Docker"],
        "missing_skills": ["AWS"],
        "reason": "Strong match with Python and Docker background. Missing AWS cloud experience.",
    }

    res = verifier.verify_explanation(explanation, resume, job)
    assert res.faithfulness_score == 1.0
    assert len(res.invalid_matched) == 0
    assert len(res.invalid_missing) == 0
    assert len(res.unsupported_reason_skills) == 0


def test_claim_verifier_matched_skill_error(verifier):
    """Claiming a matched skill that is absent from candidate resume must be flagged as invalid_matched."""
    resume = {
        "skills": ["Python"],
        "summary": "Python backend developer.",
    }
    job = {
        "title": "Python Developer",
        "description": "Looking for Python, Kubernetes, and Golang.",
        "skills": ["Python", "Kubernetes", "Golang"],
    }
    explanation = {
        "job_id": "job_matched_err",
        "rank": 1,
        "matched_skills": ["Python", "Kubernetes"],  # Candidate lacks Kubernetes!
        "missing_skills": ["Golang"],
        "reason": "Strong Python candidate but needs Golang.",
    }

    res = verifier.verify_explanation(explanation, resume, job)
    assert "Kubernetes" in res.invalid_matched
    assert "Python" in res.valid_matched
    assert res.faithfulness_score < 1.0


def test_claim_verifier_missing_skill_not_required_by_job(verifier):
    """Claiming a missing skill that the job never required must be flagged as invalid_missing."""
    resume = {
        "skills": ["Python", "Django"],
        "summary": "Python and Django developer.",
    }
    job = {
        "title": "Backend Developer",
        "description": "Seeking Python and PostgreSQL experience.",
        "skills": ["Python", "PostgreSQL"],
    }
    explanation = {
        "job_id": "job_miss_err1",
        "rank": 1,
        "matched_skills": ["Python"],
        "missing_skills": ["Rust"],  # Job never asked for Rust!
        "reason": "Good Python foundation but lacks Rust systems programming.",
    }

    res = verifier.verify_explanation(explanation, resume, job)
    assert "Rust" in res.invalid_missing
    assert len(res.valid_missing) == 0
    assert res.faithfulness_score < 1.0


def test_claim_verifier_missing_skill_candidate_already_has(verifier):
    """Claiming a skill is missing when candidate already has it on resume must be flagged as invalid_missing."""
    resume = {
        "skills": ["Python", "Docker", "AWS"],
        "summary": "Cloud engineer with Python, Docker, and AWS skills.",
    }
    job = {
        "title": "Cloud Engineer",
        "description": "Requires Docker and AWS.",
        "skills": ["Docker", "AWS"],
    }
    explanation = {
        "job_id": "job_miss_err2",
        "rank": 1,
        "matched_skills": ["Docker"],
        "missing_skills": ["AWS"],  # Candidate already HAS AWS!
        "reason": "Docker developer missing AWS experience.",
    }

    res = verifier.verify_explanation(explanation, resume, job)
    assert "AWS" in res.invalid_missing
    assert len(res.valid_missing) == 0
    assert res.faithfulness_score < 1.0


def test_claim_verifier_reason_unsupported_skills(verifier):
    """Reason text citing skills neither verified as matched nor missing must be flagged."""
    resume = {
        "skills": ["Python"],
        "summary": "Python developer.",
    }
    job = {
        "title": "Software Engineer",
        "description": "Python web backend role.",
        "skills": ["Python"],
    }
    explanation = {
        "job_id": "job_reason_err",
        "rank": 1,
        "matched_skills": ["Python"],
        "missing_skills": [],
        "reason": "Candidate has extensive React and GraphQL frontend architecture experience.",
    }

    res = verifier.verify_explanation(explanation, resume, job)
    unsupported = [s.lower() for s in res.unsupported_reason_skills]
    assert any("react" in s for s in unsupported)
    assert res.faithfulness_score < 1.0


def test_claim_verifier_multiple_simultaneous_errors(verifier):
    """Simultaneous errors across matched, missing, and reason text must be cleanly detected."""
    resume = {
        "skills": ["Python"],
        "summary": "Python developer.",
    }
    job = {
        "title": "Data Engineer",
        "description": "Python, Spark, and SQL role.",
        "skills": ["Python", "Spark", "SQL"],
    }
    explanation = {
        "job_id": "job_multi_err",
        "rank": 1,
        "matched_skills": ["Python", "Kubernetes"],  # Invalid matched
        "missing_skills": ["Cobol"],  # Invalid missing (not in job)
        "reason": "Shows strong Kafka streaming architecture and Python skills.",  # Kafka unsupported
    }

    res = verifier.verify_explanation(explanation, resume, job)
    assert "Kubernetes" in res.invalid_matched
    assert "Cobol" in res.invalid_missing
    unsupported = [s.lower() for s in res.unsupported_reason_skills]
    assert any("kafka" in s for s in unsupported)
    assert res.faithfulness_score < 0.60


def test_claim_verifier_verify_all_aggregation(verifier):
    """verify_all must aggregate multiple explanations and compute mean faithfulness score."""
    resume = {"skills": ["Python", "SQL"]}
    job1 = {"id": "j1", "title": "SE", "skills": ["Python"], "description": "Python"}
    job2 = {"id": "j2", "title": "DE", "skills": ["Python", "Java"], "description": "Python and Java"}

    exps = [
        {"job_id": "j1", "rank": 1, "matched_skills": ["Python"], "missing_skills": [], "reason": "Python match."},
        {"job_id": "j2", "rank": 2, "matched_skills": ["Python", "Go"], "missing_skills": [], "reason": "Go match."},
    ]
    jobs_map = {"j1": job1, "j2": job2}

    verifications, mean_score = verifier.verify_all(exps, resume, jobs_map)
    assert len(verifications) == 2
    assert verifications[0].faithfulness_score == 1.0
    assert verifications[1].faithfulness_score < 1.0
    assert 0.0 < mean_score < 1.0
