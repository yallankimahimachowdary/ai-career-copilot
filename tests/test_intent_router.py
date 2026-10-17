"""
tests/test_intent_router.py
---------------------------
Unit and evaluation tests for Query-Intent Router across 5 career copilot intents:
- job_search
- skill_gap_analysis
- resume_feedback
- career_advice
- interview_preparation
"""

import pytest
from app.schemas.chat import ChatQueryRequest, IntentType
from app.services.intent_router_eval import evaluate_intent_benchmark, to_canonical_intent
from app.services.router_service import router_service


@pytest.mark.asyncio
async def test_intent_router_benchmark_performance():
    """Verify that query intent router achieves high accuracy and macro-F1 across 5 intents."""
    report = await evaluate_intent_benchmark(
        benchmark_path="data/evaluation/query_intent_benchmark_v1.json",
        use_llm=False,
    )

    summary = report["summary"]
    assert summary["accuracy"] >= 0.90, f"Expected accuracy >= 0.90, got {summary['accuracy']}"
    assert summary["macro_f1"] >= 0.90, f"Expected macro_f1 >= 0.90, got {summary['macro_f1']}"
    assert summary["total_count"] == 50

    per_intent = report["per_intent"]
    for intent_name, metrics in per_intent.items():
        assert metrics["support"] == 10
        assert metrics["precision"] >= 0.80, f"Precision below 0.80 for {intent_name}"
        assert metrics["recall"] >= 0.80, f"Recall below 0.80 for {intent_name}"
        assert metrics["f1_score"] >= 0.80, f"F1 below 0.80 for {intent_name}"


@pytest.mark.asyncio
async def test_resume_feedback_intent_routing():
    """Verify resume feedback queries route to RESUME_FEEDBACK and produce tailored critiques."""
    decision = await router_service.classify_intent(
        "Please review my resume bullet points and check ATS formatting.",
        use_llm=False,
    )
    assert decision.intent == IntentType.RESUME_FEEDBACK
    assert decision.confidence >= 0.85
    assert to_canonical_intent(decision.intent) == "resume_feedback"


@pytest.mark.asyncio
async def test_resume_feedback_execution_without_resume():
    """Verify execution of resume feedback strategy when candidate has no uploaded resume."""
    from unittest.mock import AsyncMock

    mock_db = AsyncMock()
    req = ChatQueryRequest(query="How can I rewrite my experience bullet points?")
    decision = await router_service.classify_intent(req.query, use_llm=False)

    resp = await router_service.route_and_execute(db=mock_db, request=req, use_llm=False)
    assert resp.router_decision.intent == IntentType.RESUME_FEEDBACK
    assert len(resp.actionable_recommendations) >= 3
    assert len(resp.suggested_followups) >= 2
    assert "XYZ formula" in resp.response or "bullet" in resp.response.lower()


def test_to_canonical_intent_mapping():
    """Verify normalization of intent enum values and string variants."""
    assert to_canonical_intent(IntentType.JOB_SEARCH_AND_MATCH) == "job_search"
    assert to_canonical_intent(IntentType.SKILL_PROGRESSION_AND_PATH) == "skill_gap_analysis"
    assert to_canonical_intent(IntentType.RESUME_FEEDBACK) == "resume_feedback"
    assert to_canonical_intent(IntentType.MACRO_MARKET_DYNAMICS) == "career_advice"
    assert to_canonical_intent(IntentType.INTERVIEW_COACHING) == "interview_preparation"
    assert to_canonical_intent("job-search") == "job_search"
