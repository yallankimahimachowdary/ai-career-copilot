"""Tests for Resume PII Anonymizer Service."""

from app.services.anonymizer import anonymize_resume


def test_anonymize_email_and_phone():
    text = "Contact me at sdeepika3057@gmail.com or call +91-9876543210."
    result = anonymize_resume(text)
    assert "[EMAIL]" in result
    assert "sdeepika3057@gmail.com" not in result
    assert "[PHONE]" in result
    assert "9876543210" not in result


def test_anonymize_links_and_urls():
    text = "GitHub: https://github.com/mahimachowdary and LinkedIn: linkedin.com/in/mahima"
    result = anonymize_resume(text)
    assert "https://github.com" not in result
    assert "[LINK]" in result


def test_anonymize_candidate_initials():
    text = "Resume of S.Deepika, Biotechnology specialist. S. Deepika researched oncology."
    result = anonymize_resume(text, candidate_name="S.Deepika")
    assert "S.Deepika" not in result
    assert "S. Deepika" not in result
    assert "S." not in result
    assert "Deepika" not in result
    assert "[NAME]" in result


def test_anonymize_spaced_initial_and_suffix():
    text = "Deepika S. worked on bioinformatics pipeline. Contact S Deepika for details."
    result = anonymize_resume(text, candidate_name="S.Deepika")
    assert "Deepika" not in result
    assert "Deepika S." not in result
    assert "S Deepika" not in result
    assert "[NAME]" in result


def test_anonymize_multiword_name():
    text = "Candidate YALLANKI MAHIMA CHOWDARY has 3 years of Python experience."
    result = anonymize_resume(text, candidate_name="YALLANKI MAHIMA CHOWDARY")
    assert "MAHIMA" not in result
    assert "CHOWDARY" not in result
    assert "YALLANKI" not in result
    assert "[NAME]" in result
