from datetime import datetime, timezone
from typing import List, Optional
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


class JobPostingResponse(JobPostingBase):
    """Response schema for a job posting."""
    id: str = Field(..., description="Unique job posting ID")
    source: str = Field(..., description="Data source (e.g. kaggle_linkedin)")
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
    created_at: datetime


class SimilarJobResponse(BaseModel):
    """Search result with similarity score."""
    id: str
    title: str
    company_name: Optional[str] = None
    location: Optional[str] = None
    similarity_score: float


class SemanticJobSearchRequest(BaseModel):
    """Request body for semantic job search."""
    query: str = Field(..., min_length=2, description="Resume text, skills, or job description to match against")
    limit: int = Field(default=10, ge=1, le=100, description="Max results to return")
