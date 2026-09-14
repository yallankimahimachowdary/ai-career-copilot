"""
tests/test_router.py
--------------------
Unit tests for the Adaptive Query Intent Router and Domain Taxonomy Preprocessing.
"""

import pytest
from app.core.taxonomy import (
    extract_canonical_skills,
    filter_category_codes,
    is_category_code,
)
from app.schemas.chat import IntentType
from app.services.router_service import router_service


def test_taxonomy_category_code_filtering():
    """Verify that LinkedIn noise codes (ENG, QA, MGMT) are correctly identified and removed."""
    raw_tokens = ["Python", "ENG", "FastAPI", "QA", "Docker", "MGMT", "SQL", "C"]
    
    assert is_category_code("ENG") is True
    assert is_category_code("QA") is True
    assert is_category_code("Python") is False

    cleaned = filter_category_codes(raw_tokens)
    assert "ENG" not in cleaned
    assert "QA" not in cleaned
    assert "MGMT" not in cleaned
    assert "Python" in cleaned
    assert "FastAPI" in cleaned
    assert "Docker" in cleaned
    assert "SQL" in cleaned


def test_taxonomy_skill_extraction():
    """Verify regex boundary skill extraction from free text."""
    sample_text = (
        "Seeking a Senior Python Backend Developer with extensive FastAPI, PostgreSQL, "
        "and Docker experience. Familiarity with AWS and Kubernetes is a plus."
    )
    skills = extract_canonical_skills(sample_text)
    
    assert "Python" in skills
    assert "FastAPI" in skills
    assert "SQL" in skills
    assert "Docker" in skills
    assert "AWS" in skills
    assert "Kubernetes" in skills


@pytest.mark.asyncio
async def test_router_classification_market():
    """Verify that salary and compensation queries route to MACRO_MARKET_DYNAMICS."""
    queries = [
        "What is the average salary for a Senior Software Engineer in San Francisco?",
        "What are the compensation percentiles for Python backend roles?",
        "Which market locations have the highest median pay?",
    ]
    for q in queries:
        decision = await router_service.classify_intent(q)
        assert decision.intent == IntentType.MACRO_MARKET_DYNAMICS
        assert decision.confidence >= 0.80


@pytest.mark.asyncio
async def test_router_classification_interview():
    """Verify that interview prep queries route to INTERVIEW_COACHING."""
    queries = [
        "Can you ask me a senior backend interview question to practice?",
        "How should I structure my STAR behavioral answer for a team conflict question?",
        "Give me technical interview questions on Python asyncio and connection pools.",
    ]
    for q in queries:
        decision = await router_service.classify_intent(q)
        assert decision.intent == IntentType.INTERVIEW_COACHING
        assert decision.confidence >= 0.80


@pytest.mark.asyncio
async def test_router_classification_skill_progression():
    """Verify that skill gaps and roadmap queries route to SKILL_PROGRESSION_AND_PATH."""
    queries = [
        "What skills do I need to learn to transition to an AI Systems Engineer?",
        "Can you build a 10-day learning roadmap for mastering Kafka and Kubernetes?",
        "What are my critical skill gaps for the Stripe Backend Engineer role?",
    ]
    for q in queries:
        decision = await router_service.classify_intent(q)
        assert decision.intent == IntentType.SKILL_PROGRESSION_AND_PATH
        assert decision.confidence >= 0.80


@pytest.mark.asyncio
async def test_router_classification_job_search():
    """Verify that job recommendation queries route to JOB_SEARCH_AND_MATCH."""
    queries = [
        "Find me remote software engineer jobs matching my resume qualifications.",
        "Show me open vacancies at Stripe or Databricks for Python developers.",
        "What roles do I qualify for right now?",
    ]
    for q in queries:
        decision = await router_service.classify_intent(q)
        assert decision.intent == IntentType.JOB_SEARCH_AND_MATCH
        assert decision.confidence >= 0.80
