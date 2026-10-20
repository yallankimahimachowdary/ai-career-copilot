"""Unit tests for R9-6: Deterministic Rule-Based Parser Mode."""

from pathlib import Path
import pypdf
import pytest

from app.core.taxonomy import CANONICAL_SKILL_PATTERNS
from app.services.parser_agent import ParserAgent


def extract_pdf_text(path: Path) -> str:
    reader = pypdf.PdfReader(path)
    return "\n".join([page.extract_text() or "" for page in reader.pages]).strip()


@pytest.mark.asyncio
async def test_rule_based_parser_canonical_skills_and_logging(caplog):
    parser = ParserAgent()
    canonical_set = set(CANONICAL_SKILL_PATTERNS.keys())

    test_pdf = Path("uploads/resumes/candidate_a_resume.pdf")
    assert test_pdf.exists()
    raw_text = extract_pdf_text(test_pdf)

    with caplog.at_level("INFO"):
        parsed = await parser.parse(raw_text, mode="rule_based")

    # Assert mode was logged
    assert any("[ParserAgent] Executing parser in mode: 'rule_based'" in r.message for r in caplog.records)
    assert parsed.parse_metadata.get("parser_mode") == "rule_based"
    assert parsed.parse_metadata.get("parser_engine") == "rules"

    # Assert all extracted skills strictly belong to the canonical taxonomy
    assert len(parsed.skills) > 0
    non_canonical = [s for s in parsed.skills if s not in canonical_set]
    assert non_canonical == [], f"Non-canonical skills found in rule-based mode: {non_canonical}"

    # Verify deterministic output
    parsed_repeat = await parser.parse(raw_text, mode="rule_based")
    assert parsed.skills == parsed_repeat.skills
