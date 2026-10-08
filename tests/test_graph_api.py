"""Integration tests for Graph API endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

from app.main import app
from app.schemas.graph import (
    CareerPathwayResponse,
    CareerPathwaySkillItem,
    GraphNodeStats,
    GraphRelStats,
    GraphStatsResponse,
    ReachableRoleItem,
    SkillBridgeResponse,
)


@pytest.mark.asyncio
async def test_get_graph_stats_api():
    mock_stats = GraphStatsResponse(
        total_nodes=100,
        total_relationships=250,
        nodes=GraphNodeStats(candidates=10, skills=40, job_postings=30, companies=20),
        relationships=GraphRelStats(has_skill=50, requires=150, matched_to=25, posted_by=25),
    )
    with patch("app.api.v1.endpoints.graph.graph_service.get_graph_stats", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_stats
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/graph/stats")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_nodes"] == 100
            assert data["nodes"]["candidates"] == 10
            assert data["relationships"]["has_skill"] == 50


@pytest.mark.asyncio
async def test_get_bridge_skills_api():
    mock_bridge = SkillBridgeResponse(
        from_role="Frontend Engineer",
        to_role="Full Stack Engineer",
        from_postings_found=15,
        to_postings_found=20,
        shared_foundation_skills=["JavaScript", "React"],
        stepping_stone_bridge_skills=["TypeScript", "GraphQL"],
        target_role_skills=["Node.js", "PostgreSQL"],
        transition_overlap_pct=50.0,
        recommended_learning_order=["TypeScript", "Node.js"],
        bridge_summary="Strong shared foundation in JavaScript and React.",
    )
    with patch("app.api.v1.endpoints.graph.graph_service.find_bridge_skills", new_callable=AsyncMock) as mock_bridge_fn:
        mock_bridge_fn.return_value = mock_bridge
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/graph/bridge-skills",
                params={"from_role": "Frontend Engineer", "to_role": "Full Stack Engineer"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["from_role"] == "Frontend Engineer"
            assert "JavaScript" in data["shared_foundation_skills"]
            assert data["transition_overlap_pct"] == 50.0


@pytest.mark.asyncio
async def test_get_career_pathway_api():
    mock_pathway = CareerPathwayResponse(
        candidate_id="c-999",
        candidate_name="Jane Doe",
        current_skills_count=4,
        current_skills=["Python", "SQL", "Docker", "Git"],
        high_leverage_bridge_skills=[
            CareerPathwaySkillItem(
                skill="Kubernetes",
                co_occurring_with_candidate_skills=3,
                unlocks_postings_count=12,
                demand_weight=15.6,
            )
        ],
        reachable_roles=[
            ReachableRoleItem(
                job_id="j-101",
                title="DevOps Engineer",
                company="TechCorp",
                matched_skills=["Docker", "Git", "Python"],
                missing_bridge_skills=["Kubernetes", "Terraform"],
                readiness_pct=60.0,
            )
        ],
        graph_insight="Kubernetes unlocks 12 additional postings.",
    )
    with patch("app.api.v1.endpoints.graph.graph_service.find_candidate_career_pathway", new_callable=AsyncMock) as mock_p:
        mock_p.return_value = mock_pathway
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/graph/career-pathway/c-999")
            assert resp.status_code == 200
            data = resp.json()
            assert data["candidate_id"] == "c-999"
            assert len(data["high_leverage_bridge_skills"]) == 1
            assert data["high_leverage_bridge_skills"][0]["skill"] == "Kubernetes"
