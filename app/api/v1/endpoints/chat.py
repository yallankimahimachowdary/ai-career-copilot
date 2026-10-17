"""
app/api/v1/endpoints/chat.py
----------------------------
API Routes for the Adaptive Query Intent Router and RAG Chat Assistant.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import enforce_resume_ownership, get_current_user
from app.db.session import get_db
from app.models.resume import Resume
from app.models.user import User
from app.schemas.chat import (
    ChatQueryRequest,
    ChatQueryResponse,
    RouterDecision,
)
from app.services.router_service import router_service

router = APIRouter()


@router.post(
    "/query",
    response_model=ChatQueryResponse,
    summary="Process Career Query via Adaptive Intent Router",
    description=(
        "Core Adaptive RAG endpoint. Classifies student query into one of 4 strategies "
        "(Job Search & Match, Skill Progression, Interview Coaching, or Macro Market Dynamics), "
        "executes targeted retrieval, and returns an explainable multi-agent response."
    ),
)
async def process_chat_query(
    request: ChatQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatQueryResponse:
    if request.resume_id:
        res_obj = await db.get(Resume, request.resume_id)
        if not res_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Resume {request.resume_id} not found.",
            )
        enforce_resume_ownership(res_obj, current_user)

    try:
        return await router_service.route_and_execute(db=db, request=request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Adaptive router execution error: {str(exc)}",
        )


@router.post(
    "/classify-intent",
    response_model=RouterDecision,
    summary="Diagnostic: Classify Query Intent Only",
    description="Returns the classified intent enum, confidence score, and strategy justification without executing full retrieval.",
)
async def classify_query_intent(
    request: ChatQueryRequest,
    current_user: User = Depends(get_current_user),
) -> RouterDecision:
    try:
        return await router_service.classify_intent(query=request.query)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Intent classification failed: {str(exc)}",
        )

