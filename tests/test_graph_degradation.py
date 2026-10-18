"""Tests for Graph Orchestrator Degradation, Session Hygiene, and Honest Error Reporting.

Remediation R5.1 verification:
1. When match node encounters an error (e.g. SQLAlchemyError), status is 'degraded: match',
   the original error is recorded with host:port, matched_jobs is empty, match_unavailable is True,
   no arbitrary jobs are returned, and synthesis states matching is unavailable.
2. Real-session rollback test: an aborted query followed by rollback allows subsequent queries
   to succeed without InFailedSQLTransactionError.
3. When router fails, orchestrator records error, marks low_confidence=True, fallback_used=True,
   and degraded status naming 'router'.
4. 'recovered' flag is True ONLY when a retried operation succeeds; unrecovered failures are False.
5. Static AST / grep test ensuring no unranked select(JobPosting).limit calls exist.
"""

import ast
import re
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError, SQLAlchemyError

from app.db.session import AsyncSessionLocal
from app.models.job_posting import JobPosting
from app.schemas.chat import ChatQueryRequest, IntentType, RouterDecision
from app.services.graph_orchestrator import (
    GraphState,
    _build_error_record,
    _mark_recovered,
    determine_execution_status,
    langgraph_orchestrator,
)


# ---------------------------------------------------------------------------
# 1. Honest Match Degradation Test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_match_failure_honest_degradation():
    """
    When match_node encounters a database / search failure:
    - Status is degraded naming 'match'.
    - Original error is recorded with host:port.
    - matched_jobs is empty (no arbitrary jobs like Databricks or Stripe).
    - match_unavailable is True.
    - Response text explicitly states matching is unavailable.
    """
    # Create a mock session where execute raises an error
    mock_db = AsyncMock()
    mock_db.execute.side_effect = SQLAlchemyError("FATAL: connection terminated unexpectedly")
    mock_db.rollback = AsyncMock()

    request = ChatQueryRequest(
        query="Looking for remote Python backend engineer jobs",
    )

    with patch(
        "app.services.router_service.router_service.classify_intent",
        new=AsyncMock(
            return_value=RouterDecision(
                intent=IntentType.JOB_SEARCH,
                confidence=0.92,
                strategy_selected="Strategy 1: Hybrid Vector Search & XGBoost Re-ranking",
                reasoning="Explicit job search request.",
                backend="trained",
                low_confidence=False,
                fallback_used=False,
                strategy="Strategy 1: Hybrid Vector Search & XGBoost Re-ranking",
            )
        ),
    ):
        result = await langgraph_orchestrator.execute(request, db=mock_db, use_llm=False)

    # Rollback must have been called on the session
    mock_db.rollback.assert_called()

    # Trace inspection
    trace = next((s for s in result.sources if s.get("type") == "orchestrator_trace"), None)
    assert trace is not None, "Execution trace must be attached to sources"
    assert trace["status"] == "degraded: match", f"Expected 'degraded: match', got {trace['status']}"

    # Error record verification
    match_errors = [e for e in trace["errors"] if e.get("agent_name") == "match"]
    assert len(match_errors) == 1, "Exactly one match error should be recorded"
    err = match_errors[0]
    assert err["recovered"] is False, "Unrecovered failure must have recovered=False"
    assert "target_host_port" in err or "5432" in err["error_message"]
    assert "connection terminated unexpectedly" in err["error_message"]

    # No unranked or arbitrary jobs in sources
    job_sources = [s for s in result.sources if s.get("type") == "job_posting"]
    assert len(job_sources) == 0, f"Expected 0 job sources on failure, found {len(job_sources)}"

    # Response states matching is unavailable
    assert "matching is currently unavailable" in result.response.lower()
    assert "databricks" not in result.response.lower()
    assert "stripe" not in result.response.lower()


# ---------------------------------------------------------------------------
# 2. Session Rollback & Transaction Isolation Test
# ---------------------------------------------------------------------------

@pytest.mark.requires_postgres
@pytest.mark.asyncio
async def test_session_rollback_prevents_in_failed_sql_transaction():
    """
    Verifies that when a query fails within an AsyncSession,
    calling rollback() allows subsequent queries on the same session to succeed
    without encountering InFailedSQLTransactionError ('current transaction is aborted').
    """
    async with AsyncSessionLocal() as session:
        # 1. Execute an invalid SQL statement that fails
        try:
            await session.execute(text("SELECT * FROM nonexistent_table_xyz_123"))
        except ProgrammingError:
            # Cleanly roll back the aborted transaction
            await session.rollback()

        # 2. Subsequent valid query on the SAME session MUST succeed
        res = await session.execute(text("SELECT count(*) FROM job_postings"))
        count = res.scalar()
        assert count is not None and count > 0, "Query after rollback must succeed"


# ---------------------------------------------------------------------------
# 3. Router Failure Degradation Test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_router_failure_honest_degradation():
    """
    When router fails permanently:
    - Status is degraded naming 'router'.
    - fallback_used is True and low_confidence is True.
    - Error is recorded with host:port (localhost:11434).
    """
    request = ChatQueryRequest(query="find python jobs")

    with patch(
        "app.services.router_service.router_service.classify_intent",
        new=AsyncMock(side_effect=ConnectionError("WinError 1225 remote computer refused the network connection")),
    ):
        result = await langgraph_orchestrator.execute(request, db=None, use_llm=False)

    trace = next((s for s in result.sources if s.get("type") == "orchestrator_trace"), None)
    assert trace is not None
    assert "router" in trace["status"]

    router_errors = [e for e in trace["errors"] if e.get("agent_name") == "route"]
    assert len(router_errors) >= 1
    err = router_errors[0]
    assert err["recovered"] is False
    assert "11434" in err.get("target_host_port", "") or "11434" in err["error_message"]

    assert result.router_decision.fallback_used is True
    assert result.router_decision.low_confidence is True


# ---------------------------------------------------------------------------
# 4. 'recovered' Flag & determine_execution_status Unit Tests
# ---------------------------------------------------------------------------

def test_recovered_semantics_and_status():
    """
    Verifies determine_execution_status rules:
    - No errors, no fallbacks -> 'success'
    - Retried and recovered errors -> 'success'
    - Unrecovered error -> 'degraded: <agent>'
    - match_unavailable=True -> 'degraded: match'
    - fallback_used=True -> 'degraded: router'
    """
    # Case 1: Pure success
    assert determine_execution_status(["route", "match", "synthesize"], []) == "success"

    # Case 2: Transient error that was marked recovered
    err_recovered = [
        {"agent_name": "match", "step": "MATCH", "error_message": "timeout", "recovered": True}
    ]
    assert determine_execution_status(["route", "match", "synthesize"], err_recovered) == "success"

    # Case 3: Unrecovered error
    err_unrecovered = [
        {"agent_name": "match", "step": "MATCH", "error_message": "db error", "recovered": False}
    ]
    assert determine_execution_status(
        ["route", "match", "synthesize"], err_unrecovered
    ) == "degraded: match"

    # Case 4: match_unavailable flag
    assert determine_execution_status(
        ["route", "match", "synthesize"], [], match_unavailable=True
    ) == "degraded: match"

    # Case 5: router fallback used
    assert determine_execution_status(
        ["route", "match", "synthesize"], [], fallback_used=True
    ) == "degraded: router"

    # Test _mark_recovered helper
    errors = [
        {"agent_name": "match", "recovered": False},
        {"agent_name": "parse", "recovered": False},
    ]
    _mark_recovered(errors, "match")
    assert errors[0]["recovered"] is True
    assert errors[1]["recovered"] is False


# ---------------------------------------------------------------------------
# 5. Static AST / Code Audit: No Unranked select(JobPosting).limit
# ---------------------------------------------------------------------------

def test_no_unranked_job_posting_limit():
    """
    Ensures that no code in graph_orchestrator.py or router_service.py
    calls select(JobPosting).limit(...) without an order_by clause.
    """
    target_files = [
        "app/services/graph_orchestrator.py",
        "app/services/router_service.py",
    ]

    for filepath in target_files:
        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()

        # Check for unranked select(JobPosting).limit(4)
        pattern = r"select\s*\(\s*JobPosting\s*\)\s*\.limit\s*\("
        matches = re.findall(pattern, code)
        assert len(matches) == 0, (
            f"Found unranked select(JobPosting).limit in {filepath}. "
            f"Matches: {matches}. All job limits must use similarity/scoring ranking."
        )
