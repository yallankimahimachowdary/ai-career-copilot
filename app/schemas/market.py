"""Pydantic schemas for the Market Intelligence Agent - Sprint 6."""

from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------------

class SalaryBand(BaseModel):
    """Aggregated salary statistics for a role/location combination."""
    min_annual: Optional[float] = None
    p25_annual: Optional[float] = None
    median_annual: Optional[float] = None
    p75_annual: Optional[float] = None
    max_annual: Optional[float] = None
    mean_annual: Optional[float] = None
    currency: str = "USD"
    sample_size: int = 0


# ---------------------------------------------------------------------------
# Salary Insights
# ---------------------------------------------------------------------------

class SalaryInsightsRequest(BaseModel):
    title_query: str = Field(..., min_length=1, description="Job title keyword, e.g. 'Software Engineer'")
    location: Optional[str] = Field(None, description="Optional city/state filter, e.g. 'New York'")
    pay_period_filter: Optional[Literal["YEARLY", "HOURLY", "ALL"]] = Field(
        "ALL", description="Filter by pay period before normalisation"
    )


class TopPayingCompany(BaseModel):
    company_name: str
    median_salary: Optional[float] = None
    posting_count: int


class SalaryInsightsResponse(BaseModel):
    role_title: str
    location_filter: Optional[str] = None
    salary_band: SalaryBand
    top_paying_companies: List[TopPayingCompany] = []
    narrative: str
    data_quality_note: str


# ---------------------------------------------------------------------------
# Trending Skills
# ---------------------------------------------------------------------------

class SkillDemandItem(BaseModel):
    skill: str
    posting_count: int
    percentage: float  # % of analysed postings that mention this skill
    trend_signal: Literal["high", "moderate", "low"]


class SkillDemandRequest(BaseModel):
    title_query: Optional[str] = Field(None, description="Optional role filter. Leave blank for all roles.")
    location: Optional[str] = None
    top_n: int = Field(10, ge=1, le=50)


class SkillDemandResponse(BaseModel):
    role_context: str
    total_postings_analysed: int
    skills: List[SkillDemandItem]
    narrative: str


# ---------------------------------------------------------------------------
# Demand Heat-map
# ---------------------------------------------------------------------------

class LocationDemandItem(BaseModel):
    location: str
    posting_count: int
    percentage: float
    avg_annual_salary: Optional[float] = None
    remote_pct: float  # 0–100


class DemandHeatmapRequest(BaseModel):
    title_query: Optional[str] = Field(None, description="Optional role filter.")
    top_n: int = Field(10, ge=1, le=50)


class DemandHeatmapResponse(BaseModel):
    role_context: str
    total_postings_analysed: int
    locations: List[LocationDemandItem]
    hottest_market: Optional[str] = None
    narrative: str


# ---------------------------------------------------------------------------
# Role Overview
# ---------------------------------------------------------------------------

class WorkTypeBreakdown(BaseModel):
    full_time: int = 0
    part_time: int = 0
    contract: int = 0
    internship: int = 0
    other: int = 0


class RoleOverviewRequest(BaseModel):
    title_query: str = Field(..., min_length=1)
    location: Optional[str] = None


class RoleOverviewResponse(BaseModel):
    title_query: str
    location_filter: Optional[str] = None
    total_postings: int
    work_type_breakdown: WorkTypeBreakdown
    remote_pct: float
    top_companies: List[str]
    salary_band: SalaryBand
    top_skills: List[SkillDemandItem]
    top_locations: List[LocationDemandItem]
    narrative: str
    data_quality_note: str


# ---------------------------------------------------------------------------
# Resume Positioning (personalised market report)
# ---------------------------------------------------------------------------

class ResumePositioningRequest(BaseModel):
    resume_id: str


class SkillAlignmentItem(BaseModel):
    skill: str
    market_demand_pct: float  # % of relevant postings mentioning this skill
    candidate_has: bool
    signal: Literal["strength", "gap", "opportunity"]


class ResumePositioningResponse(BaseModel):
    resume_id: str
    candidate_name: Optional[str] = None
    total_relevant_postings: int
    skill_alignment: List[SkillAlignmentItem]
    matched_skill_count: int
    coverage_pct: float  # % of top-20 market skills the candidate has
    salary_expectation_band: SalaryBand
    competitive_locations: List[str]
    market_narrative: str
    positioning_tips: List[str]
