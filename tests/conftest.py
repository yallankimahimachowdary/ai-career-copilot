import os
import pytest

# Ensure test-only dummy credentials exist for test discovery and execution
# when a real .env file is not present. These are never used in production.
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-testing-only-32chars")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:test@localhost:5432/ai_career_copilot_test")
os.environ.setdefault("NEO4J_PASSWORD", "test-neo4j-password")

from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
