"""
tests/test_data_layer.py
-------------------------
Comprehensive test suite for Phase R5 Data Layer:
  1. Role graph (Neo4j Role nodes, LEADS_TO progression paths, OFFERS edges).
  2. Database tables (evaluation_logs, learning_resources, job_market_trends).
  3. Curated seed datasets (role_graph_seed.json, learning_resources_seed.json, interview_corpus_v1.jsonl).
  4. Idempotent loaders & validation (dataset SHA-256 enforcement, constraints).
  5. API endpoints and service wiring (role pathways, learning resource attachment, dynamic velocity, Chroma interview retrieval).
"""

import asyncio
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.api.deps import get_current_user, get_db
from app.core.security import create_access_token
from app.db.chroma import get_interview_material_collection
from app.db.neo4j import execute_cypher
from app.db.session import AsyncSessionLocal, engine
from app.main import app
from app.models.evaluation_log import EvaluationLog
from app.models.job_market_trend import JobMarketTrend
from app.models.job_posting import JobPosting
from app.models.learning_resource import LearningResource
from app.models.resume import Resume
from app.models.user import User
from app.schemas.coach import CoachQuestionBankRequest, ResourceItem, SkillGapItem, SkillGapReport
from app.schemas.graph import GraphStatsResponse, RoleProgressionResponse
from app.services.coach_service import _SKILL_PATTERNS, coach_agent
from app.services.graph_service import graph_service
from app.services.market_service import market_agent
from scripts.log_evaluation_result import _extract_dataset_sha256

CANONICAL_SKILLS = set(_SKILL_PATTERNS.keys())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
async def dispose_engine_after_test():
    """Ensure asyncpg connection pool is disposed so connections don't cross event loops."""
    yield
    await engine.dispose()


@pytest.fixture
def test_user():
    return User(
        id="test-data-layer-user-id",
        email="datalayer@example.com",
        full_name="Data Layer Tester",
        is_active=True,
        is_superuser=False,
    )


@pytest.fixture
def auth_headers(test_user):
    token = create_access_token(test_user.email, extra_claims={"id": test_user.id})
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Dataset Integrity Tests (No external service dependencies)
# ---------------------------------------------------------------------------

def test_role_graph_seed_dataset():
    """Verify role_graph_seed.json schema, canonical skills, and DAG structure."""
    seed_path = Path("data/graph/role_graph_seed.json")
    assert seed_path.exists(), "role_graph_seed.json must exist"

    with open(seed_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    roles = data.get("roles", [])
    assert len(roles) == 52, f"Expected 52 roles, found {len(roles)}"

    role_names = {r["name"] for r in roles}
    assert len(role_names) == 52, "All role names must be unique"

    edge_count = 0
    for r in roles:
        assert r.get("family") in {
            "core_engineering", "cloud_devops", "business_nontech", "web_software", "data_ai"
        }
        for sk in r.get("requires_skills", []):
            assert sk["name"] in CANONICAL_SKILLS, f"Skill '{sk['name']}' in role '{r['name']}' not canonical"
            assert sk.get("importance") in ("core", "nice", "essential")

        for edge in r.get("leads_to", []):
            edge_count += 1
            assert edge["target"] in role_names, f"Target role '{edge['target']}' not found in role names"
            assert edge["target"] != r["name"], f"Self-loop detected on role '{r['name']}'"

    assert edge_count >= 50, f"Expected >= 50 progression edges, found {edge_count}"


def test_learning_resources_seed_dataset():
    """Verify learning_resources_seed.json schema, canonical coverage, and active status."""
    seed_path = Path("data/learning/learning_resources_seed.json")
    assert seed_path.exists(), "learning_resources_seed.json must exist"

    with open(seed_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    resources = data.get("resources", [])
    assert len(resources) >= 70, f"Expected >= 70 learning resources, found {len(resources)}"

    for res in resources:
        assert res["skill_name"] in CANONICAL_SKILLS, f"Resource skill '{res['skill_name']}' not canonical"
        assert res.get("resource_type") in ("official_docs", "course", "book", "tutorial", "practice")
        assert res.get("difficulty") in ("beginner", "intermediate", "advanced")
        if res.get("url"):
            assert res["url"].startswith("http"), f"Invalid URL for '{res['title']}': {res['url']}"


def test_interview_corpus_seed_dataset():
    """Verify interview_corpus_v1.jsonl count, categories, key points, and metadata hash."""
    corpus_path = Path("data/interview_corpus/interview_corpus_v1.jsonl")
    meta_path = Path("data/interview_corpus/metadata.json")
    assert corpus_path.exists(), "interview_corpus_v1.jsonl must exist"
    assert meta_path.exists(), "metadata.json must exist"

    with open(corpus_path, "rb") as f:
        corpus_bytes = f.read()
    actual_sha = hashlib.sha256(corpus_bytes).hexdigest().upper()

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    assert meta.get("sha256") == actual_sha, "Corpus SHA-256 must match metadata"

    lines = corpus_bytes.decode("utf-8").strip().split("\n")
    items = [json.loads(line) for line in lines if line.strip()]
    assert len(items) >= 150, f"Expected >= 150 items, found {len(items)}"

    non_tech_count = 0
    for item in items:
        assert item.get("role_family") in {
            "core_engineering", "cloud_devops", "business_nontech", "web_software", "data_ai"
        }
        assert 3 <= len(item.get("key_points", [])) <= 6, f"Item {item['id']} must have 3-6 key points"
        assert item.get("difficulty") in ("junior", "mid", "senior", "lead")
        for tag in item.get("skill_tags", []):
            assert tag in CANONICAL_SKILLS, f"Skill tag '{tag}' not canonical in {item['id']}"
        if item.get("question_type") in ("behavioral", "situational", "hr"):
            non_tech_count += 1

    assert non_tech_count >= 20, f"Expected >= 20 behavioral/situational/HR questions, found {non_tech_count}"


def test_log_evaluation_result_strict_validation():
    """Verify _extract_dataset_sha256 strictly rejects missing or empty dataset SHA."""
    with pytest.raises(ValueError, match="dataset_sha256 is required"):
        _extract_dataset_sha256({})

    with pytest.raises(ValueError, match="dataset_sha256 is required"):
        _extract_dataset_sha256({"dataset_sha256": ""})

    with pytest.raises(ValueError, match="dataset_sha256 is required"):
        _extract_dataset_sha256({"split": {"sha256": "   "}})

    valid_sha = "6340BB8A778BDC19A65A7E72EEF8F771AD7AE4AC7A0889912DC50BC679335AD4"
    assert _extract_dataset_sha256({"dataset_sha256": valid_sha}) == valid_sha
    assert _extract_dataset_sha256({"split": {"sha256": valid_sha.lower()}}) == valid_sha


# ---------------------------------------------------------------------------
# 2. Database Constraint & Model Unit Tests (requires Postgres)
# ---------------------------------------------------------------------------

@pytest.mark.requires_postgres
@pytest.mark.asyncio
async def test_postgres_learning_resources_constraints():
    """Verify check constraints and unique constraints on learning_resources table."""
    async with AsyncSessionLocal() as session:
        # Invalid resource_type check constraint violation
        bad_resource = text("""
            INSERT INTO learning_resources (
                id, skill_name, title, provider, resource_type, difficulty, is_active, source
            ) VALUES (
                gen_random_uuid(), 'Python', 'Invalid Podcast Resource', 'Tester', 'podcast', 'beginner', true, 'curated_seed'
            )
        """)
        with pytest.raises(Exception):
            async with session.begin_nested():
                await session.execute(bad_resource)

        # Invalid difficulty check constraint violation
        bad_diff = text("""
            INSERT INTO learning_resources (
                id, skill_name, title, provider, resource_type, difficulty, is_active, source
            ) VALUES (
                gen_random_uuid(), 'Python', 'Master Level Resource', 'Tester', 'book', 'master', true, 'curated_seed'
            )
        """)
        with pytest.raises(Exception):
            async with session.begin_nested():
                await session.execute(bad_diff)


@pytest.mark.requires_postgres
@pytest.mark.asyncio
async def test_postgres_job_market_trends_constraints():
    """Verify check constraints and unique constraint on job_market_trends table."""
    async with AsyncSessionLocal() as session:
        # Invalid period_type check constraint violation (must be snapshot or month)
        bad_trend = text("""
            INSERT INTO job_market_trends (
                id, skill_name, period_start, period_end, period_type,
                postings_with_skill, total_postings, demand_share, source
            ) VALUES (
                gen_random_uuid(), 'Python', '2026-10-01', '2026-10-31', 'daily',
                10, 100, 10.0, 'derived_postings'
            )
        """)
        with pytest.raises(Exception):
            async with session.begin_nested():
                await session.execute(bad_trend)


@pytest.mark.requires_postgres
@pytest.mark.asyncio
async def test_postgres_learning_resources_retrieval():
    """Verify learning_resources rows exist, are queryable, and map to canonical skills."""
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(LearningResource).where(LearningResource.is_active.is_(True))
        )
        resources = res.scalars().all()
        assert len(resources) >= 65, f"Expected >= 65 active resources, found {len(resources)}"

        python_res = [r for r in resources if r.skill_name == "Python"]
        assert len(python_res) >= 1, "Expected Python learning resource"
        assert "python.org" in python_res[0].url.lower()


@pytest.mark.requires_postgres
@pytest.mark.asyncio
async def test_postgres_job_market_trends_retrieval():
    """Verify job_market_trends records exist with demand_share and snapshot SHA."""
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(JobMarketTrend).where(JobMarketTrend.period_type == "month")
        )
        trends = res.scalars().all()
        assert len(trends) == len(CANONICAL_SKILLS), f"Expected {len(CANONICAL_SKILLS)} skills in trends, found {len(trends)}"

        top_trend = max(trends, key=lambda t: t.postings_with_skill)
        assert top_trend.postings_with_skill > 0
        assert top_trend.demand_share > 0.0
        assert top_trend.source_snapshot_sha256 is not None


@pytest.mark.requires_postgres
@pytest.mark.asyncio
async def test_postgres_evaluation_logs_retrieval():
    """Verify evaluation_logs records exist with dataset_sha256 and metric values."""
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(EvaluationLog).where(EvaluationLog.component == "router_trained")
        )
        logs = res.scalars().all()
        assert len(logs) >= 2, f"Expected >= 2 trained router metrics, found {len(logs)}"
        metric_names = {l.metric_name for l in logs}
        assert "accuracy" in metric_names
        assert logs[0].dataset_sha256 is not None
        assert len(logs[0].dataset_sha256) == 64


# ---------------------------------------------------------------------------
# 3. Neo4j Role Graph & Pathway Integration Tests (requires Neo4j)
# ---------------------------------------------------------------------------

@pytest.mark.requires_neo4j
@pytest.mark.asyncio
async def test_neo4j_graph_stats_includes_roles():
    """Verify graph_service.get_graph_stats() reflects Role, LEADS_TO, and OFFERS."""
    stats = await graph_service.get_graph_stats()
    assert isinstance(stats, GraphStatsResponse)
    assert stats.nodes.roles == 52, f"Expected 52 Role nodes, got {stats.nodes.roles}"
    assert stats.relationships.leads_to == 53, f"Expected 53 LEADS_TO edges, got {stats.relationships.leads_to}"
    assert stats.relationships.offers >= 300, f"Expected >= 300 OFFERS edges, got {stats.relationships.offers}"
    assert stats.nodes.skills >= 77
    assert stats.relationships.requires >= 500


@pytest.mark.requires_neo4j
@pytest.mark.asyncio
async def test_neo4j_role_progression_pathways():
    """Verify find_role_progression_pathways returns 1..3 depth progression and missing skills."""
    res = await graph_service.find_role_progression_pathways(
        role_name="Junior Web Developer Trainee",
        candidate_skills=["HTML/CSS", "JavaScript"],
        max_depth=3,
    )
    assert isinstance(res, RoleProgressionResponse)
    assert res.total_reachable_roles > 0
    assert len(res.pathways) == res.total_reachable_roles

    # Check first hop
    step1 = res.pathways[0]
    assert step1.depth >= 1
    assert step1.total_years > 0.0
    assert "HTML/CSS" not in step1.missing_skills
    assert "JavaScript" not in step1.missing_skills
    assert len(step1.role_path) >= 2


@pytest.mark.requires_neo4j
@pytest.mark.asyncio
async def test_neo4j_role_progression_unknown_role():
    """Verify find_role_progression_pathways handles unknown role cleanly."""
    res = await graph_service.find_role_progression_pathways(
        role_name="Nonexistent Quantum Wizard",
    )
    assert res.total_reachable_roles == 0
    assert len(res.pathways) == 0
    assert "No progressive pathways found" in res.summary


# ---------------------------------------------------------------------------
# 4. ChromaDB Interview Corpus Integration Tests (requires Chroma)
# ---------------------------------------------------------------------------

@pytest.mark.requires_chroma
def test_chroma_interview_material_collection_size():
    """Verify Chroma collection interview_material_embeddings has all 157 items."""
    col = get_interview_material_collection()
    count = col.count()
    assert count == 157, f"Expected 157 interview questions in ChromaDB, found {count}"


@pytest.mark.requires_chroma
def test_chroma_semantic_query_retrieval():
    """Verify nearest-neighbor query retrieves relevant questions with metadata."""
    from app.services.embedding_service import get_sentence_transformer
    col = get_interview_material_collection()
    model = get_sentence_transformer()

    emb = model.encode("How do you design REST APIs in Python?", normalize_embeddings=True).tolist()
    res = col.query(query_embeddings=[emb], n_results=2)

    assert res and res.get("documents") and len(res["documents"][0]) == 2
    meta = res["metadatas"][0][0]
    assert "corpus_id" in meta
    assert "role_family" in meta
    assert "key_points_json" in meta


# ---------------------------------------------------------------------------
# 5. Service Wiring Tests (Coach, Market, Graph)
# ---------------------------------------------------------------------------

@pytest.mark.requires_postgres
@pytest.mark.asyncio
async def test_coach_skill_gap_attaches_learning_resources():
    """Verify CoachAgent attaches real learning resources to critical gaps."""
    async with AsyncSessionLocal() as session:
        r_stmt = select(Resume).limit(1)
        r_res = await session.execute(r_stmt)
        resume = r_res.scalar_one_or_none()

        j_stmt = select(JobPosting).limit(1)
        j_res = await session.execute(j_stmt)
        job = j_res.scalar_one_or_none()

        if resume and job:
            report = await coach_agent.generate_skill_gap_report(resume, job, db=session)
            assert isinstance(report, SkillGapReport)
            for gap in report.critical_gaps:
                assert isinstance(gap.learning_resources, list)
                if gap.learning_resources:
                    res_item = gap.learning_resources[0]
                    assert isinstance(res_item, ResourceItem)
                    assert res_item.title is not None


@pytest.mark.requires_postgres
@pytest.mark.requires_chroma
@pytest.mark.asyncio
async def test_coach_question_bank_retrieves_grounded_questions():
    """Verify CoachAgent question bank generation uses Chroma retrieval with fallback."""
    async with AsyncSessionLocal() as session:
        r_stmt = select(Resume).limit(1)
        r_res = await session.execute(r_stmt)
        resume = r_res.scalar_one_or_none()

        j_stmt = select(JobPosting).limit(1)
        j_res = await session.execute(j_stmt)
        job = j_res.scalar_one_or_none()

        if resume and job:
            gap_report = await coach_agent.generate_skill_gap_report(resume, job, db=session)
            qb_req = CoachQuestionBankRequest(
                resume_id=str(resume.id),
                job_id=str(job.id),
                max_technical=2,
                max_behavioral=2,
                max_gap=1,
            )
            qb = await coach_agent.generate_question_bank(resume, job, gap_report, qb_req)
            assert len(qb.technical_questions) <= 2
            assert len(qb.behavioral_questions) <= 2


@pytest.mark.requires_postgres
@pytest.mark.asyncio
async def test_market_trending_skills_enrichment():
    """Verify market_agent.get_trending_skills populates demand_share and dynamic velocity."""
    async with AsyncSessionLocal() as session:
        resp = await market_agent.get_trending_skills(session, top_n=5)
        assert len(resp.skills) <= 5
        for item in resp.skills:
            assert item.demand_share is not None
            assert item.velocity is not None
            assert item.velocity >= 0.0


# ---------------------------------------------------------------------------
# 6. API Route Tests (FastAPI Client)
# ---------------------------------------------------------------------------

@pytest.mark.requires_neo4j
@pytest.mark.asyncio
async def test_api_role_pathway_endpoint(async_client, auth_headers, test_user):
    """Verify GET /api/v1/graph/role-pathway returns 200 with RoleProgressionResponse."""
    app.dependency_overrides[get_current_user] = lambda: test_user
    try:
        response = await async_client.get(
            "/api/v1/graph/role-pathway?role_name=Junior Web Developer Trainee&candidate_skills=HTML/CSS,JavaScript",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["starting_role"] == "Junior Web Developer Trainee"
        assert data["total_reachable_roles"] > 0
        assert len(data["pathways"]) == data["total_reachable_roles"]
        assert "depth" in data["pathways"][0]
        assert "missing_skills" in data["pathways"][0]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.requires_neo4j
@pytest.mark.asyncio
async def test_api_graph_stats_endpoint(async_client, auth_headers, test_user):
    """Verify GET /api/v1/graph/stats returns 200 with roles, leads_to, and offers."""
    app.dependency_overrides[get_current_user] = lambda: test_user
    try:
        response = await async_client.get("/api/v1/graph/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["nodes"]["roles"] == 52
        assert data["relationships"]["leads_to"] == 53
        assert data["relationships"]["offers"] >= 300
    finally:
        app.dependency_overrides.pop(get_current_user, None)
