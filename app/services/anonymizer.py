"""Resume PII Anonymization Service for Experiment Pipeline and Remote LLM Calls."""

import re
from typing import Optional


def anonymize_resume(text: str, candidate_name: Optional[str] = None) -> str:
    """Remove candidate name, email, phone number, address, and hyperlinks from resume text."""
    if not text:
        return ""

    cleaned = text

    # 1. Mask URLs and hyperlinks (http, https, www, linkedin.com, github.com)
    url_pattern = r"(https?://\S+|www\.\S+|[a-zA-Z0-9.\-_]+(?:\.com|\.in|\.org|\.io|\.net|\.dev)/\S*)"
    cleaned = re.sub(url_pattern, "[LINK]", cleaned, flags=re.IGNORECASE)

    # 2. Mask Email addresses (including spaced emails often produced by PDF extractors)
    email_pattern = r"[a-zA-Z0-9_.+-]+(?:\s*@\s*|\s*\[at\]\s*)[a-zA-Z0-9-]+(?:\s*\.\s*|\s*\[dot\]\s*)[a-zA-Z0-9-.]+"
    cleaned = re.sub(email_pattern, "[EMAIL]", cleaned, flags=re.IGNORECASE)


    # 3. Mask Phone numbers (Indian, international, US with various formatting)
    phone_pattern = r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,5}[-.\s]?\d{3,5}\b"
    # Filter to match tokens that have at least 7 digits
    def replace_phone(match):
        digits = re.sub(r"\D", "", match.group(0))
        if len(digits) >= 9:
            return "[PHONE]"
        return match.group(0)

    cleaned = re.sub(phone_pattern, replace_phone, cleaned)

    # 4. Mask Explicit Candidate Name if provided
    if candidate_name and candidate_name.strip():
        # Match the full raw candidate name including any initial dot / space (e.g. "S.Deepika", "S. Deepika", "S Deepika")
        raw_name = candidate_name.strip()
        cleaned = re.sub(rf"\b{re.escape(raw_name)}\b", "[NAME]", cleaned, flags=re.IGNORECASE)

        # Also support initial-first patterns like S.Deepika or S. Deepika when parts are split
        parts = [p.strip() for p in re.split(r"[\s.]+", raw_name) if p.strip()]
        for part in sorted(parts, key=len, reverse=True):
            if len(part) > 1:
                # Match standalone word part
                cleaned = re.sub(rf"\b{re.escape(part)}\b", "[NAME]", cleaned, flags=re.IGNORECASE)
                # Match single-letter initial prefix immediately attached or followed by dot/space: e.g. S.Deepika or S. [NAME]
                cleaned = re.sub(rf"\b[A-Za-z]\.?\s*{re.escape(part)}\b", "[NAME]", cleaned, flags=re.IGNORECASE)
                cleaned = re.sub(rf"\b[A-Za-z]\.?\s*\[NAME\]", "[NAME]", cleaned, flags=re.IGNORECASE)

        # Remove any leftover dangling single-letter initial tokens associated with candidate name
        initials = [p.strip() for p in re.split(r"[\s.]+", raw_name) if len(p.strip()) == 1]
        for init in initials:
            # Mask leftover initial preceding [NAME] or succeeding [NAME] (e.g. "S. [NAME]", "[NAME], S.")
            cleaned = re.sub(rf"\b{re.escape(init)}\.?\s*\[NAME\]", "[NAME]", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(rf"\[NAME\]\s*,?\s*{re.escape(init)}\b\.?", "[NAME]", cleaned, flags=re.IGNORECASE)

    # Also mask lines that look like candidate name headers at the very start
    lines = cleaned.splitlines()
    if lines:
        first_line = lines[0].strip()
        if first_line and not any(kw in first_line.lower() for kw in ["resume", "curriculum", "summary", "profile", "objective", "skills"]):
            if len(first_line.split()) <= 4 and re.match(r"^[A-Za-z\s.]+$", first_line):
                lines[0] = "[CANDIDATE_NAME]"
        cleaned = "\n".join(lines)

    # 5. Mask Physical Address Patterns (Pin codes, Indian states, street lines)
    pincode_pattern = r"\b\d{6}\b"  # 6-digit Indian PIN code
    cleaned = re.sub(pincode_pattern, "[PINCODE]", cleaned)

    address_keywords = r"(?:Plot|Flat|House|Door|Street|Road|Nagar|Colony|Sector|Layout|Apartment|Apt|Bldg)[^,\n]+,[^,\n]+"
    cleaned = re.sub(address_keywords, "[ADDRESS]", cleaned, flags=re.IGNORECASE)

    # Clean up duplicate replacement tokens
    cleaned = re.sub(r"(\[NAME\]\s*)+", "[NAME] ", cleaned)
    cleaned = re.sub(r"(\[LINK\]\s*)+", "[LINK] ", cleaned)

    return cleaned.strip()
