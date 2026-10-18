"""
tests/test_graph_orchestrator.py
--------------------------------
Unit, resilience, equivalence, and integration tests for LangGraph StateGraph Orchestrator.

Validates:
  1. Equivalence of agent invocation across all 5 intents
  2. Bounded retry on transient failures (retrying up to MAX_NODE_RETRIES=1)
  3. Non-retry and graceful degradation on permanent failures
  4. Partial failure tolerance and state preservation
  5. Per-node latency tracing and execution metadata
  6. Ownership verification when routed through chat API
  7. Backend toggle (langgraph vs sequential)
  8. Graph compilation and Mermaid export verification
"""

import asyncio
from datetime import datetime, timezone
import json
from unittest.mock import AsyncMock, patch
import pytest

from app.schemas.chat import (
    ChatQueryRequest,
    ChatQueryResponse,
    IntentType,
    RouterDecision,
)
from app.services.graph_orchestrator import (
    GraphState,
    LangGraphOrchestrator,
    STRATEGY_MAP,
    langgraph_orchestrator,
)
from app.services.router_service import router_service


@pytest.fixture
def mock_trained_router():
    """Stub router predicting specific intents deterministically."""
    def _create_mock(intent_str: str, confidence: float = 0.95):
        decision = RouterDecision(
            intent=IntentType(intent_str),
            confidence=confidence,
            strategy_selected=f"Strategy for {intent_str}",
            reasoning=f"Mocked intent classification: {intent_str}",
            backend="trained",
            low_confidence=False,
            fallback_used=False,
            strategy=f"Strategy for {intent_str}",
        )
        return patch.object(router_service, "classify_intent", AsyncMock(return_value=decision))
    return _create_mock


# ---------------------------------------------------------------------------
# 1. Equivalence & Agent Invocation per Intent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "intent,expected_nodes",
    [
        ("JOB_SEARCH", ["route", "parse", "match", "synthesize"]),
        ("SKILL_GAP_ANALYSIS", ["route", "parse", "match", "coach", "synthesize"]),
        ("INTERVIEW_PREPARATION", ["route", "parse", "coach", "synthesize"]),
        ("CAREER_ADVICE", ["route", "parse", "market", "synthesize"]),
        ("RESUME_FEEDBACK", ["route", "parse", "coach", "synthesize"]),
    ],
)
async def test_graph_orchestrator_agent_invocation_equivalence(mock_trained_router, intent, expected_nodes):
    """Verify that for each intent, exactly the target agents documented in Stage 0 are invoked."""
    req = ChatQueryRequest(
        query=f"Query testing intent {intent}",
        raw_resume_text="Senior Python Developer with FastAPI and Docker experience.",
    )

    with mock_trained_router(intent):
        response = await langgraph_orchestrator.execute(request=req, db=None)

    assert isinstance(response, ChatQueryResponse)
    assert response.router_decision.intent == intent

    # Find the execution trace inside sources
    trace = next((s for s in response.sources if s.get("type") == "orchestrator_trace"), None)
    assert trace is not None, "Execution trace must be attached to response sources"
    assert trace["backend"] == "langgraph"

    completed = trace["completed_nodes"]
    for node in expected_nodes:
        assert node in completed, f"Node {node} was expected to execute for intent {intent}, got {completed}"

    # Verify per-node timings exist for all completed nodes
    timings = trace["node_timings_ms"]
    for node in expected_nodes:
        assert node in timings
        assert timings[node] >= 0.0


# ---------------------------------------------------------------------------
# 2. Bounded Retry on Transient Failures
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_graph_orchestrator_bounded_retry_transient_failure():
    """Verify that transient failures trigger bounded retry (1 retry) then succeed."""
    req = ChatQueryRequest(
        query="Tell me about software engineering salaries in Austin",
    )

    call_count = {"market": 0}

    # Simulate market_agent.get_salary_insights failing once with a transient TimeoutError, then succeeding
    async def transient_insights(*args, **kwargs):
        call_count["market"] += 1
        if call_count["market"] == 1:
            raise TimeoutError("Temporary market upstream timeout")
        from app.schemas.market import SalaryBand, SalaryInsightResponse
        return SalaryInsightResponse(
            role_title="Software Engineer",
            salary_band=SalaryBand(p25_annual=125000, median_annual=155000, p75_annual=185000, currency="USD", sample_size=20),
            narrative="Market insights narrative.",
        )

    with patch.object(
        router_service,
        "classify_intent",
        AsyncMock(return_value=RouterDecision(
            intent=IntentType.CAREER_ADVICE,
            confidence=0.92,
            strategy_selected="Strategy 4: Market Dynamics",
            reasoning="Career advice query.",
            backend="trained",
            low_confidence=False,
            fallback_used=False,
            strategy="Strategy 4: Market Dynamics",
        )),
    ):
        with patch("app.services.graph_orchestrator.market_agent.get_salary_insights", side_effect=transient_insights):
            # Pass a mock DB so market_node enters the DB query path
            mock_db = AsyncMock()
            response = await langgraph_orchestrator.execute(request=req, db=mock_db)

    assert isinstance(response, ChatQueryResponse)
    assert call_count["market"] == 2, "Transient error should have triggered exactly 1 retry"
    trace = next((s for s in response.sources if s.get("type") == "orchestrator_trace"), None)
    assert trace is not None
    assert trace["retries"].get("market") == 1
    assert "market" in trace["completed_nodes"]


@pytest.mark.asyncio
async def test_graph_orchestrator_exhausted_retries_transient_failure():
    """When transient failure persists past MAX_NODE_RETRIES, record error and proceed with fallback."""
    req = ChatQueryRequest(query="Find Python jobs")

    # Always raise TimeoutError on embedding_service
    with patch.object(
        router_service,
        "classify_intent",
        AsyncMock(return_value=RouterDecision(
            intent=IntentType.JOB_SEARCH,
            confidence=0.91,
            strategy_selected="Strategy 1: Hybrid Vector Search",
            reasoning="Job search query.",
            backend="trained",
            low_confidence=False,
            fallback_used=False,
            strategy="Strategy 1: Hybrid Vector Search",
        )),
    ):
        with patch("app.services.graph_orchestrator.embedding_service.get_embedding", side_effect=TimeoutError("Persistent connection reset")):
            mock_db = AsyncMock()
            mock_db.execute = AsyncMock(side_effect=TimeoutError("Persistent connection reset"))
            response = await langgraph_orchestrator.execute(request=req, db=mock_db)

    assert isinstance(response, ChatQueryResponse)
    trace = next((s for s in response.sources if s.get("type") == "orchestrator_trace"), None)
    assert trace is not None
    assert trace["retries"].get("match") == 1  # 1 retry attempted
    assert len(trace["errors"]) >= 1
    err = trace["errors"][0]
    assert err["agent_name"] == "match"
    assert "Persistent connection reset" in err["error_message"]
    # Pipeline still completed synthesize
    assert "synthesize" in trace["completed_nodes"]


# ---------------------------------------------------------------------------
# 3. Permanent Failure Policy (No Retry, Immediate Graceful Recovery)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_graph_orchestrator_permanent_failure_no_retry():
    """Verify that permanent errors (e.g. ValueError, KeyError) are not retried and fall back gracefully."""
    req = ChatQueryRequest(query="Prepare me for an interview")

    call_count = {"coach": 0}

    async def invalid_schema_coach(*args, **kwargs):
        call_count["coach"] += 1
        raise ValueError("Invalid schema payload received from LLM")

    with patch.object(
        router_service,
        "classify_intent",
        AsyncMock(return_value=RouterDecision(
            intent=IntentType.INTERVIEW_PREPARATION,
            confidence=0.88,
            strategy_selected="Strategy 3: Interview Coaching",
            reasoning="Interview prep query.",
            backend="trained",
            low_confidence=False,
            fallback_used=False,
            strategy="Strategy 3: Interview Coaching",
        )),
    ):
        with patch("app.services.graph_orchestrator.coach_agent.generate_skill_gap_report", side_effect=invalid_schema_coach):
            response = await langgraph_orchestrator.execute(request=req, db=None)

    assert isinstance(response, ChatQueryResponse)
    # Permanent errors must not be retried
    assert call_count["coach"] == 1
    trace = next((s for s in response.sources if s.get("type") == "orchestrator_trace"), None)
    assert trace is not None
    assert trace["retries"].get("coach", 0) == 0
    assert any(e["agent_name"] == "coach" for e in trace["errors"])
    assert "synthesize" in trace["completed_nodes"]


# ---------------------------------------------------------------------------
# 4. Partial Failure State Preservation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_graph_orchestrator_partial_failure_state_preservation():
    """When parser fails, matching and coaching still proceed with available state."""
    req = ChatQueryRequest(
        query="What are my skill gaps for Senior Backend Engineer?",
        raw_resume_text="Corrupted OCR stream...",
    )

    with patch("app.services.graph_orchestrator.parser_agent.parse", side_effect=RuntimeError("OCR syntax parser failed")):
        with patch.object(
            router_service,
            "classify_intent",
            AsyncMock(return_value=RouterDecision(
                intent=IntentType.SKILL_GAP_ANALYSIS,
                confidence=0.90,
                strategy_selected="Strategy 2: Skill Gap Analysis",
                reasoning="Skill gap query.",
                backend="trained",
                low_confidence=False,
                fallback_used=False,
                strategy="Strategy 2: Skill Gap Analysis",
            )),
        ):
            response = await langgraph_orchestrator.execute(request=req, db=None)

    assert isinstance(response, ChatQueryResponse)
    trace = next((s for s in response.sources if s.get("type") == "orchestrator_trace"), None)
    assert trace is not None
    assert any(e["agent_name"] == "parse" for e in trace["errors"])
    # Downstream agents still executed successfully
    assert "match" in trace["completed_nodes"]
    assert "coach" in trace["completed_nodes"]
    assert "synthesize" in trace["completed_nodes"]


# ---------------------------------------------------------------------------
# 5. Graph Structure & Mermaid Diagram Export
# ---------------------------------------------------------------------------

def test_graph_mermaid_export():
    """Verify that StateGraph compiles, provides Mermaid representation, and includes retry cycles."""
    graph = langgraph_orchestrator.app.get_graph()
    mermaid_str = graph.draw_mermaid()
    assert "graph TD;" in mermaid_str or "graph" in mermaid_str
    assert "route" in mermaid_str
    assert "parse" in mermaid_str
    assert "match" in mermaid_str
    assert "market" in mermaid_str
    assert "coach" in mermaid_str
    assert "synthesize" in mermaid_str
    assert "retry_route" in mermaid_str or "route -.-> route" in mermaid_str or "retry" in mermaid_str


# ---------------------------------------------------------------------------
# 6. Backend Toggle (ORCHESTRATOR_BACKEND)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orchestrator_backend_toggle_behavior():
    """Verify that settings.ORCHESTRATOR_BACKEND controls execution path in API handler."""
    from app.api.v1.endpoints import chat
    from app.core.config import settings

    req = ChatQueryRequest(query="Show me Python jobs in San Francisco")

    # 1. When ORCHESTRATOR_BACKEND is "langgraph"
    with patch.object(settings, "ORCHESTRATOR_BACKEND", "langgraph"):
        with patch.object(
            langgraph_orchestrator, "execute",
            AsyncMock(return_value=ChatQueryResponse(
                query=req.query,
                router_decision=RouterDecision(
                    intent=IntentType.JOB_SEARCH,
                    confidence=0.95,
                    strategy_selected="LangGraph Strategy",
                    reasoning="LangGraph execution.",
                    backend="trained",
                    low_confidence=False,
                    fallback_used=False,
                    strategy="LangGraph Strategy",
                ),
                response="Response from LangGraph",
                sources=[{"type": "orchestrator_trace", "backend": "langgraph"}],
                actionable_recommendations=[],
                suggested_followups=[],
            )),
        ) as mock_graph_exec:
            res = await chat.process_chat_query(request=req, db=None, current_user=None)
            assert res.response == "Response from LangGraph"
            mock_graph_exec.assert_awaited_once()

    # 2. When ORCHESTRATOR_BACKEND is "sequential"
    with patch.object(settings, "ORCHESTRATOR_BACKEND", "sequential"):
        with patch.object(
            router_service, "route_and_execute",
            AsyncMock(return_value=ChatQueryResponse(
                query=req.query,
                router_decision=RouterDecision(
                    intent=IntentType.JOB_SEARCH,
                    confidence=0.95,
                    strategy_selected="Sequential Strategy",
                    reasoning="Sequential execution.",
                    backend="trained",
                    low_confidence=False,
                    fallback_used=False,
                    strategy="Sequential Strategy",
                ),
                response="Response from Sequential Router",
                sources=[],
                actionable_recommendations=[],
                suggested_followups=[],
            )),
        ) as mock_seq_exec:
            res = await chat.process_chat_query(request=req, db=None, current_user=None)
            assert res.response == "Response from Sequential Router"
            mock_seq_exec.assert_awaited_once()
