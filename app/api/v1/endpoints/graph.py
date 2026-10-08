"""Neo4j Knowledge Graph API endpoints — Sprint Graph Integration."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.db.session import get_db
from app.schemas.graph import (
    CareerPathwayResponse,
    GraphStatsResponse,
    GraphSyncResponse,
    SkillBridgeResponse,
)
from app.services.graph_service import graph_service

router = APIRouter()


@router.get(
    "/stats",
    response_model=GraphStatsResponse,
    summary="Get Graph Database Metrics",
    description="Returns aggregate counts of nodes (Candidate, Skill, JobPosting, Company) and relationships (HAS_SKILL, REQUIRES, MATCHED_TO, POSTED_BY) currently in Neo4j.",
)
async def get_graph_stats() -> GraphStatsResponse:
    try:
        return await graph_service.get_graph_stats()
    except Exception as exc:
        logger.error(f"Failed to fetch Neo4j graph stats: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query graph statistics: {str(exc)}",
        )


@router.get(
    "/bridge-skills",
    response_model=SkillBridgeResponse,
    summary="Find Skills Bridging Two Roles",
    description=(
        "Executes a graph query to find foundational overlap, intermediate stepping-stone skills, "
        "and target delta requirements between two distinct role titles (e.g. 'Software Engineer' and 'Data Scientist')."
    ),
)
async def get_bridge_skills(
    from_role: str = Query(..., min_length=2, description="Source or current role title (e.g. 'Frontend Engineer')"),
    to_role: str = Query(..., min_length=2, description="Target or aspirational role title (e.g. 'Machine Learning Engineer')"),
) -> SkillBridgeResponse:
    try:
        return await graph_service.find_bridge_skills(from_role=from_role, to_role=to_role)
    except Exception as exc:
        logger.error(f"Failed to compute graph bridge skills between '{from_role}' and '{to_role}': {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Graph bridging query failed: {str(exc)}",
        )


@router.get(
    "/career-pathway/{candidate_id}",
    response_model=CareerPathwayResponse,
    summary="Graph-Powered Candidate Skill Pathway & Reachable Roles",
    description=(
        "Traverses 2-hop graph relationships ((Candidate)-[:HAS_SKILL]->(Skill)<-[:REQUIRES]-(Job)-[:REQUIRES]->(BridgeSkill)) "
        "to discover high-leverage skills that unlock the most industry opportunities, along with reachable roles and readiness %."
    ),
)
async def get_career_pathway(
    candidate_id: str,
) -> CareerPathwayResponse:
    try:
        return await graph_service.find_candidate_career_pathway(candidate_id=candidate_id)
    except Exception as exc:
        logger.error(f"Failed to compute career pathway for candidate '{candidate_id}': {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Career pathway query failed: {str(exc)}",
        )


@router.post(
    "/sync-all-jobs",
    response_model=GraphSyncResponse,
    summary="Batch Synchronize PostgreSQL Jobs to Neo4j",
    description="Loads all existing job postings and their extracted skills from PostgreSQL into Neo4j graph nodes and relationships.",
)
async def sync_all_jobs(
    db: AsyncSession = Depends(get_db),
) -> GraphSyncResponse:
    try:
        synced_count = await graph_service.sync_all_existing_jobs(db=db)
        stats = await graph_service.get_graph_stats()
        return GraphSyncResponse(
            status="success",
            synced_jobs_count=synced_count,
            total_skills_count=stats.nodes.skills,
            message=f"Successfully synchronized {synced_count} job postings. Graph now contains {stats.total_nodes} nodes and {stats.total_relationships} relationships.",
        )
    except Exception as exc:
        logger.error(f"Failed to synchronize jobs to Neo4j: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job synchronization failed: {str(exc)}",
        )
