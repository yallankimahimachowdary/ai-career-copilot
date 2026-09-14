"""
app/schemas/chat.py
-------------------
Pydantic Schemas for the Adaptive Query Intent Router and RAG Chat Assistant.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class IntentType(str, Enum):
    JOB_SEARCH_AND_MATCH = "JOB_SEARCH_AND_MATCH"
    SKILL_PROGRESSION_AND_PATH = "SKILL_PROGRESSION_AND_PATH"
    INTERVIEW_COACHING = "INTERVIEW_COACHING"
    MACRO_MARKET_DYNAMICS = "MACRO_MARKET_DYNAMICS"


class RouterDecision(BaseModel):
    intent: IntentType = Field(
        ...,
        description="Identified candidate intent classified by the Adaptive Query Router."
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model or heuristic confidence score for the routing classification."
    )
    strategy_selected: str = Field(
        ...,
        description="Specific retrieval and orchestration strategy executed."
    )
    reasoning: str = Field(
        ...,
        description="Transparent justification of why this retrieval strategy was selected."
    )


class ChatQueryRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=2,
        description="Candidate question or prompt (e.g. 'What skills do I need for Stripe backend role?')"
    )
    resume_id: Optional[str] = Field(
        default=None,
        description="Active resume ID for personalizing the retrieval context."
    )
    job_id: Optional[str] = Field(
        default=None,
        description="Optional target job ID context."
    )
    history: Optional[List[Dict[str, str]]] = Field(
        default_factory=list,
        description="Prior conversational turns [{'role': 'user'|'assistant', 'content': '...'}]"
    )


class ChatQueryResponse(BaseModel):
    query: str
    router_decision: RouterDecision
    response: str
    sources: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list,
        description="Retrieved job postings, market percentiles, or question bank references."
    )
    actionable_recommendations: Optional[List[str]] = Field(
        default_factory=list,
        description="Direct next steps or actionable items for the candidate."
    )
    suggested_followups: List[str] = Field(
        default_factory=list,
        description="Recommended follow-up questions tailored to the classified intent."
    )
