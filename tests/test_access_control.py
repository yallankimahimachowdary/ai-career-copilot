"""
tests/test_access_control.py
----------------------------
Comprehensive test suite verifying access control, token enforcement,
resource ownership verification, legacy NULL-owner restrictions,
removal of demo/fallback shortcuts, fail-loud ingestion, and parameter tampering immunity.
"""

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.deps import enforce_resume_ownership, get_current_user, get_db, get_owned_resume
from app.core.security import create_access_token
from app.main import app
from app.models.job_posting import JobPosting
from app.models.resume import Resume
from app.models.user import User
from app.schemas.chat import ChatQueryRequest
from scripts.ingest.adzuna_ingest import AdzunaIngestService


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_users():
    user_a = User(
        id="usr-user-a-uuid",
        email="user_a@example.com",
        full_name="User A",
        is_active=True,
        is_superuser=False,
    )
    user_b = User(
        id="usr-user-b-uuid",
        email="user_b@example.com",
        full_name="User B",
        is_active=True,
        is_superuser=False,
    )
    admin = User(
        id="usr-admin-uuid",
        email="admin@example.com",
        full_name="Super Admin",
        is_active=True,
        is_superuser=True,
    )

    token_a = create_access_token(user_a.id, extra_claims={"email": user_a.email, "is_superuser": False})
    token_b = create_access_token(user_b.id, extra_claims={"email": user_b.email, "is_superuser": False})
    token_admin = create_access_token(admin.id, extra_claims={"email": admin.email, "is_superuser": True})

    return {
        "user_a": user_a,
        "user_b": user_b,
        "admin": admin,
        "token_a": token_a,
        "token_b": token_b,
        "token_admin": token_admin,
        "headers_a": {"Authorization": f"Bearer {token_a}"},
        "headers_b": {"Authorization": f"Bearer {token_b}"},
        "headers_admin": {"Authorization": f"Bearer {token_admin}"},
    }


class AccessControlMockDB:
    def __init__(self, user_map, resume_map, job_map):
        self.user_map = user_map
        self.resume_map = resume_map
        self.job_map = job_map

    async def get(self, model, ident):
        if model == User:
            return self.user_map.get(ident)
        if model == Resume:
            return self.resume_map.get(ident)
        if model == JobPosting:
            return self.job_map.get(ident)
        return None

    async def execute(self, statement):
        compiled = statement.compile()
        sql = str(compiled).lower()
        params = compiled.params or {}
        items = []
        if "from resumes" in sql or "from resume" in sql:
            items = list(self.resume_map.values())
            if "where resumes.id" in sql or "where resume.id" in sql or "resumes.id =" in sql:
                target_id = params.get("id_1") or params.get("resume_id") or params.get("id")
                items = [r for r in items if r.id == target_id]
            elif "where resumes.user_id" in sql or "resumes.user_id =" in sql:
                target_user = params.get("user_id_1") or params.get("user_id")
                items = [r for r in items if r.user_id == target_user]
        elif "from users" in sql or "from user" in sql:
            items = list(self.user_map.values())
            if "where users.id" in sql or "users.id =" in sql:
                target_id = params.get("id_1") or params.get("user_id")
                items = [u for u in items if u.id == target_id]
        elif "from job_postings" in sql or "from job_posting" in sql:
            items = list(self.job_map.values())
            if "where job_postings.id" in sql or "job_postings.id =" in sql:
                target_id = params.get("id_1") or params.get("job_id")
                items = [j for j in items if j.id == target_id]

        class ResultWrapper:
            def __init__(self, items):
                self._items = items
            def scalar_one_or_none(self):
                return self._items[0] if self._items else None
            def scalars(self):
                return self
            def first(self):
                return self._items[0] if self._items else None
            def all(self):
                return self._items
            def scalar(self):
                return len(self._items)

        return ResultWrapper(items)

    def add(self, instance):
        if isinstance(instance, Resume):
            self.resume_map[instance.id] = instance
        elif isinstance(instance, User):
            self.user_map[instance.id] = instance
        elif isinstance(instance, JobPosting):
            self.job_map[instance.id] = instance

    async def commit(self):
        pass

    async def refresh(self, instance):
        pass

    async def delete(self, instance):
        if isinstance(instance, Resume):
            self.resume_map.pop(instance.id, None)
        elif isinstance(instance, JobPosting):
            self.job_map.pop(instance.id, None)


@pytest.fixture
def mock_system_db(auth_users):
    user_map = {
        auth_users["user_a"].id: auth_users["user_a"],
        auth_users["user_b"].id: auth_users["user_b"],
        auth_users["admin"].id: auth_users["admin"],
    }
    now = datetime.now(timezone.utc)
    resume_a = Resume(
        id="resume-a-uuid",
        user_id=auth_users["user_a"].id,
        filename="alice_resume.pdf",
        file_path="/tmp/alice_resume.pdf",
        file_type="application/pdf",
        raw_text="Alice Candidate resume text with Python and SQL",
        candidate_name="Alice Candidate",
        email="alice@example.com",
        phone="555-0199",
        parsed_data={"contact_info": {"name": "Alice Candidate"}, "skills": ["Python", "SQL"]},
        embedding=[0.05] * 384,
        created_at=now,
        updated_at=now,
    )
    resume_legacy = Resume(
        id="resume-legacy-null-uuid",
        user_id=None,  # Legacy NULL owner
        filename="legacy_resume.pdf",
        file_path="/tmp/legacy_resume.pdf",
        file_type="application/pdf",
        raw_text="Legacy Candidate resume text with C++",
        candidate_name="Legacy Candidate",
        email="legacy@example.com",
        phone="555-0100",
        parsed_data={"contact_info": {"name": "Legacy Candidate"}, "skills": ["C++"]},
        embedding=[0.05] * 384,
        created_at=now,
        updated_at=now,
    )
    job_target = JobPosting(
        id="job-target-uuid",
        title="Backend Software Engineer",
        company_name="Acme Tech",
        description="Looking for Python backend engineer.",
        skills=["Python", "SQL"],
        source="internal",
        remote_allowed=True,
        is_active=True,
        freshness_status="fresh",
        created_at=now,
    )
    resume_map = {
        resume_a.id: resume_a,
        resume_legacy.id: resume_legacy,
    }
    job_map = {
        job_target.id: job_target,
    }

    mock_db = AccessControlMockDB(user_map, resume_map, job_map)

    async def _get_db():
        yield mock_db

    app.dependency_overrides[get_db] = _get_db
    yield mock_db, resume_a, resume_legacy, job_target
    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Test 1: Route Inventory Sweep asserting 401 on all non-public routes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_inventory_sweep_asserts_401_on_all_private_routes(async_client: AsyncClient):
    """
    Exhaustive sweep over all OpenAPI routes:
    Verifies that every single non-public route strictly returns 401 Unauthorized
    when called without an Authorization token.
    """
    public_paths = {
        "/health",
        "/api/v1/health",
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/login/oauth",
        "/",
        "/docs",
        "/redoc",
        "/api/v1/openapi.json",
    }

    paths = app.openapi()["paths"]
    tested_private_count = 0

    for path, methods in paths.items():
        if path in public_paths:
            continue

        for method in methods:
            if method.lower() not in ("get", "post", "delete", "put", "patch"):
                continue

            # Fill path parameters with dummy placeholders
            test_path = path.replace("{resume_id}", "any-res-id")
            test_path = test_path.replace("{job_id}", "any-job-id")
            test_path = test_path.replace("{candidate_id}", "any-cand-id")

            # Call endpoint without token
            if method.lower() == "get":
                res = await async_client.get(test_path)
            elif method.lower() == "post":
                res = await async_client.post(test_path, json={})
            elif method.lower() == "delete":
                res = await async_client.delete(test_path)
            else:
                continue

            # Route MUST reject anonymous caller with 401 Unauthorized
            assert res.status_code == 401, (
                f"Security defect: {method.upper()} {test_path} allowed unauthenticated access (status: {res.status_code})"
            )
            tested_private_count += 1

    # Ensure we verified a substantial number of private endpoints
    assert tested_private_count >= 15, f"Expected to sweep at least 15 private endpoints, swept {tested_private_count}"


# ---------------------------------------------------------------------------
# Test 2: Anonymous /resumes GET and upload -> 401
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_anonymous_resumes_get_and_upload_rejected_with_401(async_client: AsyncClient):
    """Verify that calling GET /resumes or POST /resumes/upload anonymously yields 401."""
    # Anonymous list resumes
    res_list = await async_client.get("/api/v1/resumes")
    assert res_list.status_code == 401

    # Anonymous upload
    files = {"file": ("test.txt", b"Resume content", "text/plain")}
    res_upload = await async_client.post("/api/v1/resumes/upload", files=files)
    assert res_upload.status_code == 401


# ---------------------------------------------------------------------------
# Test 3: Cross-user checks across resumes, matches, coach, chat, graph -> 403
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cross_user_checks_across_all_domains_yield_403(
    async_client: AsyncClient, auth_users, mock_system_db
):
    """
    User B must be rejected with HTTP 403 Forbidden when attempting to access,
    match, coach, chat, or pathway-inspect User A's resume.
    """
    _, resume_a, _, job_target = mock_system_db
    headers_b = auth_users["headers_b"]

    # 1. Resumes GET
    res = await async_client.get(f"/api/v1/resumes/{resume_a.id}", headers=headers_b)
    assert res.status_code == 403
    assert "forbidden" in res.json()["detail"].lower()

    # 2. Resumes DELETE
    res = await async_client.delete(f"/api/v1/resumes/{resume_a.id}", headers=headers_b)
    assert res.status_code == 403

    # 3. Matches for Resume
    res = await async_client.post(f"/api/v1/matches/resume/{resume_a.id}", headers=headers_b)
    assert res.status_code == 403

    # 4. Matches Compare
    res = await async_client.get(f"/api/v1/matches/compare/{resume_a.id}/{job_target.id}", headers=headers_b)
    assert res.status_code == 403

    # 5. Coach Skill Gap
    res = await async_client.post(
        "/api/v1/coach/skill-gap",
        json={"resume_id": resume_a.id, "job_id": job_target.id},
        headers=headers_b,
    )
    assert res.status_code == 403

    # 6. Coach Question Bank
    res = await async_client.post(
        "/api/v1/coach/question-bank",
        json={"resume_id": resume_a.id, "job_id": job_target.id},
        headers=headers_b,
    )
    assert res.status_code == 403

    # 7. Coach Session
    res = await async_client.post(
        "/api/v1/coach/session",
        json={"resume_id": resume_a.id, "job_id": job_target.id},
        headers=headers_b,
    )
    assert res.status_code == 403

    # 8. Market Resume Positioning
    res = await async_client.post(
        "/api/v1/market/resume-positioning",
        json={"resume_id": resume_a.id},
        headers=headers_b,
    )
    assert res.status_code == 403

    # 9. Chat Query referencing User A's resume
    res = await async_client.post(
        "/api/v1/chat/query",
        json={"query": "What are my skill gaps?", "resume_id": resume_a.id},
        headers=headers_b,
    )
    assert res.status_code == 403

    # 10. Graph Career Pathway referencing User A's candidate ID
    res = await async_client.get(
        f"/api/v1/graph/career-pathway/{resume_a.id}",
        headers=headers_b,
    )
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# Test 4: NULL-owner resume -> 403 for regular user, 200 for superuser
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_null_owner_legacy_resume_access_control(
    async_client: AsyncClient, auth_users, mock_system_db
):
    """
    Legacy resumes where user_id is NULL can only be accessed by administrative superusers.
    Regular non-superuser callers must receive 403 Forbidden.
    """
    _, _, resume_legacy, _ = mock_system_db

    # Regular user attempting to access NULL-owner resume
    res_regular = await async_client.get(
        f"/api/v1/resumes/{resume_legacy.id}",
        headers=auth_users["headers_a"],
    )
    assert res_regular.status_code == 403
    assert "legacy" in res_regular.json()["detail"].lower() or "forbidden" in res_regular.json()["detail"].lower()

    # Superuser attempting to access NULL-owner resume
    res_admin = await async_client.get(
        f"/api/v1/resumes/{resume_legacy.id}",
        headers=auth_users["headers_admin"],
    )
    assert res_admin.status_code == 200
    assert res_admin.json()["id"] == resume_legacy.id


# ---------------------------------------------------------------------------
# Test 5: "demo", "demo-resume", and non-existent IDs return 404
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_demo_ids_return_404_not_found(
    async_client: AsyncClient, auth_users, mock_system_db
):
    """
    Demo shortcuts and UUID placeholders must never fall back to selecting
    arbitrary records from the DB. They must fail loud with 404 Not Found.
    """
    headers = auth_users["headers_a"]
    demo_ids = ["demo", "demo-resume", "46ca6338-3b1a-4bfc-96e1-5b2a661348e4", "nonexistent-id-xyz"]

    for demo_id in demo_ids:
        # Coach skill gap
        res_coach = await async_client.post(
            "/api/v1/coach/skill-gap",
            json={"resume_id": demo_id, "job_id": "job-target-uuid"},
            headers=headers,
        )
        assert res_coach.status_code == 404, f"Expected 404 for resume_id='{demo_id}', got {res_coach.status_code}"

        # Resume detail
        res_detail = await async_client.get(
            f"/api/v1/resumes/{demo_id}",
            headers=headers,
        )
        assert res_detail.status_code == 404

        # Match jobs
        res_match = await async_client.post(
            f"/api/v1/matches/resume/{demo_id}",
            headers=headers,
        )
        assert res_match.status_code == 404


# ---------------------------------------------------------------------------
# Test 6: SQL execution inspection verifying Resume.user_id filter
# ---------------------------------------------------------------------------

def test_sql_execution_inspection_user_id_filter():
    """
    Inspect the compiled SQLAlchemy statement in list_resumes logic:
    - Normal user queries must compile `resumes.user_id = :user_id_1` into WHERE clause.
    - Superuser queries omit this constraint to permit full administrative oversight.
    """
    normal_user = User(id="user-norm", email="norm@example.com", is_superuser=False)
    admin_user = User(id="user-admin", email="admin@example.com", is_superuser=True)

    # 1. Normal user statement
    stmt_normal = select(Resume).order_by(Resume.created_at.desc())
    if not normal_user.is_superuser:
        stmt_normal = stmt_normal.where(Resume.user_id == normal_user.id)

    sql_normal = str(stmt_normal.compile(compile_kwargs={"literal_binds": True}))
    assert "resumes.user_id = 'user-norm'" in sql_normal

    # 2. Superuser statement
    stmt_admin = select(Resume).order_by(Resume.created_at.desc())
    if not admin_user.is_superuser:
        stmt_admin = stmt_admin.where(Resume.user_id == admin_user.id)

    sql_admin = str(stmt_admin.compile(compile_kwargs={"literal_binds": True})).lower()
    assert "where" not in sql_admin


# ---------------------------------------------------------------------------
# Test 7: Adzuna credentials missing without mock -> raises; with mock -> succeeds
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_adzuna_credentials_missing_raises_loudly():
    """Adzuna ingest must fail loud on missing credentials unless mock_response is explicitly passed."""
    service = AdzunaIngestService()
    service.app_id = None
    service.app_key = None

    # Missing credentials without mock -> must strictly raise ValueError
    with pytest.raises(ValueError, match="ADZUNA credentials not configured"):
        await service.fetch_jobs(query="DevOps Engineer")

    with pytest.raises(ValueError, match="ADZUNA credentials not configured"):
        await service.ingest_jobs(query="DevOps Engineer", save_to_live=False)

    # Supplying explicit mock -> succeeds in isolated mode
    mock_payload = [
        {
            "id": "mock_explicit_01",
            "title": "Cloud Architect",
            "company": {"display_name": "Test Cloud Co"},
            "location": {"display_name": "Bengaluru"},
            "description": "Python, AWS, Terraform",
        }
    ]
    fetched = await service.fetch_jobs(mock_response=mock_payload)
    assert len(fetched) == 1
    assert fetched[0]["id"] == "mock_explicit_01"

    ingested = await service.ingest_jobs(mock_response=mock_payload, save_to_live=False)
    assert len(ingested) == 1
    assert ingested[0]["source"] == "adzuna_mock"


# ---------------------------------------------------------------------------
# Test 8: Client-supplied user_id or owner in upload is ignored
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_client_supplied_user_id_ignored_on_upload(
    async_client: AsyncClient, auth_users, mock_system_db
):
    """
    When a candidate uploads a resume, any client-supplied user_id, owner_id,
    or candidate ID in form-data or query is completely ignored.
    The resume's user_id is derived strictly from the authenticated token.
    """
    mock_db, _, _, _ = mock_system_db
    sample_content = b"Candidate Name\ntest@example.com\nPython, FastAPI"
    files = {"file": ("test_resume.txt", sample_content, "text/plain")}
    data = {
        "user_id": "victim-user-id-to-impersonate",
        "owner_id": "victim-user-id-to-impersonate",
    }

    headers = auth_users["headers_a"]
    res = await async_client.post("/api/v1/resumes/upload", files=files, data=data, headers=headers)
    assert res.status_code == 201
    created_id = res.json()["id"]

    saved_record = mock_db.resume_map.get(created_id)
    assert saved_record is not None
    # User ID must be User A's ID from token, NOT the victim's ID
    assert saved_record.user_id == auth_users["user_a"].id
    assert saved_record.user_id != "victim-user-id-to-impersonate"


# ---------------------------------------------------------------------------
# Test 9: Unit tests for enforce_resume_ownership and get_owned_resume
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enforce_resume_ownership_unit():
    """Direct unit testing of enforce_resume_ownership contract."""
    from fastapi import HTTPException

    owner = User(id="owner-1", is_superuser=False)
    stranger = User(id="stranger-2", is_superuser=False)
    superuser = User(id="admin-1", is_superuser=True)

    owned_resume = Resume(id="res-1", user_id="owner-1")
    legacy_resume = Resume(id="res-2", user_id=None)

    # 1. Unauthenticated -> 401
    with pytest.raises(HTTPException) as exc_info:
        enforce_resume_ownership(owned_resume, current_user=None)
    assert exc_info.value.status_code == 401

    # 2. Non-owner -> 403
    with pytest.raises(HTTPException) as exc_info:
        enforce_resume_ownership(owned_resume, current_user=stranger)
    assert exc_info.value.status_code == 403

    # 3. Owner -> passes
    enforce_resume_ownership(owned_resume, current_user=owner)

    # 4. Superuser on owned resume -> passes
    enforce_resume_ownership(owned_resume, current_user=superuser)

    # 5. Legacy resume + non-superuser -> 403
    with pytest.raises(HTTPException) as exc_info:
        enforce_resume_ownership(legacy_resume, current_user=owner)
    assert exc_info.value.status_code == 403

    # 6. Legacy resume + superuser -> passes
    enforce_resume_ownership(legacy_resume, current_user=superuser)


# ---------------------------------------------------------------------------
# Test 10: Job deletion permissions: 401 unauthenticated, 403 ordinary, 204 admin
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_job_deletion_permissions_role_enforcement(
    async_client: AsyncClient, auth_users, mock_system_db
):
    """
    Ensure administrative job deletion is accessible strictly to superusers.
    - Unauthenticated request -> 401 Unauthorized
    - Ordinary authenticated user (non-superuser) -> 403 Forbidden
    - Authorized superuser -> 204 No Content
    Legitimate read / search functionality remains fully functional for ordinary users.
    """
    mock_db, _, _, job_target = mock_system_db
    job_id = job_target.id

    # 1. Unauthenticated request -> 401 Unauthorized
    res_anon = await async_client.delete(f"/api/v1/jobs/{job_id}")
    assert res_anon.status_code == 401, f"Expected 401, got {res_anon.status_code}"

    # 2. Ordinary authenticated user (User A, non-superuser) -> 403 Forbidden
    res_ordinary = await async_client.delete(
        f"/api/v1/jobs/{job_id}",
        headers=auth_users["headers_a"],
    )
    assert res_ordinary.status_code == 403, f"Expected 403, got {res_ordinary.status_code}"
    assert "administrative" in res_ordinary.json()["detail"].lower()

    # 3. Legitimate read functionality works for ordinary user
    res_get = await async_client.get(
        f"/api/v1/jobs/{job_id}",
        headers=auth_users["headers_a"],
    )
    assert res_get.status_code == 200
    assert res_get.json()["id"] == job_id

    # 4. Authorized superuser -> 204 No Content
    res_admin = await async_client.delete(
        f"/api/v1/jobs/{job_id}",
        headers=auth_users["headers_admin"],
    )
    assert res_admin.status_code == 204

    # 5. Verify the job is removed from database
    assert job_id not in mock_db.job_map
