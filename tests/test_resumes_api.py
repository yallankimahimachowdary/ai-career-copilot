import io
from unittest.mock import AsyncMock, MagicMock
import pytest
from httpx import AsyncClient
from app.db.session import get_db
from app.main import app
from app.models.resume import Resume


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
        # Return all or filtered items based on storage
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
    yield session, storage
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_upload_resume_success(async_client: AsyncClient, mock_db_session):
    _, storage = mock_db_session
    sample_content = b"""
    Mahima Sharma
    mahima@example.com
    Skills: Python, FastAPI, Docker, PostgreSQL
    Experience: Software Engineer at Acme Corp
    """
    files = {"file": ("resume.txt", sample_content, "text/plain")}

    response = await async_client.post("/api/v1/resumes/upload", files=files)
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "resume.txt"
    assert data["candidate_name"] == "Mahima Sharma"
    assert data["email"] == "mahima@example.com"
    assert data["embedding_dimension"] == 1536
    assert "Python" in data["parsed_data"]["skills"]
    assert data["id"] in storage


@pytest.mark.asyncio
async def test_upload_resume_invalid_extension(async_client: AsyncClient, mock_db_session):
    files = {"file": ("script.sh", b"echo 'hello'", "text/x-shellscript")}
    response = await async_client.post("/api/v1/resumes/upload", files=files)
    assert response.status_code == 400
    assert "Invalid file type" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_resume_empty_text(async_client: AsyncClient, mock_db_session):
    files = {"file": ("empty.txt", b"    \n   ", "text/plain")}
    response = await async_client.post("/api/v1/resumes/upload", files=files)
    assert response.status_code == 422
    assert "No extractable text found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_resumes(async_client: AsyncClient, mock_db_session):
    response = await async_client.get("/api/v1/resumes")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_resume_not_found(async_client: AsyncClient, mock_db_session):
    response = await async_client.get("/api/v1/resumes/nonexistent-id")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
