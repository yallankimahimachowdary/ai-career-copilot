import pytest
from unittest.mock import AsyncMock
from app.core.config import settings
from app.services.parser_agent import ParserAgent
from app.schemas.resume import ContactInfo, ParsedResume

@pytest.mark.asyncio
async def test_default_upload_does_not_call_llm(monkeypatch):
    """
    S4 Test: Default upload (PARSER_MODE=rule_based) must NOT call LLM client.
    """
    parser = ParserAgent()
    
    # Mock LLM methods with spy that fails if called
    ollama_mock = AsyncMock(side_effect=RuntimeError("LLM should not be called in default mode"))
    openai_mock = AsyncMock(side_effect=RuntimeError("OpenAI should not be called in default mode"))
    monkeypatch.setattr(parser, "_parse_with_ollama", ollama_mock)
    monkeypatch.setattr(parser, "_parse_with_openai", openai_mock)
    
    text = "Jane Doe\nSenior Machine Learning Engineer with Python, PyTorch, and SQL experience."
    parsed = await parser.parse(text, metadata={"extractor": "PyMuPDF"})
    
    # Verify LLMs were never called
    assert ollama_mock.call_count == 0
    assert openai_mock.call_count == 0
    
    # Verify provenance recorded
    assert parsed.parse_metadata.get("parser_mode") == "rule_based"
    assert parsed.parse_metadata.get("parser_engine") == "rules"
    assert "Python" in parsed.skills
    assert "SQL" in parsed.skills


@pytest.mark.asyncio
async def test_opt_in_llm_mode_calls_llm(monkeypatch):
    """
    S4 Test: Explicit opt-in (PARSER_MODE=llm or mode='llm') calls LLM client.
    """
    parser = ParserAgent()
    
    mock_llm_resume = ParsedResume(
        contact_info=ContactInfo(name="Test Candidate", email="test@example.com"),
        summary="LLM extracted summary",
        skills=["Python", "FastAPI"],
        experience=[],
        education=[],
    )
    ollama_mock = AsyncMock(return_value=mock_llm_resume)
    monkeypatch.setattr(parser, "_parse_with_ollama", ollama_mock)
    
    text = "Test Candidate profile text"
    parsed = await parser.parse(text, mode="llm")
    
    # Assert LLM was called
    assert ollama_mock.call_count == 1
    assert parsed.parse_metadata.get("parser_mode") == "llm"
    assert parsed.parse_metadata.get("parser_engine") == "ollama"


@pytest.mark.asyncio
async def test_stored_record_contains_parser_mode():
    """
    S4 Test: The serialized record dictionary preserves parser_mode in parse_metadata.
    """
    parser = ParserAgent()
    text = "Alex Smith\nCloud Engineer with AWS, Terraform, Docker, and Kubernetes expertise."
    parsed = await parser.parse(text)
    
    dumped = parsed.model_dump()
    assert "parse_metadata" in dumped
    assert dumped["parse_metadata"]["parser_mode"] == "rule_based"
    assert dumped["parse_metadata"]["parser_engine"] == "rules"
