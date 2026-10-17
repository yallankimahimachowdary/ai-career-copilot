"""
app/schemas/orchestrator.py
--------------------------
Typed Shared State and Workflow Schemas for Multi-Agent Orchestration.
Supports structured state propagation between Parser, Matcher, Market, and Coach agents.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.resume import ParsedResume


class WorkflowStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"


class WorkflowStep(str, Enum):
    INITIALIZE = "INITIALIZE"
    PARSER = "PARSER"
    MATCHER = "MATCHER"
    MARKET = "MARKET"
    COACH = "COACH"
    SYNTHESIZE = "SYNTHESIZE"
    COMPLETE = "COMPLETE"


class AgentFailureRecord(BaseModel):
    """Tracks non-fatal and fatal agent failures for transparent graceful recovery."""
    agent_name: str
    step: WorkflowStep
    error_message: str
    recovered: bool = True
    timestamp: str


class CareerWorkflowState(BaseModel):
    """
    Typed shared state passed through the multi-agent orchestration pipeline.
    Maintains provenance and inputs/outputs of each collaborating agent.
    """
    workflow_id: str = Field(..., description="Unique UUID for this orchestration execution.")
    status: WorkflowStatus = Field(default=WorkflowStatus.PENDING)
    current_step: WorkflowStep = Field(default=WorkflowStep.INITIALIZE)
    completed_steps: List[WorkflowStep] = Field(default_factory=list)

    # Input contexts
    raw_resume_text: Optional[str] = Field(default=None, description="Raw input resume text if uploaded.")
    resume_id: Optional[str] = Field(default=None, description="Existing resume ID in database.")
    target_role: Optional[str] = Field(default=None, description="Candidate target role (e.g. 'Backend Engineer').")
    target_location: Optional[str] = Field(default=None, description="Target location filter.")

    # Agent Artifacts
    parsed_resume: Optional[ParsedResume] = Field(default=None, description="Output from Parser Agent.")
    matched_jobs: List[Dict[str, Any]] = Field(default_factory=list, description="Output from Matcher Agent.")
    market_insights: Optional[Dict[str, Any]] = Field(default=None, description="Output from Market Agent.")
    coaching_plan: Optional[Dict[str, Any]] = Field(default=None, description="Output from Coach Agent.")

    # Synthesized Guidance
    executive_summary: Optional[str] = Field(default=None, description="Holistic career recommendation.")
    actionable_next_steps: List[str] = Field(default_factory=list)

    # Error handling & Graceful degradation
    errors: List[AgentFailureRecord] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowExecutionRequest(BaseModel):
    """Request payload to initiate or run a multi-agent workflow."""
    raw_resume_text: Optional[str] = None
    resume_id: Optional[str] = None
    target_role: Optional[str] = None
    target_location: Optional[str] = None
    limit_jobs: int = Field(default=5, ge=1, le=20)
    enabled_agents: List[str] = Field(
        default_factory=lambda: ["parser", "matcher", "market", "coach"],
        description="List of agents to execute in the workflow: 'parser', 'matcher', 'market', 'coach'.",
    )
