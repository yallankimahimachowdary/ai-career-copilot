"""Resume PII Anonymization Service for Experiment Pipeline and Remote LLM Calls."""

import re
from typing import Optional


def anonymize_resume(
    text: str,
    candidate_name: Optional[str] = None,
    strip_institutions: bool = True,
) -> str:
    """Remove candidate name, email, phone number, address, and hyperlinks from resume text.

    Args:
        text: Raw extracted resume text.
        candidate_name: Optional candidate name string to explicitly mask.
        strip_institutions: When True (default), strips educational and institutional affiliations
            (universities, colleges, polytechnics, institutes, schools).

            Design Rationale for `strip_institutions=True`:
            Educational prestige bias is a well-documented source of systematic skew in LLM evaluation
            and candidate ranking. LLMs prompted with elite university names systematically inflate
            suitability and ranking scores regardless of objective skill overlap or experience relevance.
            Stripping institutional affiliations normalizes candidate profiles to substantive skills,
            demonstrated competencies, and verifiable project impacts. Furthermore, highly specialized
            universities, departments, or research labs often serve as pseudo-identifiers that deanonymize
            candidates.
    """
    if not text:
        return ""

    cleaned = text

    # 1. Mask URLs and hyperlinks (http, https, www, linkedin.com, github.com)
    url_pattern = r"(https?://\S+|www\.\S+|[a-zA-Z0-9.\-_]+(?:\.com|\.in|\.org|\.io|\.net|\.dev)/\S*)"
    cleaned = re.sub(url_pattern, "[LINK]", cleaned, flags=re.IGNORECASE)

    # 2. Mask Email addresses (including spaced emails often produced by PDF extractors)
    email_pattern = r"[a-zA-Z0-9_.+-]+(?:\s*@\s*|\s*\[at\]\s*)[a-zA-Z0-9-]+(?:\s*\.\s*|\s*\[dot\]\s*)[a-zA-Z0-9-.]+"
    cleaned = re.sub(email_pattern, "[EMAIL]", cleaned, flags=re.IGNORECASE)

    # 3. Mask PIN and postal codes (Indian 6-digit PIN and labeled US ZIP codes)
    us_zip_pattern = r"\b(?:ZIP|Postal Code)\s*[:#-]?\s*\d{5}(?:-\d{4})?\b"
    cleaned = re.sub(us_zip_pattern, "[PINCODE]", cleaned, flags=re.IGNORECASE)

    pincode_pattern = r"(?:\b(?:PIN|PINCODE|POSTAL\s*CODE)\s*[:#-]?\s*)?\b[1-9][0-9]{5}\b"
    cleaned = re.sub(pincode_pattern, "[PINCODE]", cleaned, flags=re.IGNORECASE)

    # 4. Mask Phone numbers (Indian, international, US with various formatting)
    phone_pattern = r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,5}[-.\s]?\d{3,5}\b"

    def replace_phone(match):
        digits = re.sub(r"\D", "", match.group(0))
        if len(digits) >= 9:
            return "[PHONE]"
        return match.group(0)

    cleaned = re.sub(phone_pattern, replace_phone, cleaned)

    # 5. Mask Explicit Candidate Name if provided
    if candidate_name and candidate_name.strip():
        raw_name = candidate_name.strip()
        cleaned = re.sub(rf"\b{re.escape(raw_name)}\b", "[NAME]", cleaned, flags=re.IGNORECASE)

        parts = [p.strip() for p in re.split(r"[\s.]+", raw_name) if p.strip()]
        for part in sorted(parts, key=len, reverse=True):
            if len(part) > 1:
                cleaned = re.sub(rf"\b{re.escape(part)}\b", "[NAME]", cleaned, flags=re.IGNORECASE)
                cleaned = re.sub(rf"\b[A-Za-z]\.?\s*{re.escape(part)}\b", "[NAME]", cleaned, flags=re.IGNORECASE)
                cleaned = re.sub(rf"\b[A-Za-z]\.?\s*\[NAME\]", "[NAME]", cleaned, flags=re.IGNORECASE)

        initials = [p.strip() for p in re.split(r"[\s.]+", raw_name) if len(p.strip()) == 1]
        for init in initials:
            cleaned = re.sub(rf"\b{re.escape(init)}\.?\s*\[NAME\]", "[NAME]", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(rf"\[NAME\]\s*,?\s*{re.escape(init)}\b\.?", "[NAME]", cleaned, flags=re.IGNORECASE)

    lines = cleaned.splitlines()
    if lines:
        first_line = lines[0].strip()
        if first_line and not any(kw in first_line.lower() for kw in ["resume", "curriculum", "summary", "profile", "objective", "skills"]):
            if len(first_line.split()) <= 4 and re.match(r"^[A-Za-z\s.]+$", first_line):
                lines[0] = "[CANDIDATE_NAME]"
        cleaned = "\n".join(lines)

    # 6. Mask Physical Street Address Patterns
    address_keywords = (
        r"(?:\b(?:Plot|Flat|House|Door|Room|Suite|Apt|Apartment|Bldg|Building)\s*(?:No\.?|#)?\s*[\w\d/-]+[,\s]+)?"
        r"(?:[A-Za-z0-9\s#.,/-]{2,40})?"
        r"\b(?:Street|St\.|Road|Rd\.|Avenue|Ave\.|Nagar|Colony|Sector|Layout|Enclave|Bagh|Gali|Lane|Cross|Main)\b"
        r"(?:[,\s]+[A-Za-z\s]+){1,3}"
    )
    cleaned = re.sub(address_keywords, "[ADDRESS]", cleaned, flags=re.IGNORECASE)

    labeled_address = r"\b(?:Address|Permanent Address|Current Address)\s*:\s*[^\n]+"
    cleaned = re.sub(labeled_address, "[ADDRESS]", cleaned, flags=re.IGNORECASE)

    # 6. Mask Educational and Research Institutions if strip_institutions is True
    if strip_institutions:
        institution_patterns = [
            r"\b(?:[A-Z][A-Za-z0-9&.',\s]{1,40}\s+)?(?:University|College|Polytechnic|Academy|Institute of Technology|Institute of Science|Institute of Engineering)\b",
            r"\b(?:IIT|NIT|IIIT|BITS)(?:\s+[A-Z][a-z]+)?\b",
            r"\b(?:Indian|National|Birla|International)\s+Institute\s+of\s+[A-Za-z\s]+(?:,\s*[A-Za-z]+)?\b",
            r"\b(?:Stanford|Harvard|MIT|Oxford|Cambridge|Carnegie Mellon|Berkeley|Caltech|Princeton|Yale|Columbia|Cornell)\b",
        ]
        for pat in institution_patterns:
            cleaned = re.sub(pat, "[INSTITUTION]", cleaned)

    # Clean up duplicate replacement tokens
    cleaned = re.sub(r"(\[NAME\]\s*)+", "[NAME] ", cleaned)
    cleaned = re.sub(r"(\[LINK\]\s*)+", "[LINK] ", cleaned)
    cleaned = re.sub(r"(\[ADDRESS\]\s*)+", "[ADDRESS] ", cleaned)
    cleaned = re.sub(r"(\[PINCODE\]\s*)+", "[PINCODE] ", cleaned)
    cleaned = re.sub(r"(\[INSTITUTION\]\s*)+", "[INSTITUTION] ", cleaned)

    return cleaned.strip()
