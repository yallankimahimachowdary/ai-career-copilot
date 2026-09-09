"""Unit tests for CoachAgent service - Sprint 5."""

import pytest
from unittest.mock import MagicMock

from app.schemas.coach import (
    AnswerEvaluationRequest,
    CoachQuestionBankRequest,
    SkillGapItem,
)
from app.services.coach_service import (
    _clean,
    _compute_readiness_score,
    _extract_job_requirements,
    _extract_resume_skills,
    _rule_based_evaluate_answer,
    _rule_based_gap_report,
    _rule_based_question_bank,
    _skill_category,
    CoachAgent,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_resume(skills=None, projects=None, name="Test Candidate"):
    resume = MagicMock()
    resume.id = "test-resume-id"
    resume.candidate_name = name
    resume.parsed_data = {
        "contact_info": {"name": name},
        "skills": skills or ["Python", "JavaScript", "SQL", "HTML/CSS", "Git/GitHub"],
        "projects": projects or [
            {
                "name": "Smart Task Manager",
                "description": "A task management system built with React and FastAPI.",
                "technologies": ["React", "FastAPI", "PostgreSQL"],
            }
        ],
        "experience": [],
        "education": [
            {"institution": "Test University", "degree": "B.Tech", "field_of_study": "Computer Science"}
        ],
    }
    return resume


def _make_job(title="Software Engineer", description="", company="TestCorp"):
    job = MagicMock()
    job.id = "test-job-id"
    job.title = title
    job.company_name = company
    job.description = description or (
        "We are looking for a Software Engineer with experience in Python, JavaScript, "
        "SQL, HTML/CSS, Git/GitHub, React, and REST API development. "
        "Required: strong communication and problem-solving skills."
    )
    job.skills_desc = ""
    return job


def _make_gap_report(resume, job):
    reqs = _extract_job_requirements(job)
    return _rule_based_gap_report(resume, job, _extract_resume_skills(resume), reqs)


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

def test_clean_normalizes_skill():
    assert _clean("Python") == "python"
    assert _clean("HTML/CSS") == "html/css"


def test_skill_category_classification():
    assert _skill_category("Python") == "Language"
    assert _skill_category("React") == "Framework"
    assert _skill_category("Docker") == "DevOps / Cloud"
    assert _skill_category("Machine Learning") == "AI / Data Science"
    assert _skill_category("Git/GitHub") == "Tooling / Workflow"
    assert _skill_category("Communication") == "Soft Skill"
    assert _skill_category("SomeUnknownTool") == "Technical"


def test_compute_readiness_score_full_match():
    score = _compute_readiness_score(["Python", "SQL", "Java"], [], [])
    assert score > 80.0


def test_compute_readiness_score_all_gaps():
    gaps = [
        SkillGapItem(skill="Python", category="Language", importance="high", candidate_has=False, recommendation="Learn Python"),
        SkillGapItem(skill="SQL", category="Language", importance="high", candidate_has=False, recommendation="Learn SQL"),
    ]
    score = _compute_readiness_score([], gaps, [])
    assert score < 30.0


def test_compute_readiness_score_empty():
    score = _compute_readiness_score([], [], [])
    assert score == 70.0


def test_compute_readiness_score_clamps_to_range():
    score = _compute_readiness_score([], [], [])
    assert 5.0 <= score <= 98.0


# ---------------------------------------------------------------------------
# Resume / Job extraction tests
# ---------------------------------------------------------------------------

def test_extract_resume_skills_deduplicates():
    resume = _make_resume(
        skills=["Python", "Python", "SQL"],
        projects=[{"name": "proj", "technologies": ["SQL", "React"]}],
    )
    skills = _extract_resume_skills(resume)
    assert skills.count("Python") == 1
    assert "React" in skills


def test_extract_resume_skills_filters_category_codes():
    resume = _make_resume(skills=["Python", "IT", "HCPR", "JavaScript"])
    skills = _extract_resume_skills(resume)
    assert "IT" not in skills
    assert "HCPR" not in skills
    assert "Python" in skills


def test_extract_job_requirements_known_skills():
    job = _make_job(description="We need Python, JavaScript, and Docker expertise.")
    reqs = _extract_job_requirements(job)
    assert "Python" in reqs["must_have"]
    assert "JavaScript" in reqs["must_have"]
    assert "Docker" in reqs["must_have"]


def test_extract_job_requirements_no_category_codes():
    job = _make_job(description="Required skills: IT HCPR ENG Python")
    reqs = _extract_job_requirements(job)
    for code in ["IT", "HCPR", "ENG"]:
        assert code not in reqs["must_have"]


def test_extract_job_requirements_fallback_on_empty():
    job = _make_job(description="Looking for someone with xyzzy frameworking experience.", company="TestCo")
    reqs = _extract_job_requirements(job)
    assert isinstance(reqs["must_have"], list)


# ---------------------------------------------------------------------------
# Rule-based gap report tests
# ---------------------------------------------------------------------------

def test_rule_based_gap_report_confirmed_strengths():
    resume = _make_resume(skills=["Python", "JavaScript", "SQL"])
    job = _make_job(description="Requires Python, JavaScript, SQL, and Docker.")
    reqs = _extract_job_requirements(job)
    report = _rule_based_gap_report(resume, job, _extract_resume_skills(resume), reqs)
    assert "Python" in report.confirmed_strengths
    assert "JavaScript" in report.confirmed_strengths


def test_rule_based_gap_report_critical_gaps():
    resume = _make_resume(skills=["Python"])
    job = _make_job(description="Requires Python, React, Docker, Kubernetes.")
    reqs = _extract_job_requirements(job)
    report = _rule_based_gap_report(resume, job, _extract_resume_skills(resume), reqs)
    gap_skills = [g.skill for g in report.critical_gaps]
    assert "React" in gap_skills or "Docker" in gap_skills


def test_rule_based_gap_report_readiness_score_range():
    resume = _make_resume()
    job = _make_job()
    reqs = _extract_job_requirements(job)
    report = _rule_based_gap_report(resume, job, _extract_resume_skills(resume), reqs)
    assert 5.0 <= report.overall_readiness_score <= 98.0


def test_rule_based_gap_report_executive_summary_not_empty():
    resume = _make_resume()
    job = _make_job()
    report = _make_gap_report(resume, job)
    assert len(report.executive_summary) > 20


def test_rule_based_gap_report_learning_roadmap_not_empty():
    resume = _make_resume()
    job = _make_job()
    report = _make_gap_report(resume, job)
    assert len(report.learning_roadmap) >= 1


# ---------------------------------------------------------------------------
# Rule-based question bank tests
# ---------------------------------------------------------------------------

def test_rule_based_question_bank_technical_questions():
    resume = _make_resume(skills=["Python", "SQL", "JavaScript"])
    job = _make_job()
    gap_report = _make_gap_report(resume, job)
    req = CoachQuestionBankRequest(resume_id="test-resume-id", job_id="test-job-id")
    bank = _rule_based_question_bank(resume, job, gap_report, req)
    assert len(bank.technical_questions) > 0
    for q in bank.technical_questions:
        assert q.category == "technical"
        assert q.question
        assert q.sample_answer


def test_rule_based_question_bank_behavioral_questions():
    resume = _make_resume()
    job = _make_job()
    gap_report = _make_gap_report(resume, job)
    req = CoachQuestionBankRequest(resume_id="test-resume-id", job_id="test-job-id", max_behavioral=3)
    bank = _rule_based_question_bank(resume, job, gap_report, req)
    assert len(bank.behavioral_questions) == 3
    for q in bank.behavioral_questions:
        assert q.category == "behavioral"


def test_rule_based_question_bank_respects_max_counts():
    resume = _make_resume(skills=["Python", "SQL", "JavaScript", "React", "Docker", "AWS"])
    job = _make_job()
    gap_report = _make_gap_report(resume, job)
    req = CoachQuestionBankRequest(
        resume_id="test-resume-id",
        job_id="test-job-id",
        max_technical=2,
        max_behavioral=1,
        max_gap=1,
    )
    bank = _rule_based_question_bank(resume, job, gap_report, req)
    assert len(bank.technical_questions) <= 2
    assert len(bank.behavioral_questions) <= 1
    assert len(bank.gap_questions) <= 1


def test_rule_based_question_bank_gap_questions_from_critical_gaps():
    resume = _make_resume(skills=["Python"])
    job = _make_job(description="Requires Python, Kubernetes, and AWS.")
    gap_report = _make_gap_report(resume, job)
    req = CoachQuestionBankRequest(resume_id="test-resume-id", job_id="test-job-id", max_gap=2)
    bank = _rule_based_question_bank(resume, job, gap_report, req)
    for q in bank.gap_questions:
        assert q.category == "gap_probing"
        assert q.target_skill in [g.skill for g in gap_report.critical_gaps]


def test_rule_based_question_bank_preparation_tips():
    resume = _make_resume()
    job = _make_job()
    gap_report = _make_gap_report(resume, job)
    req = CoachQuestionBankRequest(resume_id="test-resume-id", job_id="test-job-id")
    bank = _rule_based_question_bank(resume, job, gap_report, req)
    assert len(bank.preparation_tips) >= 3


# ---------------------------------------------------------------------------
# Rule-based answer evaluation tests
# ---------------------------------------------------------------------------

def test_rule_based_evaluate_long_answer_scores_higher():
    long_answer = " ".join(["word"] * 200)
    short_answer = "Brief answer."
    req_long = AnswerEvaluationRequest(
        question_text="Tell me about yourself.",
        target_skill="Communication",
        job_context="Software Engineer",
        candidate_answer=long_answer,
    )
    req_short = AnswerEvaluationRequest(
        question_text="Tell me about yourself.",
        target_skill="Communication",
        job_context="Software Engineer",
        candidate_answer=short_answer,
    )
    result_long = _rule_based_evaluate_answer(req_long)
    result_short = _rule_based_evaluate_answer(req_short)
    assert result_long.score > result_short.score


def test_rule_based_evaluate_score_clamped():
    req = AnswerEvaluationRequest(
        question_text="Test?",
        target_skill="Python",
        job_context="Dev",
        candidate_answer=" python " * 200,
    )
    result = _rule_based_evaluate_answer(req)
    assert 0.0 <= result.score <= 10.0


def test_rule_based_evaluate_returns_improved_answer():
    req = AnswerEvaluationRequest(
        question_text="Test?",
        target_skill="SQL",
        job_context="Data Engineer",
        candidate_answer="I know SQL.",
    )
    result = _rule_based_evaluate_answer(req)
    assert len(result.improved_answer) > 20


def test_rule_based_evaluate_rubric_breakdown_keys():
    req = AnswerEvaluationRequest(
        question_text="Explain Python decorators.",
        target_skill="Python",
        job_context="Software Engineer",
        candidate_answer="Decorators wrap functions to add behavior.",
    )
    result = _rule_based_evaluate_answer(req)
    assert "depth" in result.rubric_breakdown
    assert "structure" in result.rubric_breakdown
    assert "technical_accuracy" in result.rubric_breakdown
    assert "specificity" in result.rubric_breakdown


def test_rule_based_evaluate_poor_grade_for_short_answer():
    req = AnswerEvaluationRequest(
        question_text="Test?",
        target_skill="Java",
        job_context="Backend",
        candidate_answer="I like Java.",
    )
    result = _rule_based_evaluate_answer(req)
    assert result.grade in ("poor", "needs_improvement")


# ---------------------------------------------------------------------------
# CoachAgent class tests (rule-based, no LLM)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_coach_agent_gap_report_uses_fallback_when_no_gemini():
    agent = CoachAgent()
    agent.gemini_key = None
    resume = _make_resume()
    job = _make_job()
    report = await agent.generate_skill_gap_report(resume, job)
    assert report.resume_id == "test-resume-id"
    assert report.job_id == "test-job-id"
    assert 5.0 <= report.overall_readiness_score <= 98.0
    assert report.executive_summary


@pytest.mark.asyncio
async def test_coach_agent_question_bank_uses_fallback_when_no_gemini():
    agent = CoachAgent()
    agent.gemini_key = None
    resume = _make_resume()
    job = _make_job()
    gap_report = await agent.generate_skill_gap_report(resume, job)
    req = CoachQuestionBankRequest(resume_id="test-resume-id", job_id="test-job-id")
    bank = await agent.generate_question_bank(resume, job, gap_report, req)
    assert bank.resume_id == "test-resume-id"
    assert isinstance(bank.technical_questions, list)
    assert isinstance(bank.behavioral_questions, list)


@pytest.mark.asyncio
async def test_coach_agent_evaluate_answer_uses_fallback_when_no_gemini():
    agent = CoachAgent()
    agent.gemini_key = None
    req = AnswerEvaluationRequest(
        question_text="Explain Python generators.",
        target_skill="Python",
        job_context="Backend Engineer",
        candidate_answer=(
            "Python generators use yield to produce values lazily. "
            "I used a generator in my data pipeline project to process CSV files "
            "without loading everything into memory. This reduced memory usage by 60%."
        ),
    )
    result = await agent.evaluate_candidate_answer(req)
    assert 0.0 <= result.score <= 10.0
    assert result.grade in ("excellent", "good", "needs_improvement", "poor")


@pytest.mark.asyncio
async def test_coach_agent_full_session():
    agent = CoachAgent()
    agent.gemini_key = None
    resume = _make_resume()
    job = _make_job()
    qb_req = CoachQuestionBankRequest(resume_id="test-resume-id", job_id="test-job-id")
    session = await agent.run_full_session(resume, job, qb_req)
    assert session.resume_id == "test-resume-id"
    assert session.job_id == "test-job-id"
    assert session.skill_gap_report is not None
    assert session.question_bank is not None
    assert 5.0 <= session.overall_readiness_score <= 98.0
    assert isinstance(session.top_preparation_priorities, list)


@pytest.mark.asyncio
async def test_coach_agent_gemini_failure_falls_back(monkeypatch):
    agent = CoachAgent()
    agent.gemini_key = "fake-key"

    async def fail_post(*args, **kwargs):
        raise RuntimeError("Gemini unavailable")

    monkeypatch.setattr(agent, "_gemini_post", fail_post)
    resume = _make_resume()
    job = _make_job()
    report = await agent.generate_skill_gap_report(resume, job)
    assert report.resume_id == "test-resume-id"
    assert report.overall_readiness_score >= 5.0
