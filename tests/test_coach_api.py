"""Integration tests for Coach API endpoints - Sprint 5."""

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app
from app.schemas.coach import (
    AnswerEvaluationResponse,
    FullCoachingSessionResponse,
    InterviewQuestion,
    QuestionBank,
    SkillGapItem,
    SkillGapReport,
)


# ---------------------------------------------------------------------------
# Shared mock fixtures
# ---------------------------------------------------------------------------

def _mock_resume():
    r = MagicMock()
    r.id = "res-abc"
    r.candidate_name = "Jane Doe"
    r.parsed_data = {
        "contact_info": {"name": "Jane Doe"},
        "skills": ["Python", "JavaScript", "SQL", "React"],
        "projects": [
            {"name": "Portfolio App", "description": "Portfolio", "technologies": ["React", "Python"]}
        ],
        "experience": [],
        "education": [{"institution": "MIT", "degree": "B.S.", "field_of_study": "CS"}],
    }
    return r


def _mock_job():
    j = MagicMock()
    j.id = "job-xyz"
    j.title = "Software Engineer"
    j.company_name = "Acme Corp"
    j.description = "Requires Python, JavaScript, SQL, and React experience. Docker is a plus."
    j.skills_desc = ""
    return j


def _mock_gap_report():
    return SkillGapReport(
        resume_id="res-abc",
        job_id="job-xyz",
        job_title="Software Engineer",
        company_name="Acme Corp",
        candidate_name="Jane Doe",
        overall_readiness_score=72.5,
        confirmed_strengths=["Python", "JavaScript", "SQL", "React"],
        critical_gaps=[
            SkillGapItem(
                skill="Docker",
                category="DevOps / Cloud",
                importance="high",
                candidate_has=False,
                recommendation="Study Docker via official docs and build a containerized project.",
            )
        ],
        growth_gaps=[],
        executive_summary="Jane is a strong match with 4 confirmed skills. Docker is the main gap.",
        learning_roadmap=["Learn Docker fundamentals via official docs."],
    )


def _mock_question_bank():
    return QuestionBank(
        resume_id="res-abc",
        job_id="job-xyz",
        job_title="Software Engineer",
        candidate_name="Jane Doe",
        technical_questions=[
            InterviewQuestion(
                id="TQ-001",
                category="technical",
                difficulty="junior",
                target_skill="Python",
                question="Explain list vs generator in Python.",
                why_asked="Tests Python depth.",
                sample_answer="Generators are lazy; lists are eager.",
                evaluation_criteria=["Correct", "Example given"],
            )
        ],
        behavioral_questions=[
            InterviewQuestion(
                id="BQ-001",
                category="behavioral",
                difficulty="junior",
                target_skill="Communication & Teamwork",
                question="Tell me about a project you are proud of.",
                why_asked="Assesses communication.",
                sample_answer="Use STAR method.",
                evaluation_criteria=["Situation", "Task", "Action", "Result"],
            )
        ],
        gap_questions=[
            InterviewQuestion(
                id="GQ-001",
                category="gap_probing",
                difficulty="junior",
                target_skill="Docker",
                question="Docker is required. How would you get up to speed?",
                why_asked="Probes gap.",
                sample_answer="Be honest and show a plan.",
                evaluation_criteria=["Honesty", "Plan"],
            )
        ],
        preparation_tips=["Research the company.", "Practice STAR stories."],
    )


def _mock_eval_response():
    return AnswerEvaluationResponse(
        score=7.5,
        grade="good",
        strengths=["Good depth", "Mentioned Python"],
        weaknesses=["Add more specifics"],
        improved_answer="A stronger answer would include concrete metrics.",
        rubric_breakdown={"depth": 7.0, "structure": 8.0, "technical_accuracy": 7.0, "specificity": 6.0},
    )


# ---------------------------------------------------------------------------
# /coach/skill-gap tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_skill_gap_returns_200():
    mock_resume = _mock_resume()
    mock_job = _mock_job()
    mock_report = _mock_gap_report()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with (
            patch("app.api.v1.endpoints.coach._get_resume_and_job", new_callable=AsyncMock) as mock_fetch,
            patch("app.api.v1.endpoints.coach.coach_agent.generate_skill_gap_report", new_callable=AsyncMock) as mock_gap,
        ):
            mock_fetch.return_value = (mock_resume, mock_job)
            mock_gap.return_value = mock_report
            response = await client.post(
                "/api/v1/coach/skill-gap",
                json={"resume_id": "res-abc", "job_id": "job-xyz"},
            )
    assert response.status_code == 200
    data = response.json()
    assert data["resume_id"] == "res-abc"
    assert data["job_id"] == "job-xyz"
    assert "overall_readiness_score" in data
    assert "confirmed_strengths" in data
    assert "critical_gaps" in data
    assert "learning_roadmap" in data


@pytest.mark.asyncio
async def test_skill_gap_404_on_missing_resume():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("app.api.v1.endpoints.coach._get_resume_and_job", new_callable=AsyncMock) as mock_fetch:
            from fastapi import HTTPException
            mock_fetch.side_effect = HTTPException(status_code=404, detail="Resume not-found-id not found.")
            response = await client.post(
                "/api/v1/coach/skill-gap",
                json={"resume_id": "not-found-id", "job_id": "job-xyz"},
            )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_skill_gap_validates_request_body():
    """Missing required fields should return 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/coach/skill-gap",
            json={"resume_id": "res-abc"},  # missing job_id
        )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# /coach/question-bank tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_question_bank_returns_200():
    mock_resume = _mock_resume()
    mock_job = _mock_job()
    mock_report = _mock_gap_report()
    mock_bank = _mock_question_bank()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with (
            patch("app.api.v1.endpoints.coach._get_resume_and_job", new_callable=AsyncMock) as mock_fetch,
            patch("app.api.v1.endpoints.coach.coach_agent.generate_skill_gap_report", new_callable=AsyncMock) as mock_gap,
            patch("app.api.v1.endpoints.coach.coach_agent.generate_question_bank", new_callable=AsyncMock) as mock_qb,
        ):
            mock_fetch.return_value = (mock_resume, mock_job)
            mock_gap.return_value = mock_report
            mock_qb.return_value = mock_bank
            response = await client.post(
                "/api/v1/coach/question-bank",
                json={"resume_id": "res-abc", "job_id": "job-xyz"},
            )
    assert response.status_code == 200
    data = response.json()
    assert len(data["technical_questions"]) > 0
    assert len(data["behavioral_questions"]) > 0
    assert len(data["gap_questions"]) > 0
    assert len(data["preparation_tips"]) > 0


@pytest.mark.asyncio
async def test_question_bank_respects_max_counts():
    mock_resume = _mock_resume()
    mock_job = _mock_job()
    mock_report = _mock_gap_report()
    mock_bank = _mock_question_bank()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with (
            patch("app.api.v1.endpoints.coach._get_resume_and_job", new_callable=AsyncMock) as mock_fetch,
            patch("app.api.v1.endpoints.coach.coach_agent.generate_skill_gap_report", new_callable=AsyncMock) as mock_gap,
            patch("app.api.v1.endpoints.coach.coach_agent.generate_question_bank", new_callable=AsyncMock) as mock_qb,
        ):
            mock_fetch.return_value = (mock_resume, mock_job)
            mock_gap.return_value = mock_report
            mock_qb.return_value = mock_bank
            response = await client.post(
                "/api/v1/coach/question-bank",
                json={"resume_id": "res-abc", "job_id": "job-xyz", "max_technical": 3, "max_behavioral": 2, "max_gap": 1},
            )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# /coach/evaluate-answer tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_evaluate_answer_returns_200():
    mock_eval = _mock_eval_response()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch(
            "app.api.v1.endpoints.coach.coach_agent.evaluate_candidate_answer",
            new_callable=AsyncMock,
        ) as mock_eval_fn:
            mock_eval_fn.return_value = mock_eval
            response = await client.post(
                "/api/v1/coach/evaluate-answer",
                json={
                    "question_text": "Explain Python generators.",
                    "target_skill": "Python",
                    "job_context": "Backend Engineer at Acme Corp",
                    "candidate_answer": "Generators yield values lazily, reducing memory usage.",
                },
            )
    assert response.status_code == 200
    data = response.json()
    assert "score" in data
    assert "grade" in data
    assert data["grade"] in ("excellent", "good", "needs_improvement", "poor")
    assert "strengths" in data
    assert "weaknesses" in data
    assert "improved_answer" in data
    assert "rubric_breakdown" in data


@pytest.mark.asyncio
async def test_evaluate_answer_validates_missing_fields():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/coach/evaluate-answer",
            json={"question_text": "Test?"},  # missing target_skill, job_context, candidate_answer
        )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# /coach/session tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_session_returns_200():
    mock_resume = _mock_resume()
    mock_job = _mock_job()
    mock_session = FullCoachingSessionResponse(
        resume_id="res-abc",
        job_id="job-xyz",
        skill_gap_report=_mock_gap_report(),
        question_bank=_mock_question_bank(),
        overall_readiness_score=72.5,
        top_preparation_priorities=["Learn Docker."],
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with (
            patch("app.api.v1.endpoints.coach._get_resume_and_job", new_callable=AsyncMock) as mock_fetch,
            patch("app.api.v1.endpoints.coach.coach_agent.run_full_session", new_callable=AsyncMock) as mock_session_fn,
        ):
            mock_fetch.return_value = (mock_resume, mock_job)
            mock_session_fn.return_value = mock_session
            response = await client.post(
                "/api/v1/coach/session",
                json={"resume_id": "res-abc", "job_id": "job-xyz"},
            )
    assert response.status_code == 200
    data = response.json()
    assert data["resume_id"] == "res-abc"
    assert data["job_id"] == "job-xyz"
    assert "skill_gap_report" in data
    assert "question_bank" in data
    assert "overall_readiness_score" in data
    assert "top_preparation_priorities" in data


@pytest.mark.asyncio
async def test_full_session_404_on_missing_job():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("app.api.v1.endpoints.coach._get_resume_and_job", new_callable=AsyncMock) as mock_fetch:
            from fastapi import HTTPException
            mock_fetch.side_effect = HTTPException(status_code=404, detail="Job posting bad-job not found.")
            response = await client.post(
                "/api/v1/coach/session",
                json={"resume_id": "res-abc", "job_id": "bad-job"},
            )
    assert response.status_code == 404
