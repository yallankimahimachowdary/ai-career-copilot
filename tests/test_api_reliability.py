"""
tests/test_api_reliability.py
------------------------------
Tests for API input validation, pagination bounds, public health accessibility,
and error response sanitization.
"""

from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.db.session import get_db
from app.main import app


@pytest.mark.asyncio
async def test_public_health_endpoint_accessible_without_auth(async_client: AsyncClient):
    """Verify that health check endpoints do not require authentication."""
    # Test root/public health
    res = await async_client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") in ("ok", "healthy")


@pytest.mark.asyncio
async def test_input_validation_invalid_email(async_client: AsyncClient):
    """Verify that registering with an invalid email format fails with 422."""
    res = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "not-an-email",
            "password": "Password123!",
            "full_name": "Test User",
        },
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_input_validation_short_password(async_client: AsyncClient):
    """Verify that registering with a password shorter than 8 chars fails with 422."""
    res = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "valid@example.com",
            "password": "short",
            "full_name": "Test User",
        },
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_input_validation_empty_login_payload(async_client: AsyncClient):
    """Verify that empty login payload fails with 422."""
    res = await async_client.post(
        "/api/v1/auth/login",
        json={},
    )
    assert res.status_code == 422


from app.api.deps import get_current_user
from app.models.user import User


@pytest.fixture
def auth_override():
    mock_user = User(
        id="rel-user-1",
        email="reliability@example.com",
        full_name="Reliability User",
        is_active=True,
        is_superuser=False,
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield mock_user
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_pagination_bounds_negative_skip(async_client: AsyncClient, auth_override):
    """Verify that negative skip parameter is rejected with 422."""
    res = await async_client.get("/api/v1/resumes?skip=-5&limit=20")
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_pagination_bounds_excessive_limit(async_client: AsyncClient, auth_override):
    """Verify that limit > 100 is rejected with 422."""
    res = await async_client.get("/api/v1/resumes?skip=0&limit=500")
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_pagination_bounds_zero_limit(async_client: AsyncClient, auth_override):
    """Verify that limit < 1 is rejected with 422."""
    res = await async_client.get("/api/v1/resumes?skip=0&limit=0")
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_error_response_sanitization_masks_internals_in_production(auth_override):
    """
    Verify that unhandled server errors do not leak stack traces, database internals,
    or secret tokens when running in production mode.
    """
    from httpx import ASGITransport

    mock_db = AsyncMock()
    mock_db.execute.side_effect = RuntimeError("Database connection string: postgresql://admin:SECRET_PASSWORD_123@db:5432/db")

    async def _override_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_db

    try:
        # Patch settings to simulate production environment
        with patch.object(settings, "DEBUG", False), patch.object(settings, "ENVIRONMENT", "production"):
            transport = ASGITransport(app=app, raise_app_exceptions=False)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                res = await client.get("/api/v1/resumes?skip=0&limit=10")
                assert res.status_code == 500
                data = res.json()
                # Must not leak the secret password or raw exception traceback
                assert "SECRET_PASSWORD_123" not in res.text
                assert "Traceback" not in res.text
                assert data.get("detail") == "An unexpected internal server error occurred."
    finally:
        app.dependency_overrides.pop(get_db, None)

