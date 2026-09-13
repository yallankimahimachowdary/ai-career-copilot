"""Market Intelligence Agent API endpoints - Sprint 6."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.resume import Resume
from app.schemas.market import (
    DemandHeatmapRequest,
    DemandHeatmapResponse,
    ResumePositioningRequest,
    ResumePositioningResponse,
    RoleOverviewRequest,
    RoleOverviewResponse,
    SalaryInsightsRequest,
    SalaryInsightsResponse,
    SkillDemandRequest,
    SkillDemandResponse,
)
from app.services.market_service import market_agent

router = APIRouter()


@router.post(
    "/salary-insights",
    response_model=SalaryInsightsResponse,
    summary="Salary benchmarks for a role and location",
    description=(
        "Queries live job postings to compute salary statistics (min, p25, median, p75, max) "
        "for a given job title and optional location. Normalises hourly rates to annual. "
        "Returns a Gemini-generated narrative with a data-quality note."
    ),
)
async def salary_insights(
    body: SalaryInsightsRequest,
    db: AsyncSession = Depends(get_db),
) -> SalaryInsightsResponse:
    return await market_agent.get_salary_insights(db, body)


@router.post(
    "/trending-skills",
    response_model=SkillDemandResponse,
    summary="Top in-demand skills for a role",
    description=(
        "Analyses the skills JSON arrays across matching job postings and ranks skills "
        "by posting frequency. LinkedIn category codes (IT, HCPR, ENG, etc.) are always "
        "filtered out. Returns top-N skills with demand signal (high/moderate/low)."
    ),
)
async def trending_skills(
    body: SkillDemandRequest,
    db: AsyncSession = Depends(get_db),
) -> SkillDemandResponse:
    return await market_agent.get_trending_skills(db, body)


@router.post(
    "/demand-heatmap",
    response_model=DemandHeatmapResponse,
    summary="Location heat-map of job demand",
    description=(
        "Groups job postings by location and returns posting counts, average salaries, "
        "and remote-work percentages per city/region. Useful for identifying hiring hotspots."
    ),
)
async def demand_heatmap(
    body: DemandHeatmapRequest,
    db: AsyncSession = Depends(get_db),
) -> DemandHeatmapResponse:
    return await market_agent.get_demand_heatmap(db, body)


@router.post(
    "/role-overview",
    response_model=RoleOverviewResponse,
    summary="Full market overview for a role",
    description=(
        "Combines salary benchmarks, top skills, location heat-map, work-type breakdown, "
        "and top hiring companies into a single comprehensive market report for a given role."
    ),
)
async def role_overview(
    body: RoleOverviewRequest,
    db: AsyncSession = Depends(get_db),
) -> RoleOverviewResponse:
    return await market_agent.get_role_overview(db, body)


@router.post(
    "/resume-positioning",
    response_model=ResumePositioningResponse,
    summary="Personalised market positioning for a candidate",
    description=(
        "Fetches a candidate's resume, compares their skills against live market demand, "
        "and returns a personalised positioning report: skill alignment %, salary expectation "
        "band, competitive locations, and actionable tips."
    ),
)
async def resume_positioning(
    body: ResumePositioningRequest,
    db: AsyncSession = Depends(get_db),
) -> ResumePositioningResponse:
    resume = await db.get(Resume, body.resume_id)
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume {body.resume_id} not found.",
        )
    return await market_agent.get_resume_positioning(db, resume)
