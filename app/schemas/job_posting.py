from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class JobPostingBase(BaseModel):
    """Common fields shared across job posting schemas."""
    title: str = Field(..., description="Job title")
    company_name: Optional[str] = Field(None, description="Hiring company name")
    description: str = Field(..., description="Full job description text")
    location: Optional[str] = Field(None, description="Job location")
    work_type: Optional[str] = Field(None, description="Full-time, Contract, etc.")
    remote_allowed: bool = Field(False, description="Whether remote work is allowed")
    skills: List[str] = Field(default_factory=list, description="Required skills")
    min_salary: Optional[float] = Field(None, description="Minimum salary")
    max_salary: Optional[float] = Field(None, description="Maximum salary")
    pay_period: Optional[str] = Field(None, description="YEARLY, HOURLY, etc.")
    country: Optional[str] = Field("India", description="Country location")
    currency: Optional[str] = Field("INR", description="Currency code (e.g. INR)")
    source_url: Optional[str] = Field(None, description="Canonical or redirect URL to job posting")


class JobPostingResponse(JobPostingBase):
    """Response schema for a job posting."""
    id: str = Field(..., description="Unique job posting ID")
    source: str = Field(..., description="Data source (e.g. kaggle_linkedin, adzuna_api)")
    country: str = Field("India", description="Country location")
    currency: str = Field("INR", description="Currency code")
    published_at: Optional[datetime] = Field(None, description="Original publication timestamp from employer/source")
    first_seen_at: Optional[datetime] = Field(None, description="Timestamp when our system first ingested this job")
    last_seen_at: Optional[datetime] = Field(None, description="Timestamp when job was last observed active in source feed")
    last_refreshed_at: Optional[datetime] = Field(None, description="Timestamp of last metadata/status refresh")
    is_active: bool = Field(True, description="Whether this job is currently active for recommendations")
    freshness_status: str = Field("fresh", description="Freshness status: fresh, stale, expired, inactive")
    source_job_id: Optional[str] = Field(None, description="Raw provider job ID")
    created_at: datetime = Field(..., description="Record creation timestamp")


class JobPostingDetailResponse(JobPostingResponse):
    """Full detail response including median salary."""
    med_salary: Optional[float] = Field(None, description="Median salary")
    external_id: Optional[str] = Field(None, description="External source ID")


class JobPostingListResponse(BaseModel):
    """Lightweight list item for paginated responses."""
    id: str
    title: str
    company_name: Optional[str] = None
    location: Optional[str] = None
    work_type: Optional[str] = None
    skills_count: int = 0
    is_active: bool = True
    freshness_status: str = "fresh"
    data_as_of: Optional[str] = "2026-10-19"
    published_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    created_at: datetime


class SimilarJobResponse(BaseModel):
    """Search result with similarity score."""
    id: str
    title: str
    company_name: Optional[str] = None
    location: Optional[str] = None
    similarity_score: float
    freshness_status: Optional[str] = "fresh"
    is_active: Optional[bool] = True


class SemanticJobSearchRequest(BaseModel):
    """Request body for semantic job search."""
    query: str = Field(..., min_length=2, description="Resume text, skills, or job description to match against")
    limit: int = Field(default=10, ge=1, le=100, description="Max results to return")
    include_inactive: bool = Field(default=False, description="Whether to include inactive or expired jobs")


class JobRefreshRequest(BaseModel):
    """Request payload for manual job refresh."""
    queries: Optional[List[str]] = Field(None, description="Optional search queries to refresh")
    sources: Optional[List[str]] = Field(None, description="Optional sources to refresh (e.g. ['adzuna'])")
    max_retries: Optional[int] = Field(None, ge=0, le=5, description="Max retries for transient provider failures")
    evaluate_freshness: bool = Field(True, description="Whether to evaluate freshness across all stored listings")


class JobRefreshRunResponse(BaseModel):
    """Response returned from a job refresh execution."""
    run_id: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    status: str
    sources: Dict[str, Any] = Field(default_factory=dict)
    freshness_summary: Dict[str, int] = Field(default_factory=dict)
    error_category: Optional[str] = None
    error_message: Optional[str] = None


class JobRefreshStatusResponse(BaseModel):
    """Current status of the refresh coordinator."""
    is_running: bool
    last_run: Optional[JobRefreshRunResponse] = None
    data_as_of: str = "2026-10-19"
