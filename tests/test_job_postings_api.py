import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.job_posting import JobPosting
from app.services.embedding_service import embedding_service
from app.core.config import settings
from app.db.session import get_db
from app.main import app

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
def mock_db_session():
    """Fixture providing an in-memory mock database session."""
    session = AsyncMock()
    storage = {}

    def mock_add(instance):
        storage[instance.id] = instance

    async def mock_commit():
        pass

    async def mock_refresh(instance):
        pass

    async def mock_delete(instance):
        storage.pop(instance.id, None)

    async def mock_execute(statement):
        items = list(storage.values())
        return MockResult(items)

    session.add = MagicMock(side_effect=mock_add)
    session.commit = AsyncMock(side_effect=mock_commit)
    session.refresh = AsyncMock(side_effect=mock_refresh)
    session.delete = AsyncMock(side_effect=mock_delete)
    session.execute = AsyncMock(side_effect=mock_execute)

    async def _override_get_db():
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    yield session
    app.dependency_overrides.pop(get_db, None)

@pytest.mark.asyncio
async def test_list_jobs(async_client: AsyncClient, mock_db_session: AsyncSession):
    """Test listing job postings with pagination and filtering."""
    response = await async_client.get(f"{settings.API_V1_STR}/jobs")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

@pytest.mark.asyncio
async def test_get_job_not_found(async_client: AsyncClient, mock_db_session: AsyncSession):
    """Test getting a non-existent job posting returns 404."""
    response = await async_client.get(f"{settings.API_V1_STR}/jobs/invalid-id")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_search_similar_jobs(async_client: AsyncClient, mock_db_session: AsyncSession):
    """Test semantic search for jobs."""
    # We first insert a mock job posting with an embedding to find
    job = JobPosting(
        id="test-job-1",
        title="Python Developer",
        description="Looking for a Python dev with FastAPI experience.",
        company_name="Test Co",
        location="Remote",
        skills=["Python", "FastAPI"],
        embedding=embedding_service._generate_deterministic_vector("Python Developer")
    )
    job.distance = 0.15  # Mock the pgvector computed distance column
    mock_db_session.add(job)
    await mock_db_session.commit()

    search_payload = {
        "query": "Python developer",
        "limit": 5
    }
    response = await async_client.post(f"{settings.API_V1_STR}/jobs/search/similar", json=search_payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["id"] == "test-job-1"
    assert "similarity_score" in data[0]

@pytest.mark.asyncio
async def test_delete_job(async_client: AsyncClient, mock_db_session: AsyncSession):
    """Test deleting a job posting."""
    job = JobPosting(
        id="test-job-delete",
        title="To be deleted",
        description="Will be deleted.",
        company_name="Test Co",
    )
    mock_db_session.add(job)
    await mock_db_session.commit()

    # Delete the job
    response = await async_client.delete(f"{settings.API_V1_STR}/jobs/test-job-delete")
    assert response.status_code == 204

    # Verify it's gone
    response2 = await async_client.get(f"{settings.API_V1_STR}/jobs/test-job-delete")
    assert response2.status_code == 404
