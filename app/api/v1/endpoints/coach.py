"""Coach Agent API endpoints - Sprint 5."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.job_posting import JobPosting
from app.models.resume import Resume
from app.schemas.coach import (
    AnswerEvaluationRequest,
    AnswerEvaluationResponse,
    CoachQuestionBankRequest,
    CoachSkillGapRequest,
    FullCoachingSessionResponse,
    QuestionBank,
    SkillGapReport,
)
from app.services.coach_service import coach_agent

router = APIRouter()


async def _get_resume_and_job(
    resume_id: str, job_id: str, db: AsyncSession
):
    """Fetch both Resume and JobPosting from the database, raising 404 if not found."""
    resume = await db.get(Resume, resume_id)
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume {resume_id} not found.",
        )
    job = await db.get(JobPosting, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job posting {job_id} not found.",
        )
    return resume, job


@router.post(
    "/skill-gap",
    response_model=SkillGapReport,
    summary="Step 1: Generate a skill-gap diagnostic report",
    description=(
        "Compares a candidate's resume against a target job posting and produces a "
        "detailed skill-gap analysis including confirmed strengths, critical gaps, "
        "growth gaps, an executive summary, and a learning roadmap."
    ),
)
async def skill_gap(
    body: CoachSkillGapRequest,
    db: AsyncSession = Depends(get_db),
) -> SkillGapReport:
    resume, job = await _get_resume_and_job(body.resume_id, body.job_id, db)
    return await coach_agent.generate_skill_gap_report(resume, job)


@router.post(
    "/question-bank",
    response_model=QuestionBank,
    summary="Step 2: Generate a curated interview question bank",
    description=(
        "Generates tailored technical questions (on matched skills), STAR behavioral "
        "questions grounded in the candidate's real projects, and gap-probing questions "
        "on missing skills."
    ),
)
async def question_bank(
    body: CoachQuestionBankRequest,
    db: AsyncSession = Depends(get_db),
) -> QuestionBank:
    resume, job = await _get_resume_and_job(body.resume_id, body.job_id, db)
    gap_report = await coach_agent.generate_skill_gap_report(resume, job)
    return await coach_agent.generate_question_bank(resume, job, gap_report, body)


@router.post(
    "/evaluate-answer",
    response_model=AnswerEvaluationResponse,
    summary="Step 3: Evaluate a practice interview answer",
    description=(
        "Evaluates a candidate's practice answer using rubric-based scoring. "
        "Returns a score, grade, strengths, weaknesses, and an improved model answer."
    ),
)
async def evaluate_answer(
    body: AnswerEvaluationRequest,
) -> AnswerEvaluationResponse:
    return await coach_agent.evaluate_candidate_answer(body)


@router.post(
    "/session",
    response_model=FullCoachingSessionResponse,
    summary="Full coaching session (all 3 steps combined)",
    description=(
        "Runs the complete coaching pipeline in one call: skill-gap diagnostic (Step 1) "
        "and curated question bank (Step 2). Returns a unified coaching session object "
        "with the readiness score and top preparation priorities."
    ),
)
async def full_session(
    body: CoachSkillGapRequest,
    db: AsyncSession = Depends(get_db),
) -> FullCoachingSessionResponse:
    resume, job = await _get_resume_and_job(body.resume_id, body.job_id, db)
    qb_req = CoachQuestionBankRequest(
        resume_id=body.resume_id,
        job_id=body.job_id,
    )
    return await coach_agent.run_full_session(resume, job, qb_req)
