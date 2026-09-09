import io
import re
from pypdf import PdfReader
from docx import Document


class ExtractionError(Exception):
    """Exception raised for text extraction errors."""
    pass


def clean_text(text: str) -> str:
    """Normalize extracted text by removing control chars and excessive whitespace."""
    if not text:
        return ""
    # Normalize line breaks
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Replace multiple spaces/tabs with single space while keeping linebreaks
    text = re.sub(r"[ \t]+", " ", text)
    # Collapse more than two consecutive newlines into two
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text_from_pdf(content: bytes) -> str:
    """Extract plain text from a PDF byte stream."""
    try:
        reader = PdfReader(io.BytesIO(content))
        extracted_pages = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                extracted_pages.append(page_text)
        return clean_text("\n\n".join(extracted_pages))
    except Exception as e:
        raise ExtractionError(f"Failed to extract text from PDF: {str(e)}") from e


def extract_text_from_docx(content: bytes) -> str:
    """Extract plain text from a DOCX byte stream."""
    try:
        doc = Document(io.BytesIO(content))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    paragraphs.append(row_text)
        return clean_text("\n\n".join(paragraphs))
    except Exception as e:
        raise ExtractionError(f"Failed to extract text from DOCX: {str(e)}") from e


def extract_text_from_txt(content: bytes) -> str:
    """Extract plain text from a TXT byte stream with encoding fallback."""
    for encoding in ["utf-8", "latin-1", "cp1252"]:
        try:
            return clean_text(content.decode(encoding))
        except UnicodeDecodeError:
            continue
    raise ExtractionError("Failed to decode text file with supported encodings (utf-8, latin-1, cp1252).")


def extract_text(content: bytes, filename: str) -> str:
    """Extract clean plain text based on file extension."""
    lower_filename = filename.lower()
    if lower_filename.endswith(".pdf"):
        text = extract_text_from_pdf(content)
    elif lower_filename.endswith(".docx"):
        text = extract_text_from_docx(content)
    elif lower_filename.endswith(".txt"):
        text = extract_text_from_txt(content)
    else:
        raise ExtractionError(f"Unsupported file format for '{filename}'. Allowed: .pdf, .docx, .txt")

    if not text:
        raise ExtractionError(f"No extractable text found in '{filename}'. File might be empty or scanned image.")

    return text
