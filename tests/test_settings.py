"""Unit tests for Settings validation and credential enforcement."""

import pytest
from pydantic import ValidationError
from app.core.config import Settings


def test_settings_requires_mandatory_credentials(monkeypatch):
    """Verify that SECRET_KEY, DATABASE_URL, and NEO4J_PASSWORD are strictly required without defaults."""
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    errors = exc_info.value.errors()
    missing_fields = {e["loc"][0] for e in errors}
    assert "SECRET_KEY" in missing_fields
    assert "DATABASE_URL" in missing_fields
    assert "NEO4J_PASSWORD" in missing_fields


def test_settings_rejects_empty_or_whitespace_credentials(monkeypatch):
    """Verify that empty or whitespace strings cannot silently bypass validation."""
    monkeypatch.setenv("SECRET_KEY", "   ")
    monkeypatch.setenv("DATABASE_URL", "   ")
    monkeypatch.setenv("NEO4J_PASSWORD", "   ")

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    errors = exc_info.value.errors()
    failed_fields = {e["loc"][0] for e in errors}
    assert "SECRET_KEY" in failed_fields
    assert "DATABASE_URL" in failed_fields
    assert "NEO4J_PASSWORD" in failed_fields


def test_settings_succeeds_with_valid_credentials(monkeypatch):
    """Verify that Settings instantiates correctly when valid credentials are provided."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-min-32-chars-long-12345")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test_user:test_pass@localhost:5432/test_db")
    monkeypatch.setenv("NEO4J_PASSWORD", "test-neo4j-secure-password")

    s = Settings(_env_file=None)
    assert s.SECRET_KEY == "test-secret-key-min-32-chars-long-12345"
    assert s.DATABASE_URL == "postgresql+asyncpg://test_user:test_pass@localhost:5432/test_db"
    assert s.NEO4J_PASSWORD == "test-neo4j-secure-password"
