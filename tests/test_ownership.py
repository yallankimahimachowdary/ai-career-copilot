"""
tests/test_ownership.py
-----------------------
Tests for resource ownership enforcement and cross-user isolation.
Ensures that one user cannot view, list, or delete another user's private resumes.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.resume import Resume
from app.models.user import User


class MockResult:
    def __init__(self, items):
        self._items = items

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def scalars(self):
        return self

    def all(self):
        return self._items


@pytest.fixture
def ownership_mock_db():
    session = AsyncMock()
    resume_storage = {}
    user_storage = {}

    def mock_add(instance):
        if isinstance(instance, Resume):
            resume_storage[instance.id] = instance
        elif isinstance(instance, User):
            user_storage[instance.id] = instance

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
        return None

    async def mock_execute(statement):
        # Handle select(Resume) with possible where(Resume.user_id == ...)
        sql_str = str(statement).lower()
        items = list(resume_storage.values())
        if "where" in sql_str and "user_id" in sql_str:
            # Check compiled parameter
            if hasattr(statement, "compile"):
                compiled = statement.compile()
                target_uid = None
                for val in compiled.params.values():
                    if isinstance(val, str) and ("user" in val or "alice" in val or "bob" in val):
                        target_uid = val
                        break
                if target_uid:
                    items = [r for r in items if r.user_id == target_uid]

        # Handle select(Resume).where(Resume.id == ...)
        if "where" in sql_str and "resumes.id" in sql_str:
            if hasattr(statement, "compile"):
                compiled = statement.compile()
                for val in compiled.params.values():
                    if val in resume_storage:
                        items = [resume_storage[val]]
                        break

        return MockResult(items)

    session.add = MagicMock(side_effect=mock_add)
    session.commit = AsyncMock(side_effect=mock_commit)
    session.refresh = AsyncMock(side_effect=mock_refresh)
    session.delete = AsyncMock(side_effect=mock_delete)
    session.get = AsyncMock(side_effect=mock_get)
    session.execute = AsyncMock(side_effect=mock_execute)

    async def _override_get_db():
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    yield session, user_storage, resume_storage
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def users_and_resumes(ownership_mock_db):
    _, user_storage, resume_storage = ownership_mock_db

    user_a = User(
        id="user-a-uuid",
        email="user_a@example.com",
        hashed_password="hash",
        full_name="User Alpha",
        is_active=True,
        is_superuser=False,
    )
    user_b = User(
        id="user-b-uuid",
        email="user_b@example.com",
        hashed_password="hash",
        full_name="User Beta",
        is_active=True,
        is_superuser=False,
    )
    admin_user = User(
        id="admin-uuid",
        email="admin@example.com",
        hashed_password="hash",
        full_name="Admin User",
        is_active=True,
        is_superuser=True,
    )
    user_storage[user_a.id] = user_a
    user_storage[user_b.id] = user_b
    user_storage[admin_user.id] = admin_user
    now = datetime.now(timezone.utc)
    resume_a = Resume(
        id="resume-a-123",
        user_id=user_a.id,
        filename="alice_resume.pdf",
        file_path="uploads/resumes/alice_resume.pdf",
        file_type="pdf",
        raw_text="Alice Developer Resume",
        candidate_name="Alice Developer",
        email="alice@example.com",
        parsed_data={"skills": ["Python", "FastAPI"]},
        created_at=now,
        updated_at=now,
    )
    resume_storage[resume_a.id] = resume_a

    token_a = create_access_token(user_a.id)
    token_b = create_access_token(user_b.id)
    token_admin = create_access_token(admin_user.id)

    return {
        "user_a": user_a,
        "user_b": user_b,
        "admin": admin_user,
        "resume_a": resume_a,
        "token_a": token_a,
        "token_b": token_b,
        "token_admin": token_admin,
    }


@pytest.mark.asyncio
async def test_owner_can_access_own_resume(async_client: AsyncClient, users_and_resumes):
    token_a = users_and_resumes["token_a"]
    headers = {"Authorization": f"Bearer {token_a}"}

    res = await async_client.get("/api/v1/resumes/resume-a-123", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "resume-a-123"
    assert data["candidate_name"] == "Alice Developer"


@pytest.mark.asyncio
async def test_cross_user_access_forbidden(async_client: AsyncClient, users_and_resumes):
    """User B must be rejected with 403 Forbidden when trying to access User A's resume."""
    token_b = users_and_resumes["token_b"]
    headers = {"Authorization": f"Bearer {token_b}"}

    res = await async_client.get("/api/v1/resumes/resume-a-123", headers=headers)
    assert res.status_code == 403
    assert "forbidden" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_unauthenticated_access_to_private_resume_rejected(async_client: AsyncClient, users_and_resumes):
    """Unauthenticated guest accessing a user-owned resume is rejected with 401."""
    res = await async_client.get("/api/v1/resumes/resume-a-123")
    assert res.status_code == 401
    assert "authentication required" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_superuser_can_access_any_resume(async_client: AsyncClient, users_and_resumes):
    """Admin superuser can view User A's resume for audit and support."""
    token_admin = users_and_resumes["token_admin"]
    headers = {"Authorization": f"Bearer {token_admin}"}

    res = await async_client.get("/api/v1/resumes/resume-a-123", headers=headers)
    assert res.status_code == 200
    assert res.json()["id"] == "resume-a-123"


@pytest.mark.asyncio
async def test_cross_user_delete_forbidden(async_client: AsyncClient, users_and_resumes):
    """User B cannot delete User A's resume."""
    token_b = users_and_resumes["token_b"]
    headers = {"Authorization": f"Bearer {token_b}"}

    res = await async_client.delete("/api/v1/resumes/resume-a-123", headers=headers)
    assert res.status_code == 403
    assert "forbidden" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_owner_can_delete_own_resume(async_client: AsyncClient, users_and_resumes):
    """User A can delete their own resume."""
    token_a = users_and_resumes["token_a"]
    headers = {"Authorization": f"Bearer {token_a}"}

    res = await async_client.delete("/api/v1/resumes/resume-a-123", headers=headers)
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_list_resumes_scoped_to_current_user(async_client: AsyncClient, users_and_resumes, ownership_mock_db):
    """User B listing resumes does not see User A's resumes."""
    token_b = users_and_resumes["token_b"]
    headers = {"Authorization": f"Bearer {token_b}"}

    res = await async_client.get("/api/v1/resumes", headers=headers)
    assert res.status_code == 200
    resumes = res.json()
    assert all(r["id"] != "resume-a-123" for r in resumes)
