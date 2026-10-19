"""Unit tests for credential redaction and safe error logging (Remediation R8).

Verifies that sensitive credentials (ADZUNA_APP_ID, ADZUNA_APP_KEY, etc.)
never appear in string representations of exceptions, error attribution records,
or logger outputs.
"""

import logging
import os
import httpx
import pytest

from app.core.logging import logger
from app.core.redaction import (
    redact_credentials,
    redact_error_record,
    redact_exception,
    redact_url,
)
from app.services.graph_orchestrator import _build_error_record


def test_redact_credentials_query_string():
    raw_url = "https://api.adzuna.com/v1/api/jobs/in/search/1?app_id=test_id_1234&app_key=secret_key_56789abcdef&results_per_page=20"
    sanitized = redact_credentials(raw_url)

    assert "test_id_1234" not in sanitized
    assert "secret_key_56789abcdef" not in sanitized
    assert "app_id=[REDACTED]" in sanitized
    assert "app_key=[REDACTED]" in sanitized
    assert "results_per_page=20" in sanitized


def test_redact_credentials_env_variable(monkeypatch):
    test_id = "dz_id_9999"
    test_key = "dz_key_super_secret_token_12345678"
    monkeypatch.setenv("ADZUNA_APP_ID", test_id)
    monkeypatch.setenv("ADZUNA_APP_KEY", test_key)

    message = f"Connection to Adzuna failed with auth {test_id}:{test_key} on worker node"
    sanitized = redact_credentials(message)

    assert test_id not in sanitized
    assert test_key not in sanitized
    assert "[ADZUNA_APP_ID_REDACTED]" in sanitized
    assert "[ADZUNA_APP_KEY_REDACTED]" in sanitized


def test_request_error_does_not_leak_credentials_in_exception_or_record(monkeypatch):
    test_id = "my_app_id_888"
    test_key = "my_app_key_secret_999_xyz123"
    monkeypatch.setenv("ADZUNA_APP_ID", test_id)
    monkeypatch.setenv("ADZUNA_APP_KEY", test_key)

    url_with_creds = f"https://api.adzuna.com/v1/api/jobs/in/search/1?app_id={test_id}&app_key={test_key}&what=Engineer"
    request = httpx.Request("GET", url_with_creds)
    exc = httpx.ConnectError("Failed to connect to gateway", request=request)

    # 1. Test redact_exception
    redacted_exc_str = redact_exception(exc)
    assert test_id not in redacted_exc_str
    assert test_key not in redacted_exc_str
    assert "[REDACTED]" in redacted_exc_str or "REDACTED" in redacted_exc_str

    # 2. Test _build_error_record
    error_record = _build_error_record(
        agent_name="market",
        step="fetch_adzuna",
        exc=exc,
    )

    record_str = str(error_record)
    assert test_id not in record_str
    assert test_key not in record_str
    assert error_record["error_message"]
    assert test_id not in error_record["error_message"]
    assert test_key not in error_record["error_message"]


def test_logger_redacts_credentials_automatically(monkeypatch, caplog):
    test_id = "log_id_7777"
    test_key = "log_key_8888_secret_secret_123"
    monkeypatch.setenv("ADZUNA_APP_ID", test_id)
    monkeypatch.setenv("ADZUNA_APP_KEY", test_key)

    with caplog.at_level(logging.INFO):
        logger.info(f"Dispatching query with URL https://api.adzuna.com/v1/api/jobs/in/search/1?app_id={test_id}&app_key={test_key}")

    logged_text = caplog.text
    assert test_id not in logged_text
    assert test_key not in logged_text
    assert "[REDACTED]" in logged_text or "REDACTED" in logged_text


def test_redact_error_record_nested():
    nested_record = {
        "status": "error",
        "nested": {
            "query": "https://api.adzuna.com/search?app_id=sub_id_111&app_key=sub_key_222",
            "codes": [1, 2, "details: app_key=sub_key_222"],
        },
    }

    sanitized = redact_error_record(nested_record)
    assert "sub_id_111" not in str(sanitized)
    assert "sub_key_222" not in str(sanitized)
    assert "app_id=[REDACTED]" in sanitized["nested"]["query"]
    assert "app_key=[REDACTED]" in sanitized["nested"]["codes"][2]
