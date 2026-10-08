"""Unit and integration tests for GraphService (Neo4j)."""

import pytest
from unittest.mock import AsyncMock, patch

from app.schemas.graph import (
    CareerPathwayResponse,
    GraphNodeStats,
    GraphRelStats,
    GraphStatsResponse,
    SkillBridgeResponse,
)
from app.services.graph_service import GraphService, _clean_skills


def test_clean_skills_filters_categories_and_dupes():
    raw = ["Python", "python", "IT", "HCPR", "FastAPI", "  ", "Docker", "ENG"]
    cleaned = _clean_skills(raw)
    assert "Python" in cleaned
    assert "FastAPI" in cleaned
    assert "Docker" in cleaned
    assert "IT" not in cleaned
    assert "HCPR" not in cleaned
    assert "ENG" not in cleaned
    assert len(cleaned) == 3


@pytest.mark.asyncio
async def test_sync_candidate_cypher():
    service = GraphService()
    with patch("app.services.graph_service.execute_cypher", new_callable=AsyncMock) as mock_cypher:
        mock_cypher.return_value = [{"candidate_id": "c-123", "skills_linked": 3}]
        res = await service.sync_candidate(
            candidate_id="c-123",
            name="Alex Chen",
            email="alex@test.com",
            skills=["Python", "FastAPI", "PostgreSQL"],
        )
        assert res["candidate_id"] == "c-123"
        assert res["skills_linked"] == 3
        mock_cypher.assert_called_once()
        args = mock_cypher.call_args[0]
        assert "MERGE (c:Candidate" in args[0]
        assert args[1]["candidate_id"] == "c-123"
        assert "Python" in args[1]["skills"]


@pytest.mark.asyncio
async def test_sync_job_posting_cypher():
    service = GraphService()
    with patch("app.services.graph_service.execute_cypher", new_callable=AsyncMock) as mock_cypher:
        mock_cypher.return_value = [{"job_id": "j-456", "skills_linked": 2}]
        res = await service.sync_job_posting(
            job_id="j-456",
            title="Senior Backend Engineer",
            company_name="Acme Corp",
            location="Remote",
            work_type="Full-time",
            salary=160000.0,
            skills=["Python", "Docker"],
        )
        assert res["job_id"] == "j-456"
        mock_cypher.assert_called_once()
        args = mock_cypher.call_args[0]
        assert "MERGE (j:JobPosting" in args[0]
        assert "POSTED_BY" in args[0]
        assert args[1]["company_name"] == "Acme Corp"


@pytest.mark.asyncio
async def test_record_match_cypher():
    service = GraphService()
    with patch("app.services.graph_service.execute_cypher", new_callable=AsyncMock) as mock_cypher:
        mock_cypher.return_value = []
        await service.record_match(
            candidate_id="c-123",
            job_id="j-456",
            score=0.89,
            composite_score=0.85,
            xgboost_score=0.92,
            rank=1,
        )
        mock_cypher.assert_called_once()
        args = mock_cypher.call_args[0]
        assert "MERGE (c)-[r:MATCHED_TO]->(j)" in args[0]
        assert args[1]["score"] == 0.89
        assert args[1]["rank"] == 1


@pytest.mark.asyncio
async def test_get_graph_stats():
    service = GraphService()
    with patch("app.services.graph_service.execute_cypher", new_callable=AsyncMock) as mock_cypher:
        mock_cypher.side_effect = [
            [{"candidates": 5, "skills": 50, "job_postings": 20, "companies": 15}],
            [{"has_skill": 25, "requires": 80, "matched_to": 10, "posted_by": 20}],
        ]
        stats = await service.get_graph_stats()
        assert stats.total_nodes == 90
        assert stats.total_relationships == 135
        assert stats.nodes.candidates == 5
        assert stats.nodes.skills == 50
        assert stats.relationships.matched_to == 10


@pytest.mark.asyncio
async def test_find_bridge_skills_empty():
    service = GraphService()
    with patch("app.services.graph_service.execute_cypher", new_callable=AsyncMock) as mock_cypher:
        mock_cypher.return_value = [{"fromSkills": [], "fromCount": 0, "toSkills": [], "toCount": 0}]
        res = await service.find_bridge_skills("Astronomer", "Chef")
        assert res.from_postings_found == 0
        assert res.to_postings_found == 0
        assert res.shared_foundation_skills == []
        assert res.transition_overlap_pct == 0.0


@pytest.mark.asyncio
async def test_find_bridge_skills_populated():
    service = GraphService()
    with patch("app.services.graph_service.execute_cypher", new_callable=AsyncMock) as mock_cypher:
        mock_cypher.side_effect = [
            [{
                "fromSkills": ["Python", "SQL", "FastAPI", "Docker"],
                "fromCount": 10,
                "toSkills": ["Python", "SQL", "PyTorch", "Machine Learning"],
                "toCount": 8,
            }],
            [{"skill": "Pandas", "co_occurs": 5}],
        ]
        res = await service.find_bridge_skills("Backend Engineer", "Data Scientist")
        assert res.from_postings_found == 10
        assert res.to_postings_found == 8
        assert "Python" in res.shared_foundation_skills
        assert "SQL" in res.shared_foundation_skills
        assert "PyTorch" in res.target_role_skills
        assert "Pandas" in res.stepping_stone_bridge_skills
        assert res.transition_overlap_pct > 0.0
