import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.db.session import get_db
from app.models.job_posting import JobPosting
from app.schemas.job_posting import (
    JobPostingDetailResponse,
    JobPostingListResponse,
    SemanticJobSearchRequest,
    SimilarJobResponse,
)
from app.services.embedding_service import embedding_service

router = APIRouter()


@router.get(
    "",
    response_model=List[JobPostingListResponse],
    summary="List Job Postings",
    description="Paginated listing of job postings with optional title and location filters.",
)
async def list_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    title: Optional[str] = Query(None, description="Filter by title (case-insensitive substring)"),
    location: Optional[str] = Query(None, description="Filter by location (case-insensitive substring)"),
    db: AsyncSession = Depends(get_db),
) -> List[JobPostingListResponse]:
    stmt = select(JobPosting).order_by(JobPosting.created_at.desc())

    if title:
        stmt = stmt.where(JobPosting.title.ilike(f"%{title}%"))
    if location:
        stmt = stmt.where(JobPosting.location.ilike(f"%{location}%"))

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    jobs = result.scalars().all()

    items = []
    for job in jobs:
        skills_list = job.skills if isinstance(job.skills, list) else []
        items.append(
            JobPostingListResponse(
                id=job.id,
                title=job.title,
                company_name=job.company_name,
                location=job.location,
                work_type=job.work_type,
                skills_count=len(skills_list),
                created_at=job.created_at,
            )
        )
    return items


@router.get(
    "/{job_id}",
    response_model=JobPostingDetailResponse,
    summary="Get Job Posting Details",
    description="Retrieve full details for a specific job posting.",
)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> JobPostingDetailResponse:
    result = await db.execute(select(JobPosting).where(JobPosting.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job posting with ID '{job_id}' not found.",
        )

    return JobPostingDetailResponse(
        id=job.id,
        title=job.title,
        company_name=job.company_name,
        description=job.description,
        location=job.location,
        work_type=job.work_type,
        remote_allowed=job.remote_allowed,
        skills=job.skills if isinstance(job.skills, list) else [],
        min_salary=job.min_salary,
        max_salary=job.max_salary,
        med_salary=job.med_salary,
        pay_period=job.pay_period,
        external_id=job.external_id,
        source=job.source,
        created_at=job.created_at,
    )


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Job Posting",
    description="Delete a job posting from the database.",
)
async def delete_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(JobPosting).where(JobPosting.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job posting with ID '{job_id}' not found.",
        )

    await db.delete(job)
    await db.commit()
    return None


@router.post(
    "/search/similar",
    response_model=List[SimilarJobResponse],
    summary="Semantic Job Search",
    description="Find job postings matching a resume text, skill query, or job description using vector cosine similarity.",
)
async def search_similar_jobs(
    search_req: SemanticJobSearchRequest,
    db: AsyncSession = Depends(get_db),
) -> List[SimilarJobResponse]:
    # Compute query vector
    query_vector = await embedding_service.get_embedding(search_req.query)

    try:
        # Cosine distance ordering using pgvector
        stmt = (
            select(
                JobPosting.id,
                JobPosting.title,
                JobPosting.company_name,
                JobPosting.location,
                JobPosting.embedding.cosine_distance(query_vector).label("distance"),
            )
            .where(JobPosting.embedding.is_not(None))
            .order_by("distance")
            .limit(search_req.limit)
        )
        result = await db.execute(stmt)
        rows = result.all()

        results = []
        for row in rows:
            sim_score = max(0.0, 1.0 - float(row.distance))
            results.append(
                SimilarJobResponse(
                    id=row.id,
                    title=row.title,
                    company_name=row.company_name,
                    location=row.location,
                    similarity_score=round(sim_score, 4),
                )
            )
        return results

    except Exception as e:
        logger.error(f"Semantic job search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Semantic search is currently unavailable. Ensure pgvector is configured.",
        )
