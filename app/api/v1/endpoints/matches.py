from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.db.session import get_db
from app.schemas.matcher import (
    JobCandidatesMatchResponse,
    MatchCompareResponse,
    ResumeMatchResponse,
)
from app.services.matcher_service import matcher_agent

router = APIRouter()


@router.post(
    "/resume/{resume_id}",
    response_model=ResumeMatchResponse,
    summary="Match Jobs for Resume",
    description="Find and rank job postings matching a candidate resume using pgvector retrieval, feature extraction, weighted composite scoring, and XGBoost re-ranking with SHAP explainability.",
)
async def match_jobs_for_resume(
    resume_id: str,
    limit: int = Query(10, ge=1, le=50, description="Max matching jobs to return"),
    min_score: float = Query(0.0, ge=0.0, le=1.0, description="Minimum match threshold"),
    location: Optional[str] = Query(None, description="Optional location filter substring"),
    remote_only: bool = Query(False, description="Filter only remote-allowed positions"),
    db: AsyncSession = Depends(get_db),
) -> ResumeMatchResponse:
    try:
        return await matcher_agent.match_jobs_for_resume(
            resume_id=resume_id,
            db=db,
            limit=limit,
            min_score=min_score,
            location=location,
            remote_only=remote_only,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to match jobs for resume {resume_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Match processing failed: {str(e)}",
        )


@router.post(
    "/job/{job_id}",
    response_model=JobCandidatesMatchResponse,
    summary="Match Candidates for Job",
    description="Find and rank candidate resumes for a given job posting using vector similarity and ML re-ranking with SHAP explainability.",
)
async def match_candidates_for_job(
    job_id: str,
    limit: int = Query(10, ge=1, le=50, description="Max matching candidates to return"),
    min_score: float = Query(0.0, ge=0.0, le=1.0, description="Minimum match threshold"),
    db: AsyncSession = Depends(get_db),
) -> JobCandidatesMatchResponse:
    try:
        return await matcher_agent.match_candidates_for_job(
            job_id=job_id,
            db=db,
            limit=limit,
            min_score=min_score,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to match candidates for job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Candidate match processing failed: {str(e)}",
        )


@router.get(
    "/compare/{resume_id}/{job_id}",
    response_model=MatchCompareResponse,
    summary="Compare Resume and Job Posting",
    description="Deep-dive analysis comparing a specific resume and job posting with feature breakdowns and SHAP attribution rationale.",
)
async def compare_resume_and_job(
    resume_id: str,
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> MatchCompareResponse:
    try:
        return await matcher_agent.compare_resume_and_job(
            resume_id=resume_id,
            job_id=job_id,
            db=db,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to compare resume {resume_id} with job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Comparison failed: {str(e)}",
        )
