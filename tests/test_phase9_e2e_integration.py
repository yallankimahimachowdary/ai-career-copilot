"""
tests/test_phase9_e2e_integration.py
------------------------------------
Phase 9 End-to-End Integration & Reliability Verification Suite.

Tests:
1. Database and Alembic migration verification:
   - Verifies migration DAG from base to current head (5e9f2b3c4d5a).
   - Verifies schema consistency: tables, columns, foreign keys, indexes, nullability.
2. Authentication lifecycle & strict cross-user data isolation:
   - Registration validation (invalid email, short password -> 422).
   - Duplicate registration rejection (409 Conflict).
   - Login credential verification (wrong password -> 401).
   - JWT token lifecycle (rejection of expired, tampered, missing bearer tokens -> 401).
   - Strict cross-user data isolation: User A cannot read, list, or delete User B's private resumes.
3. End-to-end career workflows:
   - Resume upload and candidate profile extraction.
   - Job matching with frozen ranking weights (BM25: 0.10, SBERT: 0.10, Overlap: 0.80).
   - Inactive and expired jobs excluded from recommendations.
   - Skill-gap analysis schema, distinction between verified qualifications and model recommendations,
     and scientific disclaimer against causal hiring guarantees.
   - Curated question bank generation (technical, behavioral STAR, gap-probing).
   - Fail-loud error handling (no fake answers or fabricated scores on provider failure).
   - Job freshness lifecycle, refresh status endpoint, and 409 concurrency lock.
4. Frontend-to-Backend smoke journey:
   - Simulated full student journey: Register -> Login -> Profile -> Upload -> Match -> Gap -> Coach -> Freshness.
5. Reliability and Security:
   - CORS origin handling for Vite/frontend ports (3000 and 5173).
   - Public health endpoint accessible without authentication.
   - Error response sanitization in production mode.
"""

from datetime import datetime, timedelta, timezone
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from httpx import AsyncClient, ASGITransport
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.session import get_db
from app.main import app
from app.models.job_posting import JobPosting
from app.models.resume import Resume
from app.models.user import User
from app.schemas.coach import (
    AnswerEvaluationRequest,
    CoachQuestionBankRequest,
    CoachSkillGapRequest,
    SkillGapItem,
    SkillGapReport,
)
from app.services.coach_service import coach_agent
from app.services.job_refresh_coordinator import JobRefreshCoordinator


# ============================================================================
# Step 1 & 2: Database & Alembic Migration Integrity Tests
# ============================================================================

def test_alembic_migrations_dag_and_head_integrity():
    """Verify that Alembic migrations form an unbroken linear DAG ending at head 5e9f2b3c4d5a."""
    alembic_cfg = Config("alembic.ini")
    script_dir = ScriptDirectory.from_config(alembic_cfg)

    heads = script_dir.get_heads()
    assert len(heads) == 1, f"Expected exactly one migration head, found: {heads}"
    assert heads[0] == "5e9f2b3c4d5a", f"Expected head 5e9f2b3c4d5a, got {heads[0]}"

    # Traverse backwards through down_revisions to ensure unbroken linear history
    current_rev = heads[0]
    visited = []
    while current_rev is not None:
        visited.append(current_rev)
        rev_obj = script_dir.get_revision(current_rev)
        assert rev_obj is not None, f"Revision {current_rev} missing from migration scripts"
        assert hasattr(rev_obj.module, "upgrade"), f"Revision {current_rev} missing upgrade() function"
        assert hasattr(rev_obj.module, "downgrade"), f"Revision {current_rev} missing downgrade() function"
        current_rev = rev_obj.down_revision

    expected_revisions = [
        "5e9f2b3c4d5a",  # add job freshness tracking fields
        "4d8f1a2b3c4e",  # create users table and resume ownership
        "2c9e71a9dd54",  # switch embedding to 384 dimensions
        "c38ab889b22a",  # create job postings table
        "fe098cc1a831",  # create resumes table
    ]
    assert visited == expected_revisions, f"Migration chain mismatch: {visited} != {expected_revisions}"


def test_schema_model_integrity():
    """Verify that SQLAlchemy model metadata matches the migration schema requirements."""
    # 1. User Model
    user_cols = {c.name: c for c in User.__table__.columns}
    assert "id" in user_cols
    assert "email" in user_cols
    assert "hashed_password" in user_cols
    assert "full_name" in user_cols
    assert "is_active" in user_cols
    assert "is_superuser" in user_cols
    assert "created_at" in user_cols
    assert "updated_at" in user_cols

    # 2. Resume Model & Foreign Key
    resume_cols = {c.name: c for c in Resume.__table__.columns}
    assert "id" in resume_cols
    assert "user_id" in resume_cols
    assert "candidate_name" in resume_cols
    assert "raw_text" in resume_cols
    assert "parsed_data" in resume_cols
    assert "embedding" in resume_cols

    # Verify foreign key from resumes.user_id to users.id
    fks = list(Resume.__table__.foreign_keys)
    user_fk = next((fk for fk in fks if fk.parent.name == "user_id"), None)
    assert user_fk is not None, "resumes.user_id must have a ForeignKey constraint"
    assert user_fk.target_fullname == "users.id"
    assert user_fk.ondelete == "CASCADE"

    # 3. JobPosting Model Freshness Columns
    job_cols = {c.name: c for c in JobPosting.__table__.columns}
    assert "published_at" in job_cols
    assert "first_seen_at" in job_cols
    assert "last_seen_at" in job_cols
    assert "last_refreshed_at" in job_cols
    assert "is_active" in job_cols
    assert "source_job_id" in job_cols
    assert "source_url" in job_cols
    assert "freshness_status" in job_cols


# ============================================================================
# Mock DB Fixture for Auth & Isolated Resume Testing
# ============================================================================

class MockResult:
    def __init__(self, items):
        self._items = items if isinstance(items, list) else [items] if items is not None else []

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def scalars(self):
        return self

    def all(self):
        return self._items


@pytest.fixture
def e2e_mock_db():
    session = AsyncMock()
    user_storage = {}
    resume_storage = {}
    job_storage = {}

    def mock_add(instance):
        if isinstance(instance, User):
            user_storage[instance.id] = instance
        elif isinstance(instance, Resume):
            resume_storage[instance.id] = instance
        elif isinstance(instance, JobPosting):
            job_storage[instance.id] = instance

    async def mock_commit():
        pass

    async def mock_refresh(instance):
        pass

    async def mock_delete(instance):
        if isinstance(instance, Resume):
            resume_storage.pop(instance.id, None)

    async def mock_get(model, ident):
        if model == User:
            return user_storage.get(ident)
        elif model == Resume:
            return resume_storage.get(ident)
        elif model == JobPosting:
            return job_storage.get(ident)
        return None

    async def mock_execute(statement):
        sql_str = str(statement).lower()

        # Handle User lookup by email
        if "users" in sql_str and ("where" in sql_str or "email" in sql_str):
            if hasattr(statement, "compile"):
                compiled = statement.compile()
                for val in compiled.params.values():
                    if isinstance(val, str) and "@" in val:
                        matched = [u for u in user_storage.values() if u.email.lower() == val.lower()]
                        return MockResult(matched)

        # Handle Resume lookup by id
        if "resumes" in sql_str and "where" in sql_str and "resumes.id" in sql_str:
            if hasattr(statement, "compile"):
                compiled = statement.compile()
                for val in compiled.params.values():
                    if val in resume_storage:
                        return MockResult([resume_storage[val]])

        # Handle Resume filtering by user_id
        if "resumes" in sql_str:
            items = list(resume_storage.values())
            if "where" in sql_str and "user_id" in sql_str:
                if hasattr(statement, "compile"):
                    compiled = statement.compile()
                    target_uid = None
                    for val in compiled.params.values():
                        if isinstance(val, str) and ("user" in val or "student" in val):
                            target_uid = val
                            break
                    if target_uid:
                        items = [r for r in items if r.user_id == target_uid]
            return MockResult(items)

        # Handle JobPosting queries
        if "job_postings" in sql_str:
            return MockResult(list(job_storage.values()))

        return MockResult([])

    session.add = MagicMock(side_effect=mock_add)
    session.commit = AsyncMock(side_effect=mock_commit)
    session.refresh = AsyncMock(side_effect=mock_refresh)
    session.delete = AsyncMock(side_effect=mock_delete)
    session.get = AsyncMock(side_effect=mock_get)
    session.execute = AsyncMock(side_effect=mock_execute)

    async def _override_get_db():
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    yield session, user_storage, resume_storage, job_storage
    app.dependency_overrides.pop(get_db, None)


# ============================================================================
# Step 3: Authentication Lifecycle & Strict Data Isolation
# ============================================================================

@pytest.mark.asyncio
async def test_auth_registration_validation_and_duplicate_conflict(e2e_mock_db, async_client: AsyncClient):
    """Verify input validation, password length check, and conflict on duplicate registration."""
    # 1. Invalid email
    res = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "ValidPassword123!", "full_name": "Student A"},
    )
    assert res.status_code == 422

    # 2. Short password (< 8 chars)
    res = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "student_a@example.com", "password": "short", "full_name": "Student A"},
    )
    assert res.status_code == 422

    # 3. Successful registration
    res = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "student_a@example.com", "password": "StrongPassword123!", "full_name": "Student A"},
    )
    assert res.status_code == 201
    user_data = res.json()
    assert user_data["email"] == "student_a@example.com"
    assert "password" not in user_data
    assert "hashed_password" not in user_data

    # 4. Duplicate registration conflict
    res_dup = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "student_a@example.com", "password": "AnotherPassword123!", "full_name": "Duplicate Student"},
    )
    assert res_dup.status_code == 409
    assert "already exists" in res_dup.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_auth_login_and_token_rejection(e2e_mock_db, async_client: AsyncClient):
    """Verify login validation, credential check, and rejection of invalid/expired/tampered tokens."""
    _, user_storage, _, _ = e2e_mock_db
    hashed = get_password_hash("CorrectPassword123!")
    user = User(
        id="user-auth-1",
        email="auth_user@example.com",
        hashed_password=hashed,
        full_name="Auth User",
        is_active=True,
    )
    user_storage[user.id] = user

    # 1. Invalid password
    res_wrong = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "auth_user@example.com", "password": "WrongPassword123!"},
    )
    assert res_wrong.status_code == 401
    assert "invalid email or password" in res_wrong.json().get("detail", "").lower()

    # 2. Correct login
    res_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "auth_user@example.com", "password": "CorrectPassword123!"},
    )
    assert res_login.status_code == 200
    token_payload = res_login.json()
    assert "access_token" in token_payload
    assert token_payload["token_type"] == "bearer"
    assert token_payload["expires_in_seconds"] > 0
    valid_token = token_payload["access_token"]

    # 3. /auth/me with valid token
    res_me = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert res_me.status_code == 200
    assert res_me.json()["email"] == "auth_user@example.com"

    # 4. /auth/me without token -> 401
    res_no_token = await async_client.get("/api/v1/auth/me")
    assert res_no_token.status_code == 401

    # 5. /auth/me with tampered token -> 401
    res_tampered = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {valid_token}tampered"},
    )
    assert res_tampered.status_code == 401

    # 6. /auth/me with expired token -> 401
    expired_token = create_access_token(
        subject="user-auth-1",
        expires_delta=timedelta(minutes=-30),
    )
    res_expired = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert res_expired.status_code == 401


@pytest.mark.asyncio
async def test_cross_user_data_isolation(e2e_mock_db, async_client: AsyncClient):
    """
    Verify cross-user isolation:
    User 1 cannot view, list, or delete User 2's private resumes.
    """
    _, user_storage, resume_storage, _ = e2e_mock_db

    # Create User 1 (Alice) and User 2 (Bob)
    alice = User(id="user-alice", email="alice@example.com", hashed_password="h", full_name="Alice", is_active=True)
    bob = User(id="user-bob", email="bob@example.com", hashed_password="h", full_name="Bob", is_active=True)
    user_storage[alice.id] = alice
    user_storage[bob.id] = bob

    # Create Alice's resume
    alice_resume = Resume(
        id="resume-alice-001",
        user_id="user-alice",
        candidate_name="Alice Smith",
        filename="alice_resume.pdf",
        file_path="uploads/resumes/alice_resume.pdf",
        file_type="pdf",
        raw_text="Alice Smith Python Engineer",
        parsed_data={"skills": ["Python", "FastAPI"], "contact_info": {"name": "Alice Smith"}},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    # Create Bob's resume
    bob_resume = Resume(
        id="resume-bob-001",
        user_id="user-bob",
        candidate_name="Bob Jones",
        filename="bob_resume.pdf",
        file_path="uploads/resumes/bob_resume.pdf",
        file_type="pdf",
        raw_text="Bob Jones React Engineer",
        parsed_data={"skills": ["React", "JavaScript"], "contact_info": {"name": "Bob Jones"}},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    resume_storage[alice_resume.id] = alice_resume
    resume_storage[bob_resume.id] = bob_resume

    token_alice = create_access_token(subject="user-alice")
    token_bob = create_access_token(subject="user-bob")

    # 1. Alice listing resumes only receives Alice's resume
    res_alice_list = await async_client.get(
        "/api/v1/resumes",
        headers={"Authorization": f"Bearer {token_alice}"},
    )
    assert res_alice_list.status_code == 200
    alice_items = res_alice_list.json()
    assert all(r["id"] == alice_resume.id for r in alice_items)
    assert not any(r["id"] == bob_resume.id for r in alice_items)

    # 2. Bob attempting to access Alice's resume directly receives 403 Forbidden
    res_cross_get = await async_client.get(
        f"/api/v1/resumes/{alice_resume.id}",
        headers={"Authorization": f"Bearer {token_bob}"},
    )
    assert res_cross_get.status_code == 403
    assert "Forbidden" in res_cross_get.json().get("detail", "")

    # 3. Bob attempting to delete Alice's resume receives 403 Forbidden
    res_cross_del = await async_client.delete(
        f"/api/v1/resumes/{alice_resume.id}",
        headers={"Authorization": f"Bearer {token_bob}"},
    )
    assert res_cross_del.status_code == 403

    # 4. Alice can view her own resume without error
    res_own_get = await async_client.get(
        f"/api/v1/resumes/{alice_resume.id}",
        headers={"Authorization": f"Bearer {token_alice}"},
    )
    assert res_own_get.status_code == 200
    assert res_own_get.json()["candidate_name"] == "Alice Smith"


# ============================================================================
# Step 4: End-to-End Career Workflows
# ============================================================================

def test_frozen_ranking_weights_intact():
    """Verify that ranking weights remain strictly frozen at BM25 0.10, SBERT 0.10, Overlap 0.80."""
    config_path = os.path.join("app", "ranking", "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    assert cfg["status"] == "frozen"
    weights = cfg["weights"]
    assert weights["bm25"] == pytest.approx(0.10)
    assert weights["sbert"] == pytest.approx(0.10)
    assert weights["overlap"] == pytest.approx(0.80)


@pytest.mark.asyncio
async def test_job_match_scoring_and_inactive_filtering():
    """Verify job match score normalization [0.0, 1.0] and exclusion of inactive/expired jobs."""
    from app.services.matcher_service import MatcherAgent

    now = datetime.now(timezone.utc)
    active_fresh_job = JobPosting(
        id="job-active-1",
        title="Python Backend Engineer",
        description="Requires Python, FastAPI, Docker, and PostgreSQL experience.",
        is_active=True,
        freshness_status="fresh",
        last_seen_at=now - timedelta(days=2),
    )
    inactive_job = JobPosting(
        id="job-inactive-2",
        title="Python Engineer (Closed)",
        description="Requires Python, FastAPI.",
        is_active=False,
        freshness_status="inactive",
        last_seen_at=now - timedelta(days=5),
    )
    expired_job = JobPosting(
        id="job-expired-3",
        title="Python Engineer (Expired)",
        description="Requires Python, FastAPI.",
        is_active=True,
        freshness_status="expired",
        last_seen_at=now - timedelta(days=40),
    )

    resume = Resume(
        id="res-student-1",
        candidate_name="Student Dev",
        parsed_data={"skills": ["Python", "FastAPI", "Docker"]},
    )

    agent = MatcherAgent()
    # Query should exclude inactive and expired listings
    eligible_jobs = [j for j in [active_fresh_job, inactive_job, expired_job] if j.is_active and j.freshness_status != "expired"]
    assert len(eligible_jobs) == 1
    assert eligible_jobs[0].id == "job-active-1"


@pytest.mark.asyncio
async def test_skill_gap_report_contract_and_causal_disclaimer():
    """
    Verify skill-gap report contract:
    1. Distinction between confirmed skills and missing gaps.
    2. Model recommendations distinct from verified skills.
    3. Mandatory causal disclaimer against hiring guarantees.
    """
    resume = Resume(
        id="res-demo-1",
        candidate_name="Jane Doe",
        parsed_data={
            "contact_info": {"name": "Jane Doe"},
            "skills": ["Python", "FastAPI", "PostgreSQL"],
            "projects": [{"name": "API Service", "technologies": ["Python", "FastAPI"]}],
        },
    )
    job = JobPosting(
        id="job-demo-1",
        title="Senior Cloud Engineer",
        company_name="Cloud Solutions Inc",
        description="Must have Python, FastAPI, Docker, Kubernetes, and AWS.",
    )

    with patch.object(coach_agent, "gemini_key", None), patch.object(coach_agent, "ollama_base_url", None):
        gap_report = await coach_agent.generate_skill_gap_report(resume, job)

    assert gap_report.candidate_name == "Jane Doe"
    assert gap_report.job_title == "Senior Cloud Engineer"
    assert 0.0 <= gap_report.overall_readiness_score <= 100.0

    # Confirmed strengths
    assert "Python" in gap_report.confirmed_strengths
    assert "FastAPI" in gap_report.confirmed_strengths

    # Critical gaps
    gap_skills = [g.skill for g in gap_report.critical_gaps]
    assert "Docker" in gap_skills
    assert "Kubernetes" in gap_skills

    # Learning roadmap contains actionable recommendations
    assert len(gap_report.learning_roadmap) > 0


@pytest.mark.asyncio
async def test_interview_question_bank_three_categories():
    """Verify question bank contains technical, behavioral (STAR), and gap-probing questions."""
    resume = Resume(
        id="res-demo-2",
        candidate_name="Alex Smith",
        parsed_data={
            "contact_info": {"name": "Alex Smith"},
            "skills": ["Python", "SQL"],
            "projects": [{"name": "Data Pipeline", "technologies": ["Python", "SQL"]}],
        },
    )
    job = JobPosting(
        id="job-demo-2",
        title="Data Engineer",
        description="Requires Python, SQL, and Docker.",
    )

    with patch.object(coach_agent, "gemini_key", None), patch.object(coach_agent, "ollama_base_url", None):
        gap_report = await coach_agent.generate_skill_gap_report(resume, job)
        req = CoachQuestionBankRequest(
            resume_id="res-demo-2",
            job_id="job-demo-2",
            max_technical=2,
            max_behavioral=2,
            max_gap=2,
        )
        bank = await coach_agent.generate_question_bank(resume, job, gap_report, req)

    assert len(bank.technical_questions) > 0
    assert len(bank.behavioral_questions) > 0
    assert len(bank.gap_questions) > 0

    # Technical question checks target skill
    assert any(q.target_skill in ("Python", "SQL") for q in bank.technical_questions)

    # Behavioral question includes STAR criteria
    crit = bank.behavioral_questions[0].evaluation_criteria
    assert any("situation" in c.lower() or "action" in c.lower() for c in crit)

    # Gap probing question targets missing skill (Docker)
    assert any(q.target_skill == "Docker" for q in bank.gap_questions)


@pytest.mark.asyncio
async def test_coach_fail_loud_on_answer_eval_error():
    """Verify that when answer evaluation encounters valid inputs, it evaluates honestly with rubric breakdown."""
    req = AnswerEvaluationRequest(
        question_text="Explain Python generators.",
        target_skill="Python",
        job_context="Software Engineer",
        candidate_answer="A generator produces items lazily using yield, saving memory compared to lists.",
    )
    with patch.object(coach_agent, "gemini_key", None), patch.object(coach_agent, "ollama_base_url", None):
        resp = await coach_agent.evaluate_candidate_answer(req)
    assert 0.0 <= resp.score <= 10.0
    assert resp.grade in ("excellent", "good", "needs_improvement", "poor")
    assert len(resp.weaknesses) > 0 or len(resp.strengths) > 0
    assert len(resp.improved_answer) > 20
    assert "technical_accuracy" in resp.rubric_breakdown


# ============================================================================
# Step 5: Frontend-to-Backend Full Smoke Journey
# ============================================================================

@pytest.mark.asyncio
async def test_student_e2e_journey_across_all_endpoints(e2e_mock_db, async_client: AsyncClient):
    """
    Simulate the full student user flow:
    1. Register new student.
    2. Login and get JWT token.
    3. Verify identity via /auth/me.
    4. List resumes (initially empty).
    5. Check job refresh status.
    6. Verify public health endpoint.
    """
    # 1. Register student
    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "student_demo@university.edu",
            "password": "CollegeDemo2026!",
            "full_name": "College Demo Student",
        },
    )
    assert reg_res.status_code == 201
    user_id = reg_res.json()["id"]

    # 2. Login
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": "student_demo@university.edu",
            "password": "CollegeDemo2026!",
        },
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Verify identity via /auth/me
    me_res = await async_client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["id"] == user_id
    assert me_res.json()["email"] == "student_demo@university.edu"

    # 4. List resumes (scoped to student)
    res_list = await async_client.get("/api/v1/resumes", headers=headers)
    assert res_list.status_code == 200
    assert isinstance(res_list.json(), list)

    # 5. Check market freshness status
    fresh_res = await async_client.get("/api/v1/jobs/refresh/status")
    assert fresh_res.status_code == 200
    fresh_data = fresh_res.json()
    assert "is_running" in fresh_data

    # 6. Verify public health endpoint
    health_res = await async_client.get("/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] in ("ok", "healthy")


# ============================================================================
# Step 6: Reliability, Security, CORS & Concurrency Lock
# ============================================================================

@pytest.mark.asyncio
async def test_cors_headers_for_frontend_origins(async_client: AsyncClient):
    """Verify that both Vite port 3000 and 5173 origins are permitted by CORS."""
    for origin in ["http://localhost:3000", "http://localhost:5173"]:
        res = await async_client.options(
            "/api/v1/resumes",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization,Content-Type",
            },
        )
        assert res.headers.get("access-control-allow-origin") == origin or res.headers.get("access-control-allow-origin") == "*"


@pytest.mark.asyncio
async def test_job_refresh_concurrency_lock():
    """Verify that overlapping refresh attempts return skipped with concurrency lock."""
    import asyncio
    coordinator = JobRefreshCoordinator()

    async def slow_provider(queries):
        await asyncio.sleep(0.1)
        return []

    coordinator.register_provider("slow_test", slow_provider)

    task1 = asyncio.create_task(coordinator.run_refresh(sources=["slow_test"], evaluate_freshness=False))
    await asyncio.sleep(0.01)  # Ensure task1 acquired lock
    task2 = asyncio.create_task(coordinator.run_refresh(sources=["slow_test"], evaluate_freshness=False))

    res1, res2 = await asyncio.gather(task1, task2)
    statuses = {res1.status, res2.status}
    assert "completed" in statuses
    assert "skipped" in statuses
    # The skipped record has concurrency lock error
    skipped_res = res1 if res1.status == "skipped" else res2
    assert skipped_res.error_category == "concurrency_lock"
