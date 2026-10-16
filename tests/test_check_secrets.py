"""
tests/test_check_secrets.py
---------------------------
Pytest suite for secret scanning, staged Git scanning, and metadata sanitization.
"""

import os
from pathlib import Path
import subprocess
import sys
import pytest

from scripts.check_secrets import (
    SECRET_PATTERNS,
    get_staged_files,
    is_binary_content,
    load_env_secrets,
    main,
    scan_content,
    scan_file,
    scan_repository,
    scan_staged,
    should_exclude_dir,
    should_exclude_path,
)
from scripts.run_ranking_experiment import sanitize_experiment_metadata


def _init_git_repo(path: Path) -> None:
    """Helper to initialize a bare minimum git repo for tests."""
    subprocess.run(["git", "init"], cwd=str(path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=str(path), capture_output=True, check=True)


# ==============================================================================
# Existing baseline tests (preserved)
# ==============================================================================

def test_scanner_on_artifacts_and_docs():
    """Verify that artifacts/ and docs/ pass the secret scan with zero exposed secrets."""
    repo_root = Path(__file__).resolve().parent.parent
    cmd = [sys.executable, str(repo_root / "scripts" / "check_secrets.py"), "artifacts", "docs"]
    res = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True)

    assert res.returncode == 0, f"check_secrets failed on artifacts/docs:\n{res.stdout}\n{res.stderr}"
    assert "No exposed secrets or key patterns detected" in res.stdout


def test_scanner_detects_google_api_key_pattern(tmp_path: Path):
    """Verify that AIza... key pattern is detected and flagged."""
    dummy_file = tmp_path / "dummy_code.py"
    dummy_file.write_text("API_KEY = '" + "AIza" + "SyDummyKeyForTestingPurposes12345'", encoding="utf-8")

    findings = scan_file(dummy_file, SECRET_PATTERNS, env_secrets={})
    assert len(findings) == 1
    line_no, desc = findings[0]
    assert line_no == 1
    assert "Google API Key" in desc


def test_scanner_detects_gemini_token_pattern(tmp_path: Path):
    """Verify that AQ.Ab... token pattern is detected and flagged."""
    dummy_file = tmp_path / "dummy_log.json"
    dummy_file.write_text('{"token": "' + "AQ." + 'AbSyntheticTokenForTesting12345"}', encoding="utf-8")

    findings = scan_file(dummy_file, SECRET_PATTERNS, env_secrets={})
    assert len(findings) == 1
    line_no, desc = findings[0]
    assert line_no == 1
    assert "Gemini / Google Token" in desc


def test_scanner_detects_groq_api_key_pattern(tmp_path: Path):
    """Verify that gsk_... key pattern is detected and flagged."""
    dummy_file = tmp_path / "dummy_env.txt"
    dummy_file.write_text("GROQ_KEY = '" + "gsk_" + "syntheticGroqApiKeyForTesting1234567890'", encoding="utf-8")

    findings = scan_file(dummy_file, SECRET_PATTERNS, env_secrets={})
    assert len(findings) == 1
    line_no, desc = findings[0]
    assert line_no == 1
    assert "Groq API Key" in desc


def test_scanner_detects_env_key_match(tmp_path: Path):
    """Verify that exact matches for configured .env secrets are flagged."""
    dummy_file = tmp_path / "leaked_file.py"
    dummy_file.write_text("leaked_token = 'my-high-entropy-test-secret-token-123'", encoding="utf-8")

    env_secrets = {"MOCK_API_KEY": "my-high-entropy-test-secret-token-123"}
    findings = scan_file(dummy_file, SECRET_PATTERNS, env_secrets=env_secrets)
    assert len(findings) == 1
    line_no, desc = findings[0]
    assert line_no == 1
    assert "Matches .env variable: MOCK_API_KEY" in desc


def test_scanner_ignores_benign_text(tmp_path: Path):
    """Verify benign code and comments produce no false positives."""
    dummy_file = tmp_path / "clean_code.py"
    dummy_file.write_text(
        "def hello_world():\n"
        "    # Regular comment\n"
        "    return 'AI Career Copilot 2026'\n",
        encoding="utf-8",
    )

    findings = scan_file(dummy_file, SECRET_PATTERNS, env_secrets={})
    assert len(findings) == 0


def test_sanitize_experiment_metadata():
    """Verify that sanitize_experiment_metadata scrubs raw error URLs and enforces P0 fields."""
    raw_meta = {
        "model": "gemini-3.5-flash",
        "prompt_version": "v1.0",
        "attempts": 2,
        "status": "failed",
        "error": "HTTP 503 from https://example.com/api?key=" + "AQ." + "AbFakeKeyForTesting12345",
        "error_type": "HTTPStatusError",
        "api_key": "AQ." + "AbFakeKeyForTesting12345",
        "latency_ms": 150.5,
    }

    sanitized = sanitize_experiment_metadata(raw_meta)

    # 1. Blocked sensitive keys must not be present
    assert "error" not in sanitized
    assert "api_key" not in sanitized

    # 2. Required provider execution fields must be present
    assert sanitized["requested_model"] == "gemini-3.5-flash"
    assert sanitized["answered_model"] == "gemini-3.5-flash"
    assert sanitized["status"] == "failed"
    assert sanitized["attempts"] == 2
    assert sanitized["error type"] == "HTTPStatusError"
    assert sanitized["error_type"] == "HTTPStatusError"

    # 3. Safe context preserved
    assert sanitized["latency_ms"] == 150.5
    assert sanitized["prompt_version"] == "v1.0"


# ==============================================================================
# New focused tests for staged scanning, exclusions, and pruning
# ==============================================================================

def test_scan_staged_detects_secret(tmp_path: Path):
    """Verify scan_staged catches credentials in staged files."""
    _init_git_repo(tmp_path)
    leak_file = tmp_path / "service.py"
    leak_file.write_text("KEY = '" + "AIza" + "SyDummyKeyForTestingPurposes12345'\n", encoding="utf-8")
    subprocess.run(["git", "add", "service.py"], cwd=str(tmp_path), check=True)

    findings = scan_staged(repo_root=tmp_path, env_secrets={})
    assert len(findings) == 1
    git_path, line_no, desc = findings[0]
    assert git_path == "service.py"
    assert line_no == 1
    assert "Google API Key" in desc


def test_scan_staged_reads_index_not_working_tree(tmp_path: Path):
    """Verify scan_staged evaluates the staged index version, not unstaged working tree changes."""
    _init_git_repo(tmp_path)

    # Case A: staged is clean, working tree is poisoned -> scanner should PASS
    file_a = tmp_path / "clean_in_index.py"
    file_a.write_text("SAFE = 'clean content'\n", encoding="utf-8")
    subprocess.run(["git", "add", "clean_in_index.py"], cwd=str(tmp_path), check=True)
    # Poison working tree without git add
    file_a.write_text("KEY = '" + "AIza" + "SyDummyKeyForTestingPurposes12345'\n", encoding="utf-8")

    findings_a = scan_staged(repo_root=tmp_path, env_secrets={})
    assert len(findings_a) == 0, "Scanner read working tree instead of staged index!"

    # Case B: staged has secret, working tree is cleaned -> scanner should CATCH the index secret
    file_b = tmp_path / "dirty_in_index.py"
    file_b.write_text("KEY = '" + "AIza" + "SyDummyKeyForTestingPurposes12345'\n", encoding="utf-8")
    subprocess.run(["git", "add", "dirty_in_index.py"], cwd=str(tmp_path), check=True)
    # Clean working tree without git add
    file_b.write_text("SAFE = 'clean content'\n", encoding="utf-8")

    findings_b = scan_staged(repo_root=tmp_path, env_secrets={})
    assert len(findings_b) == 1
    assert findings_b[0][0] == "dirty_in_index.py"
    assert "Google API Key" in findings_b[0][2]


def test_scan_staged_handles_paths_with_spaces(tmp_path: Path):
    """Verify scan_staged correctly identifies files with spaces in directory and filename."""
    _init_git_repo(tmp_path)
    sub_dir = tmp_path / "my folder with spaces"
    sub_dir.mkdir(parents=True)
    spaced_file = sub_dir / "my secret script.py"
    spaced_file.write_text("TOKEN = '" + "gsk_" + "syntheticGroqApiKeyForTesting1234567890'\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True)

    findings = scan_staged(repo_root=tmp_path, env_secrets={})
    assert len(findings) == 1
    git_path, line_no, desc = findings[0]
    assert git_path == "my folder with spaces/my secret script.py"
    assert line_no == 1
    assert "Groq API Key" in desc


def test_scan_staged_skips_deleted_files(tmp_path: Path):
    """Verify scan_staged ignores files that are staged for deletion."""
    _init_git_repo(tmp_path)
    file_to_delete = tmp_path / "old_secret.py"
    file_to_delete.write_text("KEY = '" + "AIza" + "SyDummyKeyForTestingPurposes12345'\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=str(tmp_path), check=True)

    # Stage file deletion
    subprocess.run(["git", "rm", "old_secret.py"], cwd=str(tmp_path), check=True)

    findings = scan_staged(repo_root=tmp_path, env_secrets={})
    assert len(findings) == 0


def test_scan_staged_handles_renamed_files(tmp_path: Path):
    """Verify scan_staged inspects renamed destination files properly."""
    _init_git_repo(tmp_path)
    orig_file = tmp_path / "orig.py"
    orig_file.write_text("SAFE = 'clean'\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=str(tmp_path), check=True)

    # Rename file
    dest_name = "renamed folder with space/new file.py"
    (tmp_path / "renamed folder with space").mkdir(parents=True)
    subprocess.run(["git", "mv", "orig.py", dest_name], cwd=str(tmp_path), check=True)

    # Put a secret into the renamed destination and stage it
    (tmp_path / dest_name).write_text("KEY = '" + "AIza" + "SyDummyKeyForTestingPurposes12345'\n", encoding="utf-8")
    subprocess.run(["git", "add", dest_name], cwd=str(tmp_path), check=True)

    findings = scan_staged(repo_root=tmp_path, env_secrets={})
    assert len(findings) == 1
    assert findings[0][0] == dest_name
    assert "Google API Key" in findings[0][2]


def test_scan_staged_skips_env_and_excluded_and_binary(tmp_path: Path):
    """Verify scan_staged skips .env files, virtualenvs, and binary files."""
    _init_git_repo(tmp_path)

    # 1. .env file with raw secret (should be skipped)
    env_file = tmp_path / ".env"
    env_file.write_text("SECRET_KEY=" + "AIza" + "SyDummyKeyForTestingPurposes12345\n", encoding="utf-8")

    # 2. Virtualenv path (should be skipped)
    venv_dir = tmp_path / ".venv-p1a-clean" / "lib"
    venv_dir.mkdir(parents=True)
    venv_file = venv_dir / "mod.py"
    venv_file.write_text("KEY = '" + "AIza" + "SyDummyKeyForTestingPurposes12345'\n", encoding="utf-8")

    # 3. Binary file with null bytes (should be skipped)
    bin_file = tmp_path / "blob.dat"
    bin_file.write_bytes(b"\x00\x01\x02" + b"AIza" + b"SyDummyKeyForTestingPurposes12345")

    # 4. Clean file (scanned, no findings)
    clean_file = tmp_path / "clean.py"
    clean_file.write_text("print('hello world')\n", encoding="utf-8")

    subprocess.run(["git", "add", "-f", "."], cwd=str(tmp_path), check=True)

    findings = scan_staged(repo_root=tmp_path, env_secrets={})
    assert len(findings) == 0


def test_scan_staged_fails_safely_when_git_fails(tmp_path: Path):
    """Verify scan_staged raises a clear RuntimeError when executed outside a Git repository."""
    non_git_dir = tmp_path / "not_git"
    non_git_dir.mkdir()

    with pytest.raises(RuntimeError) as exc_info:
        scan_staged(repo_root=non_git_dir, env_secrets={})

    assert "Git command failed" in str(exc_info.value) or "not a git repository" in str(exc_info.value).lower()


def test_scan_repository_prunes_virtualenv_dirs(tmp_path: Path):
    """Verify scan_repository prunes .venv, .venv-*, venv, and cache directories."""
    # Create virtual environments with secrets
    (tmp_path / ".venv" / "lib").mkdir(parents=True)
    (tmp_path / ".venv" / "lib" / "bad.py").write_text("KEY = '" + "AIza" + "SyDummyKeyForTestingPurposes12345'", encoding="utf-8")

    (tmp_path / ".venv-p1a-clean" / "lib").mkdir(parents=True)
    (tmp_path / ".venv-p1a-clean" / "lib" / "bad.py").write_text("KEY = '" + "AIza" + "SyDummyKeyForTestingPurposes12345'", encoding="utf-8")

    (tmp_path / "venv" / "lib").mkdir(parents=True)
    (tmp_path / "venv" / "lib" / "bad.py").write_text("KEY = '" + "AIza" + "SyDummyKeyForTestingPurposes12345'", encoding="utf-8")

    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "node_modules" / "pkg" / "bad.js").write_text("KEY = '" + "AIza" + "SyDummyKeyForTestingPurposes12345'", encoding="utf-8")

    # Create safe code file
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("print('safe code')", encoding="utf-8")

    findings = scan_repository(
        target_paths=[tmp_path],
        repo_root=tmp_path,
        env_secrets={},
    )
    assert len(findings) == 0, f"Expected 0 findings from pruned scan, got: {findings}"


def test_exclusion_helpers():
    """Verify directory and path exclusion helper logic."""
    assert should_exclude_dir(".venv")
    assert should_exclude_dir(".venv-p1a-clean")
    assert should_exclude_dir("venv")
    assert should_exclude_dir("node_modules")
    assert should_exclude_dir(".git")
    assert not should_exclude_dir("app")
    assert not should_exclude_dir("docs")

    assert should_exclude_path(".env")
    assert should_exclude_path(".env.local")
    assert not should_exclude_path(".env.example")
    assert should_exclude_path(".venv-p1a-clean/lib/site-packages/pkg.py")
    assert should_exclude_path("node_modules/lib/index.js")
    assert not should_exclude_path("app/core/config.py")


def test_cli_staged_flag_execution(tmp_path: Path, monkeypatch):
    """Verify check_secrets.py CLI with --staged flag exits 0 on clean and 1 on secret."""
    _init_git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)

    # 1. Clean staged file -> exit 0
    clean_f = tmp_path / "clean.py"
    clean_f.write_text("print('all clean')\n", encoding="utf-8")
    subprocess.run(["git", "add", "clean.py"], cwd=str(tmp_path), check=True)

    exit_code_clean = main(["--staged"])
    assert exit_code_clean == 0

    # 2. Add staged secret file -> exit 1
    secret_f = tmp_path / "secret.py"
    secret_f.write_text("SECRET = '" + "AIza" + "SyDummyKeyForTestingPurposes12345'\n", encoding="utf-8")
    subprocess.run(["git", "add", "secret.py"], cwd=str(tmp_path), check=True)

    exit_code_secret = main(["--staged"])
    assert exit_code_secret == 1
