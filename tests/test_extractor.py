import io
import pytest
from docx import Document
from app.services.extractor import ExtractionError, extract_text, extract_text_from_docx, extract_text_from_txt


def test_extract_text_from_txt():
    sample_text = "John Doe\nSoftware Engineer\nPython, FastAPI, Docker"
    content = sample_text.encode("utf-8")
    result = extract_text_from_txt(content)
    assert "John Doe" in result
    assert "FastAPI" in result


def test_extract_text_from_docx():
    doc = Document()
    doc.add_paragraph("Alice Smith")
    doc.add_paragraph("Senior Data Scientist")
    doc.add_paragraph("Skills: Machine Learning, PyTorch, SQL")
    
    file_stream = io.BytesIO()
    doc.save(file_stream)
    content = file_stream.getvalue()

    result = extract_text_from_docx(content)
    assert "Alice Smith" in result
    assert "Senior Data Scientist" in result
    assert "Machine Learning" in result


def test_extract_text_dispatch_unsupported():
    with pytest.raises(ExtractionError, match="Unsupported file format"):
        extract_text(b"malicious content", "malware.exe")


def test_extract_text_empty_content():
    with pytest.raises(ExtractionError, match="No extractable text found"):
        extract_text(b"   \n\n  ", "empty.txt")


def test_extract_text_pdf_with_pymupdf():
    """Test extracting text from PDF using PyMuPDF."""
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), "Dr. Jane Doe\nPrincipal AI Scientist\nPython, PyTorch, Kubernetes")
    pdf_bytes = doc.tobytes()
    doc.close()

    result = extract_text(pdf_bytes, "resume.pdf")
    assert "Jane Doe" in result
    assert "Principal AI Scientist" in result
    assert "PyTorch" in result


def test_extract_text_pdf_fallback_to_pypdf(monkeypatch):
    """Test PDF extraction falling back gracefully to pypdf when PyMuPDF is not available."""
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), "Fallback Candidate\nBackend Engineer\nFastAPI, PostgreSQL, Redis")
    pdf_bytes = doc.tobytes()
    doc.close()

    # Simulate fitz being unavailable
    import sys
    monkeypatch.setitem(sys.modules, "fitz", None)

    result = extract_text(pdf_bytes, "candidate.pdf")
    assert "Fallback Candidate" in result
    assert "Backend Engineer" in result
    assert "FastAPI" in result


def test_extract_text_empty_pdf():
    """Empty PDF bytes or blank PDF without text must raise ExtractionError."""
    with pytest.raises(ExtractionError, match="empty|No extractable text"):
        extract_text(b"", "empty.pdf")

    import fitz
    doc = fitz.open()
    doc.new_page()  # Blank page without text
    pdf_bytes = doc.tobytes()
    doc.close()

    with pytest.raises(ExtractionError, match="No extractable text found"):
        extract_text(pdf_bytes, "blank.pdf")


def test_extract_text_with_metadata_provenance(monkeypatch):
    """Verify that extract_text_with_metadata records the exact extractor used and does not silently fall back."""
    import fitz
    from app.services.extractor import extract_text_with_metadata

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), "Provenance Candidate\nSoftware Engineer\nPython, FastAPI")
    pdf_bytes = doc.tobytes()
    doc.close()

    # 1. Primary extractor: PyMuPDF
    text, meta = extract_text_with_metadata(pdf_bytes, "resume.pdf")
    assert "Provenance Candidate" in text
    assert meta["extractor"] == "PyMuPDF"
    assert meta["char_count"] > 0
    assert meta["word_count"] > 0

    # 2. Fallback extractor: pypdf when fitz is unavailable
    import sys
    monkeypatch.setitem(sys.modules, "fitz", None)
    text_fallback, meta_fallback = extract_text_with_metadata(pdf_bytes, "resume.pdf")
    assert "Provenance Candidate" in text_fallback
    assert meta_fallback["extractor"] == "pypdf"

    # 3. Text file extractor
    txt_content = b"Candidate\nPython, Django"
    text_txt, meta_txt = extract_text_with_metadata(txt_content, "resume.txt")
    assert meta_txt["extractor"] == "builtin-text"


