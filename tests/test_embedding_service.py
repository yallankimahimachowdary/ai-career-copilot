import math
import pytest
from app.services.embedding_service import embedding_service


@pytest.mark.asyncio
async def test_embedding_dimension_and_norm():
    text = "FastAPI backend engineer with PostgreSQL and Redis skills"
    vec = await embedding_service.get_embedding(text)

    # Validate vector length matches setting
    assert len(vec) == 1536

    # Validate L2 normalization (norm should be ~ 1.0)
    norm = math.sqrt(sum(x * x for x in vec))
    assert abs(norm - 1.0) < 1e-4


@pytest.mark.asyncio
async def test_deterministic_embedding_consistency():
    text = "Machine Learning Engineer with PyTorch"
    vec1 = await embedding_service.get_embedding(text)
    vec2 = await embedding_service.get_embedding(text)

    assert vec1 == vec2
