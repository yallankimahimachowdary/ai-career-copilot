"""
tests/test_orchestrator.py
--------------------------
Unit and integration tests for MultiAgentOrchestrator.
Tests state propagation, custom workflow routing, and agent failure recovery.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.models.job_posting import JobPosting
from app.schemas.orchestrator import (
    CareerWorkflowState,
    WorkflowExecutionRequest,
    WorkflowStatus,
    WorkflowStep,
)
from app.services.orchestrator import multi_agent_orchestrator


SAMPLE_RESUME = """
Johnathan Developer
john.dev@example.com | 555-123-4567 | San Francisco, CA
linkedin.com/in/johndev | github.com/johndev

TECHNICAL SKILLS
Python, FastAPI, Docker, PostgreSQL, Kubernetes

WORK EXPERIENCE
Senior Backend Engineer at CloudScale
- Designed REST APIs with FastAPI and Docker.
- Orchestrated Kubernetes deployments.

EDUCATION
University of California, Berkeley
B.S. in Computer Science, 2021
"""


@pytest.mark.asyncio
async def test_orchestrator_state_propagation_full_pipeline():
    """Verify end-to-end typed state propagation across Parser, Matcher, Market, and Coach agents."""
    req = WorkflowExecutionRequest(
        raw_resume_text=SAMPLE_RESUME,
        target_role="Senior Backend Engineer",
        target_location="San Francisco, CA",
        limit_jobs=3,
        enabled_agents=["parser", "matcher", "market", "coach"],
    )

    mock_job = JobPosting(
        id=uuid.uuid4(),
        title="Senior Backend Engineer",
        company_name="Cloud Corp",
        location="San Francisco, CA",
        description="Looking for Senior Backend Engineer with Python and FastAPI.",
        skills=["Python", "FastAPI", "Docker", "PostgreSQL"],
    )
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_job]
    mock_db.execute.return_value = mock_result

    state = await multi_agent_orchestrator.execute_workflow(req, db=mock_db)

    # 1. Workflow Status and Lifecycle
    assert state.status == WorkflowStatus.COMPLETED
    assert WorkflowStep.PARSER in state.completed_steps
    assert WorkflowStep.MATCHER in state.completed_steps
    assert WorkflowStep.MARKET in state.completed_steps
    assert WorkflowStep.COACH in state.completed_steps
    assert len(state.errors) == 0

    # 2. Parser Artifacts
    assert state.parsed_resume is not None
    assert "Python" in state.parsed_resume.skills
    assert "FastAPI" in state.parsed_resume.skills
    assert state.parsed_resume.contact_info.email == "john.dev@example.com"

    # 3. Matcher Artifacts (propagated from Parser skills and real DB results)
    assert len(state.matched_jobs) == 1
    top_match = state.matched_jobs[0]
    assert top_match["title"] == "Senior Backend Engineer"
    assert top_match["company_name"] == "Cloud Corp"
    assert top_match["location"] == "San Francisco, CA"
    assert "match_score" in top_match
    assert top_match["match_score"] > 0.0

    # 4. Market Artifacts (propagated from target_role & match)
    assert state.market_insights is not None
    assert "compensation" in state.market_insights
    assert state.market_insights["compensation"]["median"] > 0
    assert "demand_signal" in state.market_insights

    # 5. Coach Artifacts (propagated from Parser & top match)
    assert state.coaching_plan is not None
    assert "readiness_score" in state.coaching_plan
    assert "learning_roadmap" in state.coaching_plan
    assert len(state.coaching_plan["technical_questions"]) >= 1

    # 6. Synthesized Output
    assert state.executive_summary is not None
    assert "Johnathan Developer" in state.executive_summary or "Candidate" in state.executive_summary
    assert len(state.actionable_next_steps) >= 2


@pytest.mark.asyncio
async def test_orchestrator_empty_database_returns_no_invented_jobs():
    """Verify that when database returns 0 jobs, matched_jobs is empty and no_matching_jobs is True."""
    req = WorkflowExecutionRequest(
        raw_resume_text=SAMPLE_RESUME,
        target_role="Senior Backend Engineer",
        enabled_agents=["matcher"],
    )
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    state = await multi_agent_orchestrator.execute_workflow(req, db=mock_db)

    assert state.status == WorkflowStatus.COMPLETED
    assert len(state.matched_jobs) == 0
    assert state.no_matching_jobs is True


@pytest.mark.asyncio
async def test_orchestrator_custom_workflow_routing():
    """Verify selective routing: only enabled agents are invoked in the DAG."""
    req = WorkflowExecutionRequest(
        target_role="Data Scientist",
        target_location="Austin, TX",
        enabled_agents=["market", "coach"],  # Parser and Matcher bypassed
    )

    state = await multi_agent_orchestrator.execute_workflow(req, db=None)

    assert state.status == WorkflowStatus.COMPLETED
    assert WorkflowStep.PARSER not in state.completed_steps
    assert WorkflowStep.MATCHER not in state.completed_steps
    assert WorkflowStep.MARKET in state.completed_steps
    assert WorkflowStep.COACH in state.completed_steps
    assert state.parsed_resume is None
    assert state.market_insights is not None
    assert state.coaching_plan is not None


@pytest.mark.asyncio
async def test_orchestrator_agent_failure_and_graceful_recovery():
    """When one agent fails, orchestrator captures failure record and continues execution with remaining agents."""
    req = WorkflowExecutionRequest(
        raw_resume_text=SAMPLE_RESUME,
        target_role="Backend Engineer",
        enabled_agents=["parser", "matcher", "market", "coach"],
    )

    # Simulate parser crashing unexpectedly
    with patch("app.services.orchestrator.parser_agent.parse", side_effect=RuntimeError("Simulated OCR Parser Failure")):
        state = await multi_agent_orchestrator.execute_workflow(req, db=None)

    # Pipeline must not crash; status becomes PARTIAL_SUCCESS
    assert state.status == WorkflowStatus.PARTIAL_SUCCESS
    assert WorkflowStep.PARSER not in state.completed_steps
    assert WorkflowStep.MATCHER in state.completed_steps
    assert WorkflowStep.MARKET in state.completed_steps
    assert WorkflowStep.COACH in state.completed_steps

    # Verify transparent error tracking
    assert len(state.errors) == 1
    err = state.errors[0]
    assert err.agent_name == "parser"
    assert err.step == WorkflowStep.PARSER
    assert "Simulated OCR Parser Failure" in err.error_message
    assert err.recovered is False

    # When db is None, matcher produces 0 jobs honestly, not invented Databricks or Stripe
    assert len(state.matched_jobs) == 0
    assert state.no_matching_jobs is True
    assert state.market_insights is not None
    assert state.coaching_plan is not None
    assert state.executive_summary is not None


@pytest.mark.asyncio
async def test_orchestrator_market_and_coach_failures_graceful_recovery():
    """Multiple agent failures are logged while surviving agents propagate state."""
    req = WorkflowExecutionRequest(
        raw_resume_text=SAMPLE_RESUME,
        enabled_agents=["parser", "matcher", "market", "coach"],
    )

    with patch("app.services.orchestrator.market_agent.get_role_overview", side_effect=Exception("Database Timeout")), \
         patch("app.services.orchestrator.coach_agent.generate_skill_gap_report", side_effect=RuntimeError("LLM API Quota Exceeded")):
        state = await multi_agent_orchestrator.execute_workflow(req, db=None)

    # Coach failure logged
    assert any(e.agent_name == "coach" for e in state.errors)
    assert WorkflowStep.PARSER in state.completed_steps
    assert WorkflowStep.MATCHER in state.completed_steps
    assert state.status == WorkflowStatus.PARTIAL_SUCCESS
