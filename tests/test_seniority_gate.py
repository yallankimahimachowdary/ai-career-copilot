"""Unit tests for R9-2: Deterministic Seniority Gate & Boundary Rules.

Tests:
1. Job seniority classifier (intern, junior, mid, senior, lead)
2. Candidate seniority classifier from experience and past titles
3. Seniority compatibility rules & boundary cases (Engineer II)
4. Ranking on snapshot with gate ON: excludes incompatible roles
5. Ranking on snapshot with gate OFF: restores all roles
6. Provenance / run logging of SENIORITY_GATE flag
"""

import logging
import pytest
from app.core.config import settings
from app.core.seniority import (
    FineSeniority,
    classify_candidate_seniority,
    classify_job_seniority,
    is_seniority_compatible,
)
from scripts.job_snapshot import run_matching_on_snapshot


def test_job_seniority_classification_and_boundary():
    # Intern / Trainee
    assert classify_job_seniority("Intern Data Scientist") == FineSeniority.INTERN.value
    assert classify_job_seniority("Graduate Trainee Engineer") == FineSeniority.INTERN.value

    # Junior / Entry / Level I
    assert classify_job_seniority("Junior Software Engineer") == FineSeniority.JUNIOR.value
    assert classify_job_seniority("Entry-Level Python Developer") == FineSeniority.JUNIOR.value
    assert classify_job_seniority("Software Engineer I") == FineSeniority.JUNIOR.value

    # Boundary Case: Engineer II / Level II is strictly MID
    assert classify_job_seniority("Engineer II") == FineSeniority.MID.value
    assert classify_job_seniority("Software Engineer II") == FineSeniority.MID.value
    assert classify_job_seniority("Data Analyst Level 2") == FineSeniority.MID.value

    # Senior / Level III+
    assert classify_job_seniority("Senior Software Engineer") == FineSeniority.SENIOR.value
    assert classify_job_seniority("Sr. Backend Engineer") == FineSeniority.SENIOR.value
    assert classify_job_seniority("Software Engineer III") == FineSeniority.SENIOR.value

    # Lead / Principal / Executive
    assert classify_job_seniority("Lead Systems Architect") == FineSeniority.LEAD.value
    assert classify_job_seniority("Principal Cloud Engineer") == FineSeniority.LEAD.value
    assert classify_job_seniority("Director of Engineering") == FineSeniority.LEAD.value


def test_candidate_seniority_classification():
    # Junior candidate
    junior_resume = {
        "candidate_name": "Junior Dev",
        "level": "junior",
        "years_of_experience": 0.5,
        "experience": [{"title": "Junior Python Intern", "company": "Acme"}],
    }
    assert classify_candidate_seniority(junior_resume) == FineSeniority.JUNIOR.value

    # Senior candidate
    senior_resume = {
        "candidate_name": "Senior Dev",
        "level": "senior",
        "years_of_experience": 6.5,
        "experience": [{"title": "Senior Software Engineer", "company": "TechCorp"}],
    }
    assert classify_candidate_seniority(senior_resume) == FineSeniority.SENIOR.value

    # Mid candidate (e.g. Engineer II)
    mid_resume = {
        "candidate_name": "Mid Dev",
        "years_of_experience": 3.0,
        "experience": [{"title": "Software Engineer II", "company": "MidCorp"}],
    }
    assert classify_candidate_seniority(mid_resume) == FineSeniority.MID.value


def test_seniority_compatibility_logic():
    # Junior cannot match Senior or Lead
    assert not is_seniority_compatible(FineSeniority.JUNIOR.value, FineSeniority.SENIOR.value)
    assert not is_seniority_compatible(FineSeniority.JUNIOR.value, FineSeniority.LEAD.value)
    assert not is_seniority_compatible(FineSeniority.INTERN.value, FineSeniority.SENIOR.value)

    # Junior CAN match Junior, Intern, and Mid (boundary case like Engineer II)
    assert is_seniority_compatible(FineSeniority.JUNIOR.value, FineSeniority.JUNIOR.value)
    assert is_seniority_compatible(FineSeniority.JUNIOR.value, FineSeniority.INTERN.value)
    assert is_seniority_compatible(FineSeniority.JUNIOR.value, FineSeniority.MID.value)

    # Senior cannot match Junior or Intern
    assert not is_seniority_compatible(FineSeniority.SENIOR.value, FineSeniority.JUNIOR.value)
    assert not is_seniority_compatible(FineSeniority.SENIOR.value, FineSeniority.INTERN.value)

    # Senior CAN match Senior, Lead, and Mid
    assert is_seniority_compatible(FineSeniority.SENIOR.value, FineSeniority.SENIOR.value)
    assert is_seniority_compatible(FineSeniority.SENIOR.value, FineSeniority.LEAD.value)
    assert is_seniority_compatible(FineSeniority.SENIOR.value, FineSeniority.MID.value)


def test_ranking_seniority_gate_excludes_senior_for_junior_and_restores_when_off(caplog):
    snapshot_records = [
        {
            "id": "job_sr",
            "title": "Senior Software Engineer",
            "description": "Looking for senior Python expert with FastAPI and Docker.",
            "skills": ["Python", "FastAPI", "Docker"],
            "embedding": [0.1] * 384,
        },
        {
            "id": "job_mid",
            "title": "Software Engineer II",
            "description": "Mid-level role requiring Python, FastAPI, and Git.",
            "skills": ["Python", "FastAPI", "Git"],
            "embedding": [0.1] * 384,
        },
        {
            "id": "job_jr",
            "title": "Junior Python Developer",
            "description": "Entry-level position for learning Python and Git.",
            "skills": ["Python", "Git"],
            "embedding": [0.1] * 384,
        },
    ]

    junior_resume = {
        "candidate_name": "Test Junior",
        "level": "junior",
        "years_of_experience": 0.5,
        "skills": ["Python", "FastAPI", "Git", "Docker"],
        "summary": "Recent graduate seeking junior developer role.",
    }
    dummy_emb = [0.1] * 384

    # 1. Gate ON (explicitly or via default)
    with caplog.at_level(logging.INFO):
        matches_gate_on = run_matching_on_snapshot(
            snapshot_records=snapshot_records,
            resume_parsed_data=junior_resume,
            resume_embedding=dummy_emb,
            top_k=10,
            seniority_gate=True,
        )

    matched_ids_on = [m["job_id"] for m in matches_gate_on]
    # Senior role MUST be excluded for junior candidate
    assert "job_sr" not in matched_ids_on
    # Junior role and Mid boundary role (Engineer II) MUST be included
    assert "job_jr" in matched_ids_on
    assert "job_mid" in matched_ids_on
    # Verify flag value was logged
    assert any("[Ranking Snapshot] Seniority gate: True" in r.message for r in caplog.records)

    # 2. Gate OFF: restores old behavior (senior job included)
    caplog.clear()
    with caplog.at_level(logging.INFO):
        matches_gate_off = run_matching_on_snapshot(
            snapshot_records=snapshot_records,
            resume_parsed_data=junior_resume,
            resume_embedding=dummy_emb,
            top_k=10,
            seniority_gate=False,
        )

    matched_ids_off = [m["job_id"] for m in matches_gate_off]
    # Gate off restores Senior role
    assert "job_sr" in matched_ids_off
    assert "job_jr" in matched_ids_off
    assert "job_mid" in matched_ids_off
    assert any("[Ranking Snapshot] Seniority gate: False" in r.message for r in caplog.records)
