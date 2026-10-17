"""
tests/test_auth.py
------------------
Unit and integration tests for authentication, password hashing,
JWT token lifecycle, user registration, and profile endpoints.
"""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock
import pytest
from httpx import AsyncClient

from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)
from app.db.session import get_db
from app.main import app
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
def auth_mock_db():
    """In-memory mock database for User records."""
    session = AsyncMock()
    user_storage = {}

    def mock_add(instance):
        user_storage[instance.id] = instance

    async def mock_commit():
        pass

    async def mock_refresh(instance):
        pass

    async def mock_execute(statement):
        # Emulate filtering by email if applicable
        email_param = None
        sql_str = str(statement)
        # Check compiled parameters if available
        if hasattr(statement, "compile"):
            compiled = statement.compile()
            for val in compiled.params.values():
                if isinstance(val, str) and "@" in val:
                    email_param = val.lower()
                    break

        if email_param:
            filtered = [u for u in user_storage.values() if u.email.lower() == email_param]
            return MockResult(filtered)

        return MockResult(list(user_storage.values()))

    async def mock_get(model, ident):
        if model == User:
            return user_storage.get(ident)
        return None

    session.add = MagicMock(side_effect=mock_add)
    session.commit = AsyncMock(side_effect=mock_commit)
    session.refresh = AsyncMock(side_effect=mock_refresh)
    session.execute = AsyncMock(side_effect=mock_execute)
    session.get = AsyncMock(side_effect=mock_get)

    async def _override_get_db():
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    yield session, user_storage
    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Core Security Unit Tests
# ---------------------------------------------------------------------------

def test_password_hashing_and_verification():
    raw_pass = "SuperSecurePassword123!"
    hashed = get_password_hash(raw_pass)

    assert hashed != raw_pass
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
    assert verify_password(raw_pass, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False
    assert verify_password("", hashed) is False
    assert verify_password(raw_pass, "") is False


def test_jwt_token_lifecycle():
    user_id = "user-1234-uuid"
    token = create_access_token(subject=user_id, extra_claims={"email": "alice@example.com"})

    payload = decode_access_token(token)
    assert payload["sub"] == user_id
    assert payload["email"] == "alice@example.com"
    assert "exp" in payload
    assert "iat" in payload


def test_jwt_token_expired_raises_401():
    user_id = "user-expired-uuid"
    # Negative delta implies expired in the past
    token = create_access_token(subject=user_id, expires_delta=timedelta(seconds=-10))

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(token)

    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


def test_jwt_token_tampered_raises_401():
    user_id = "user-tampered-uuid"
    token = create_access_token(subject=user_id)
    # Corrupt the payload signature
    tampered_token = token[:-5] + "XXXXX"

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(tampered_token)

    assert exc_info.value.status_code == 401
    assert "invalid" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# API Integration Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_user_success(async_client: AsyncClient, auth_mock_db):
    _, user_storage = auth_mock_db
    payload = {
        "email": "candidate.test@example.com",
        "password": "Password123!",
        "full_name": "Test Candidate",
    }

    res = await async_client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "candidate.test@example.com"
    assert data["full_name"] == "Test Candidate"
    assert "password" not in data
    assert "hashed_password" not in data
    assert len(user_storage) == 1


@pytest.mark.asyncio
async def test_register_duplicate_email_conflict(async_client: AsyncClient, auth_mock_db):
    _, user_storage = auth_mock_db
    existing = User(
        id="user-exist-1",
        email="duplicate@example.com",
        hashed_password=get_password_hash("Existing123!"),
        full_name="Existing User",
    )
    user_storage[existing.id] = existing

    payload = {
        "email": "duplicate@example.com",
        "password": "NewPassword123!",
        "full_name": "Duplicate Attempt",
    }

    res = await async_client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 409
    assert "already exists" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_success_and_profile_access(async_client: AsyncClient, auth_mock_db):
    _, user_storage = auth_mock_db
    test_user = User(
        id="user-login-1",
        email="login.success@example.com",
        hashed_password=get_password_hash("CorrectPassword123!"),
        full_name="Login Success",
        is_active=True,
    )
    user_storage[test_user.id] = test_user

    # 1. Login with JSON payload
    login_payload = {
        "email": "login.success@example.com",
        "password": "CorrectPassword123!",
    }
    res = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert res.status_code == 200
    token_data = res.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    assert token_data["expires_in_seconds"] > 0

    token = token_data["access_token"]

    # 2. Access /api/v1/auth/me with Bearer token
    headers = {"Authorization": f"Bearer {token}"}
    profile_res = await async_client.get("/api/v1/auth/me", headers=headers)
    assert profile_res.status_code == 200
    profile = profile_res.json()
    assert profile["id"] == "user-login-1"
    assert profile["email"] == "login.success@example.com"
    assert profile["full_name"] == "Login Success"


@pytest.mark.asyncio
async def test_login_invalid_password(async_client: AsyncClient, auth_mock_db):
    _, user_storage = auth_mock_db
    test_user = User(
        id="user-invalid-pass",
        email="user.wrongpass@example.com",
        hashed_password=get_password_hash("ActualPassword123!"),
        is_active=True,
    )
    user_storage[test_user.id] = test_user

    login_payload = {
        "email": "user.wrongpass@example.com",
        "password": "WrongPassword!",
    }
    res = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert res.status_code == 401
    assert "invalid email or password" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_nonexistent_email(async_client: AsyncClient, auth_mock_db):
    login_payload = {
        "email": "does.not.exist@example.com",
        "password": "AnyPassword123!",
    }
    res = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert res.status_code == 401
    assert "invalid email or password" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_deactivated_user(async_client: AsyncClient, auth_mock_db):
    _, user_storage = auth_mock_db
    inactive_user = User(
        id="user-inactive",
        email="inactive@example.com",
        hashed_password=get_password_hash("Password123!"),
        is_active=False,
    )
    user_storage[inactive_user.id] = inactive_user

    login_payload = {
        "email": "inactive@example.com",
        "password": "Password123!",
    }
    res = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert res.status_code == 403
    assert "deactivated" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_profile_unauthorized_without_token(async_client: AsyncClient):
    res = await async_client.get("/api/v1/auth/me")
    assert res.status_code == 401
    assert "not authenticated" in res.json()["detail"].lower()
