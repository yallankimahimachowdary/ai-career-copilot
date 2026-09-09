"""Pydantic schemas for the Coach Agent - Sprint 5."""

from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class SkillGapItem(BaseModel):
    """Single skill examined in the gap analysis."""
    skill: str = Field(..., description="Skill name")
    category: str = Field(..., description="Category, e.g. Language, Framework, Cloud, Soft-skill")
    importance: Literal["high", "medium", "low"] = Field(..., description="How critical the skill is for this role")
    candidate_has: bool = Field(..., description="Whether the candidate already possesses this skill")
    recommendation: str = Field(..., description="Action recommendation, e.g. a course, project idea, or certification")


class SkillGapReport(BaseModel):
    """Full skill-gap diagnostic report (Step 1 output)."""
    resume_id: str
    job_id: str
    job_title: str
    company_name: Optional[str] = None
    candidate_name: Optional[str] = None
    overall_readiness_score: float = Field(..., ge=0.0, le=100.0, description="Interview readiness percentage 0-100")
    confirmed_strengths: List[str] = Field(default_factory=list, description="Skills the candidate already has that the role requires")
    critical_gaps: List[SkillGapItem] = Field(default_factory=list, description="Must-have skills that are missing")
    growth_gaps: List[SkillGapItem] = Field(default_factory=list, description="Nice-to-have skills that are missing")
    executive_summary: str = Field(..., description="2-3 sentence narrative summary of the candidate fit")
    learning_roadmap: List[str] = Field(default_factory=list, description="Prioritised action steps to bridge the skill gaps")


class InterviewQuestion(BaseModel):
    """A single interview question with metadata."""
    id: str = Field(..., description="Unique question ID e.g. TQ-001")
    category: Literal["technical", "behavioral", "gap_probing", "system_design"]
    difficulty: Literal["junior", "mid", "senior"]
    target_skill: str
    question: str
    why_asked: str
    sample_answer: str
    evaluation_criteria: List[str] = Field(default_factory=list)


class QuestionBank(BaseModel):
    """Full curated question bank for a resume-job pair (Step 2 output)."""
    resume_id: str
    job_id: str
    job_title: str
    candidate_name: Optional[str] = None
    technical_questions: List[InterviewQuestion] = Field(default_factory=list)
    behavioral_questions: List[InterviewQuestion] = Field(default_factory=list)
    gap_questions: List[InterviewQuestion] = Field(default_factory=list)
    preparation_tips: List[str] = Field(default_factory=list)


class AnswerEvaluationRequest(BaseModel):
    """Request body for evaluating a candidate practice answer."""
    question_id: Optional[str] = None
    question_text: str
    target_skill: str
    job_context: str
    candidate_answer: str


class AnswerEvaluationResponse(BaseModel):
    """Rubric-based evaluation result for a practice answer (Step 3 output)."""
    score: float = Field(..., ge=0.0, le=10.0)
    grade: Literal["excellent", "good", "needs_improvement", "poor"]
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    improved_answer: str
    rubric_breakdown: Dict[str, float] = Field(default_factory=dict)


class CoachSkillGapRequest(BaseModel):
    """Request body for the skill-gap endpoint."""
    resume_id: str
    job_id: str


class CoachQuestionBankRequest(BaseModel):
    """Request body for the question-bank endpoint."""
    resume_id: str
    job_id: str
    max_technical: int = Field(5, ge=1, le=10)
    max_behavioral: int = Field(3, ge=1, le=8)
    max_gap: int = Field(3, ge=1, le=8)


class FullCoachingSessionResponse(BaseModel):
    """Combined output from a full coaching session (all three steps)."""
    resume_id: str
    job_id: str
    skill_gap_report: SkillGapReport
    question_bank: QuestionBank
    overall_readiness_score: float = Field(..., ge=0.0, le=100.0)
    top_preparation_priorities: List[str] = Field(default_factory=list)
