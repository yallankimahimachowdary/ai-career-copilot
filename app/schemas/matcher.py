from typing import List, Optional
from pydantic import BaseModel, Field


class FeatureBreakdown(BaseModel):
    """Detailed numerical features extracted for candidate and job posting pair."""
    semantic_similarity: float = Field(..., description="Vector cosine similarity (0.0 - 1.0)")
    must_have_skill_match: float = Field(..., description="Match ratio for required must-have skills (0.0 - 1.0)")
    nice_to_have_skill_match: float = Field(..., description="Match ratio for preferred nice-to-have skills (0.0 - 1.0)")
    candidate_years_experience: float = Field(..., description="Estimated years of candidate work experience")
    job_required_years: float = Field(..., description="Required years extracted from job description")
    experience_deficit: float = Field(..., description="Years below requirement (0 if meeting or exceeding)")
    experience_penalty: float = Field(..., description="Penalty applied if experience deficit exceeds threshold")
    education_level_match: float = Field(..., description="Degree alignment score (0.0 - 1.0)")
    title_similarity: float = Field(..., description="Role title alignment score (0.0 - 1.0)")


class ShapExplanation(BaseModel):
    """SHAP-derived feature contribution explanation."""
    feature_name: str = Field(..., description="Internal feature key")
    display_name: str = Field(..., description="Human-friendly feature label")
    shap_value: float = Field(..., description="SHAP feature attribution value")
    impact: str = Field(..., description="Formatted string impact representation, e.g. +14% or -8%")
    description: str = Field(..., description="Contextual explanation of this feature's positive or negative effect")


class SkillsBreakdown(BaseModel):
    """Skill match and gap analysis breakdown."""
    matched_skills: List[str] = Field(default_factory=list, description="Skills present in both resume and job")
    missing_must_have: List[str] = Field(default_factory=list, description="Core required skills missing in resume")
    missing_nice_to_have: List[str] = Field(default_factory=list, description="Nice-to-have skills missing in resume")


class JobMatchItem(BaseModel):
    """Ranked job posting match result for a candidate resume."""
    job_id: str
    title: str
    company_name: Optional[str] = None
    location: Optional[str] = None
    work_type: Optional[str] = None
    remote_allowed: bool = False
    semantic_score: float = Field(..., description="pgvector cosine similarity score")
    composite_score: float = Field(..., description="Rule-based weighted composite score")
    xgboost_score: float = Field(..., description="ML re-ranked prediction score")
    final_score: float = Field(..., description="Final calibrated matching score (0.0 - 1.0)")
    rank: int = Field(..., description="Position in recommendation ranking")
    skills_breakdown: SkillsBreakdown
    features: FeatureBreakdown
    explanations: List[ShapExplanation]


class ResumeMatchResponse(BaseModel):
    """Response containing ranked job matches for a resume."""
    resume_id: str
    candidate_name: Optional[str] = None
    total_matches: int
    matches: List[JobMatchItem]


class CandidateMatchItem(BaseModel):
    """Ranked candidate resume match result for a job posting."""
    resume_id: str
    candidate_name: Optional[str] = None
    email: Optional[str] = None
    semantic_score: float
    composite_score: float
    xgboost_score: float
    final_score: float
    rank: int
    skills_breakdown: SkillsBreakdown
    features: FeatureBreakdown
    explanations: List[ShapExplanation]


class JobCandidatesMatchResponse(BaseModel):
    """Response containing ranked candidate resumes for a job posting."""
    job_id: str
    job_title: str
    company_name: Optional[str] = None
    total_matches: int
    candidates: List[CandidateMatchItem]


class MatchCompareResponse(BaseModel):
    """Detailed direct pairwise comparison between a resume and job posting."""
    resume_id: str
    candidate_name: Optional[str] = None
    job_id: str
    job_title: str
    company_name: Optional[str] = None
    semantic_score: float
    composite_score: float
    xgboost_score: float
    final_score: float
    skills_breakdown: SkillsBreakdown
    features: FeatureBreakdown
    explanations: List[ShapExplanation]
