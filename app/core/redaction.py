"""Security redaction utilities for sensitive API credentials and URL query strings."""

import os
import re
from typing import Any, Dict, Optional, Union

# Regex patterns matching Adzuna query parameters or key-value assignments
_APP_ID_PARAM_PATTERN = re.compile(r"(\bapp_id=)[^&\s\"'>]+", re.IGNORECASE)
_APP_KEY_PARAM_PATTERN = re.compile(r"(\bapp_key=)[^&\s\"'>]+", re.IGNORECASE)
_API_KEY_PARAM_PATTERN = re.compile(r"(\bapi_key=)[^&\s\"'>]+", re.IGNORECASE)


def redact_credentials(text: Optional[str]) -> str:
    """Redact sensitive query string parameters and literal credentials from a string."""
    if not text:
        return "" if text is None else str(text)

    sanitized = str(text)

    # 1. Redact key-value credentials and URL query parameters
    sanitized = _APP_ID_PARAM_PATTERN.sub(r"\1[REDACTED]", sanitized)
    sanitized = _APP_KEY_PARAM_PATTERN.sub(r"\1[REDACTED]", sanitized)
    sanitized = _API_KEY_PARAM_PATTERN.sub(r"\1[REDACTED]", sanitized)

    # 2. Redact literal environment values if set (avoid redacting short trivial strings)
    for env_var in ("ADZUNA_APP_ID", "ADZUNA_APP_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY"):
        val = os.environ.get(env_var)
        if val and len(val.strip()) >= 4:
            sanitized = sanitized.replace(val.strip(), f"[{env_var}_REDACTED]")

    return sanitized


def redact_url(url: Any) -> str:
    """Safely convert any URL or string to a redacted string representation."""
    if url is None:
        return ""
    return redact_credentials(str(url))


def redact_exception(exc: Exception) -> str:
    """Generate a redacted string representation of an exception."""
    req = getattr(exc, "request", None)
    req_info = ""
    if req and hasattr(req, "url"):
        req_info = f" [request: {redact_url(req.url)}]"
    raw_str = f"{type(exc).__name__}: {str(exc)}{req_info}"
    return redact_credentials(raw_str)



def redact_error_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively redact strings in an error audit dictionary."""
    sanitized: Dict[str, Any] = {}
    for k, v in record.items():
        if isinstance(v, str):
            sanitized[k] = redact_credentials(v)
        elif isinstance(v, dict):
            sanitized[k] = redact_error_record(v)
        elif isinstance(v, list):
            sanitized[k] = [
                redact_credentials(item) if isinstance(item, str)
                else (redact_error_record(item) if isinstance(item, dict) else item)
                for item in v
            ]
        else:
            sanitized[k] = v
    return sanitized
