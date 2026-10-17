import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_superuser, get_current_user
from app.core.logging import logger
from app.db.session import get_db
from app.models.job_posting import JobPosting
from app.models.user import User
from app.schemas.job_posting import (
    JobPostingDetailResponse,
    JobPostingListResponse,
    JobRefreshRequest,
    JobRefreshRunResponse,
    JobRefreshStatusResponse,
    SemanticJobSearchRequest,
    SimilarJobResponse,
)
from app.services.embedding_service import embedding_service
from app.services.job_refresh_coordinator import job_refresh_coordinator

router = APIRouter()


@router.get(
    "/stats",
    summary="Get Job Postings Statistics",
    description="Returns total count of active job postings indexed in PostgreSQL.",
)
async def get_job_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(func.count(JobPosting.id)))
    total_count = result.scalar() or 0
    return {"total": total_count}


@router.get(
    "",
    response_model=List[JobPostingListResponse],
    summary="List Job Postings",
    description="Paginated listing of job postings with optional filters for title, location, active status, and freshness.",
)
async def list_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    title: Optional[str] = Query(None, description="Filter by title (case-insensitive substring)"),
    location: Optional[str] = Query(None, description="Filter by location (case-insensitive substring)"),
    is_active: Optional[bool] = Query(None, description="Filter by active status (True/False)"),
    freshness: Optional[str] = Query(None, description="Filter by freshness status (fresh, stale, expired, inactive)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[JobPostingListResponse]:
    stmt = select(JobPosting).order_by(JobPosting.created_at.desc())

    if title:
        stmt = stmt.where(JobPosting.title.ilike(f"%{title}%"))
    if location:
        stmt = stmt.where(JobPosting.location.ilike(f"%{location}%"))
    if is_active is not None:
        stmt = stmt.where(JobPosting.is_active == is_active)
    if freshness:
        stmt = stmt.where(JobPosting.freshness_status == freshness)

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
                is_active=job.is_active if job.is_active is not None else True,
                freshness_status=job.freshness_status or "fresh",
                published_at=job.published_at,
                last_seen_at=job.last_seen_at,
                created_at=job.created_at,
            )
        )
    return items


@router.get(
    "/{job_id}",
    response_model=JobPostingDetailResponse,
    summary="Get Job Posting Details",
    description="Retrieve full details for a specific job posting, including freshness and source information.",
)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
        remote_allowed=bool(job.remote_allowed) if job.remote_allowed is not None else False,
        skills=job.skills if isinstance(job.skills, list) else [],
        min_salary=job.min_salary,
        max_salary=job.max_salary,
        med_salary=job.med_salary,
        pay_period=job.pay_period,
        external_id=job.external_id,
        source=job.source or "internal",
        source_job_id=job.source_job_id,
        source_url=job.source_url,
        published_at=job.published_at,
        first_seen_at=job.first_seen_at,
        last_seen_at=job.last_seen_at,
        last_refreshed_at=job.last_refreshed_at,
        is_active=job.is_active if job.is_active is not None else True,
        freshness_status=job.freshness_status or "fresh",
        created_at=job.created_at,
    )


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Job Posting",
    description="Delete a job posting from the database. Requires superuser privileges.",
)
async def delete_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
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
    description="Find job postings matching a resume text, skill query, or job description using vector cosine similarity. Excludes inactive jobs by default.",
)
async def search_similar_jobs(
    search_req: SemanticJobSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
                JobPosting.freshness_status,
                JobPosting.is_active,
                JobPosting.embedding.cosine_distance(query_vector).label("distance"),
            )
            .where(JobPosting.embedding.is_not(None))
        )

        # Exclude inactive or expired jobs by default
        if not search_req.include_inactive:
            stmt = stmt.where(JobPosting.is_active.is_(True))

        stmt = stmt.order_by("distance").limit(search_req.limit)
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
                    freshness_status=row.freshness_status or "fresh",
                    is_active=row.is_active if row.is_active is not None else True,
                )
            )
        return results

    except Exception as e:
        logger.error(f"Semantic job search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Semantic search is currently unavailable. Ensure pgvector is configured.",
        )


@router.post(
    "/refresh/run",
    response_model=JobRefreshRunResponse,
    summary="Trigger Manual Job Refresh",
    description="Manually trigger a job refresh and freshness evaluation cycle.",
)
async def trigger_refresh(
    body: Optional[JobRefreshRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobRefreshRunResponse:
    queries = body.queries if body else None
    sources = body.sources if body else None
    max_retries = body.max_retries if body else None
    evaluate_freshness = body.evaluate_freshness if body else True

    run_record = await job_refresh_coordinator.run_refresh(
        queries=queries,
        sources=sources,
        max_retries=max_retries,
        evaluate_freshness=evaluate_freshness,
        db_session=db,
    )

    if run_record.status == "skipped":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A job refresh run is already actively running.",
        )

    return JobRefreshRunResponse(
        run_id=run_record.run_id,
        started_at=run_record.started_at,
        finished_at=run_record.finished_at,
        duration_seconds=run_record.duration_seconds,
        status=run_record.status,
        sources=run_record.sources,
        freshness_summary=run_record.freshness_summary,
        error_category=run_record.error_category,
        error_message=run_record.error_message,
    )


@router.get(
    "/refresh/status",
    response_model=JobRefreshStatusResponse,
    summary="Get Job Refresh Status",
    description="Check whether a job refresh is actively executing and retrieve the last completed run.",
)
async def get_refresh_status(
    current_user: User = Depends(get_current_user),
) -> JobRefreshStatusResponse:
    last_run = job_refresh_coordinator.get_last_run()
    last_run_resp = None
    if last_run:
        last_run_resp = JobRefreshRunResponse(
            run_id=last_run.run_id,
            started_at=last_run.started_at,
            finished_at=last_run.finished_at,
            duration_seconds=last_run.duration_seconds,
            status=last_run.status,
            sources=last_run.sources,
            freshness_summary=last_run.freshness_summary,
            error_category=last_run.error_category,
            error_message=last_run.error_message,
        )
    return JobRefreshStatusResponse(
        is_running=job_refresh_coordinator.is_running(),
        last_run=last_run_resp,
    )

