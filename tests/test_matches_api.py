from unittest.mock import AsyncMock, MagicMock
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models.job_posting import JobPosting
from app.models.resume import Resume
from app.services.embedding_service import embedding_service


class MockCandidateRow:
    """Mock row returning item as row[0] and distance as row.distance."""
    def __init__(self, item, distance=0.25):
        self._item = item
        self.distance = distance

    def __getitem__(self, idx):
        if idx == 0:
            return self._item
        raise IndexError


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
def mock_matcher_db():
    """Mock database with sample resume and job posting pre-seeded."""
    session = AsyncMock(spec=AsyncSession)
    resumes_map = {}
    jobs_map = {}

    sample_resume = Resume(
        id="resume-uuid-1",
        filename="alice_resume.pdf",
        file_path="uploads/resumes/alice_resume.pdf",
        file_type="pdf",
        raw_text="Alice Smith, Senior Python Developer...",
        candidate_name="Alice Smith",
        email="alice@example.com",
        phone="555-0100",
        parsed_data={
            "contact_info": {"name": "Alice Smith", "email": "alice@example.com"},
            "summary": "Experienced Python developer",
            "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
            "experience": [
                {
                    "title": "Senior Python Developer",
                    "company": "Tech Corp",
                    "start_date": "2020",
                    "end_date": "2024",
                    "description": ["Built microservices"],
                }
            ],
            "education": [{"institution": "State University", "degree": "B.S."}],
            "projects": [],
            "certifications": [],
        },
        embedding=embedding_service._generate_deterministic_vector("Alice Python"),
    )
    resumes_map[sample_resume.id] = sample_resume

    sample_job = JobPosting(
        id="job-uuid-1",
        external_id="ext-job-1",
        title="Senior Python Backend Engineer",
        company_name="Acme Tech",
        description="Looking for Senior Python engineer with 4+ years experience. Required skills: Python, FastAPI.",
        location="Remote",
        work_type="Full-time",
        remote_allowed=True,
        skills=["Python", "FastAPI", "PostgreSQL", "AWS"],
        min_salary=120000.0,
        max_salary=160000.0,
        pay_period="YEARLY",
        embedding=embedding_service._generate_deterministic_vector("Senior Python Acme"),
    )
    jobs_map[sample_job.id] = sample_job

    async def mock_execute(stmt):
        stmt_str = str(stmt).lower()
        try:
            params = stmt.compile().params
        except Exception:
            params = {}

        param_values = {v for v in params.values() if isinstance(v, (str, int))}

        if "from resumes" in stmt_str:
            if "where resumes.id =" in stmt_str:
                matched = [resumes_map[k] for k in param_values if k in resumes_map]
                return MockResult(matched)
            # Vector candidate matching query
            return MockResult([MockCandidateRow(sample_resume, distance=0.20)])
        elif "from job_postings" in stmt_str:
            if "where job_postings.id =" in stmt_str:
                matched = [jobs_map[k] for k in param_values if k in jobs_map]
                return MockResult(matched)
            # Vector job matching query
            return MockResult([MockCandidateRow(sample_job, distance=0.20)])
        return MockResult([])

    session.execute = AsyncMock(side_effect=mock_execute)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    async def _override_get_db():
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    yield session
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_match_jobs_for_resume(async_client: AsyncClient, mock_matcher_db):
    """Test matching jobs for an existing resume."""
    resp = await async_client.post(f"{settings.API_V1_STR}/matches/resume/resume-uuid-1?limit=5")
    assert resp.status_code == 200
    data = resp.json()

    assert data["resume_id"] == "resume-uuid-1"
    assert data["candidate_name"] == "Alice Smith"
    assert len(data["matches"]) >= 1

    first_match = data["matches"][0]
    assert first_match["job_id"] == "job-uuid-1"
    assert first_match["title"] == "Senior Python Backend Engineer"
    assert 0.0 <= first_match["final_score"] <= 1.0
    assert first_match["rank"] == 1
    assert "skills_breakdown" in first_match
    assert "explanations" in first_match
    assert len(first_match["explanations"]) > 0


@pytest.mark.asyncio
async def test_match_jobs_for_resume_not_found(async_client: AsyncClient, mock_matcher_db):
    """Test 404 when resume does not exist."""
    resp = await async_client.post(f"{settings.API_V1_STR}/matches/resume/non-existent-uuid")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_match_candidates_for_job(async_client: AsyncClient, mock_matcher_db):
    """Test matching candidates for an existing job posting."""
    resp = await async_client.post(f"{settings.API_V1_STR}/matches/job/job-uuid-1?limit=5")
    assert resp.status_code == 200
    data = resp.json()

    assert data["job_id"] == "job-uuid-1"
    assert len(data["candidates"]) >= 1

    first_cand = data["candidates"][0]
    assert first_cand["resume_id"] == "resume-uuid-1"
    assert first_cand["candidate_name"] == "Alice Smith"
    assert 0.0 <= first_cand["final_score"] <= 1.0
    assert first_cand["rank"] == 1


@pytest.mark.asyncio
async def test_compare_resume_and_job(async_client: AsyncClient, mock_matcher_db):
    """Test direct pairwise comparison and SHAP explanation."""
    resp = await async_client.get(f"{settings.API_V1_STR}/matches/compare/resume-uuid-1/job-uuid-1")
    assert resp.status_code == 200
    data = resp.json()

    assert data["resume_id"] == "resume-uuid-1"
    assert data["job_id"] == "job-uuid-1"
    assert 0.0 <= data["final_score"] <= 1.0
    assert "features" in data
    assert "explanations" in data
    assert any(e["feature_name"] == "must_have_skill_match" for e in data["explanations"])
