import pytest
import pandas as pd
from unittest.mock import patch, MagicMock, AsyncMock
from scripts.seed_jobs import process_batch
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.job_posting import JobPosting

@pytest.mark.asyncio
async def test_process_batch_skip_embeddings():
    """Test that process_batch correctly maps pandas rows to JobPosting records."""
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    batch = [
        {
            "job_id": "12345",
            "title": "Software Engineer",
            "description": "Great job.",
            "company_name": "Tech Corp",
            "location": "New York",
            "formatted_work_type": "Full-time",
            "remote_allowed": 1.0,
            "min_salary": 100000.0,
            "max_salary": 150000.0,
            "med_salary": float("nan"),
            "pay_period": "YEARLY",
            "skills": ["Python", "FastAPI"]
        },
        {
            "title": "Invalid Job",
            # missing job_id and description, should be handled/skipped or fail gracefully based on script logic
        }
    ]

    # Run the batch processor skipping embeddings for speed
    await process_batch(mock_session, batch, skip_embeddings=True)

    # Verify that session.execute was called with the insert statement
    assert mock_session.execute.called
    assert mock_session.commit.called

@pytest.mark.asyncio
async def test_process_batch_with_embeddings():
    """Test that process_batch calls the embedding service when skip_embeddings=False."""
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    batch = [
        {
            "job_id": "67890",
            "title": "Data Scientist",
            "description": "Analyze data.",
            "skills": ["Python", "Pandas"]
        }
    ]

    with patch("scripts.seed_jobs.embedding_service") as mock_embedding_service:
        # We need get_embedding to be an async mock returning a vector
        async def mock_get_embedding(text):
            return [0.1] * 1536
        
        mock_embedding_service.get_embedding = mock_get_embedding
        mock_embedding_service.construct_job_embed_text.return_value = "Mock text"

        await process_batch(mock_session, batch, skip_embeddings=False)

        assert mock_embedding_service.construct_job_embed_text.called
