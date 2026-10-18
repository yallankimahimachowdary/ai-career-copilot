"""Tests ensuring no fabricated fallback data or silent defaults exist in production code.

Remediation R6 verification:
- Scans all production source files under `app/**/*.py` (excluding tests, docs, and test fixtures).
- Verifies absence of hardcoded fallback companies ('Databricks', 'Stripe', 'Tech Employer', 'Target Employer').
- Verifies absence of hardcoded fallback job IDs ('matched_job_001', 'matched_job_002').
- Verifies absence of silent default patterns (e.g. `or "Tech Employer"`, `or "Remote"`) in match/search/orchestration paths.
- Provides a strict allowlist for legitimate user-facing documentation or prompt examples with justifications.
"""

from pathlib import Path
import re
from typing import Dict, List, Set, Tuple
import pytest


APP_DIR = Path(__file__).resolve().parent.parent / "app"

# Legitimate allowlist: (normalized_relative_path, line_number_or_keyword, justification)
ALLOWLIST: Dict[str, List[Tuple[str, str]]] = {
    # app/schemas/chat.py contains a user-facing docstring example for how to ask the copilot questions
    "app/schemas/chat.py": [
        (
            "What skills do I need for Stripe backend role?",
            "Justification: User-facing schema field description example showing typical user query.",
        ),
    ],
    # app/services/graph_orchestrator.py contains prompt suggestions generated for the candidate in synthesis
    "app/services/graph_orchestrator.py": [
        (
            "What questions are commonly asked for Stripe or Vercel roles?",
            "Justification: Candidate prompt suggestions generated as actionable follow-ups in synthesis.",
        ),
    ],
    # app/services/router_service.py contains the same prompt suggestions for router synthesis
    "app/services/router_service.py": [
        (
            "What questions are commonly asked for Stripe or Vercel roles?",
            "Justification: Candidate prompt suggestions generated as actionable follow-ups in synthesis.",
        ),
    ],
}

FORBIDDEN_COMPANIES: Set[str] = {
    "Databricks",
    "Stripe",
    "Tech Employer",
    "Target Employer",
}

FORBIDDEN_JOB_IDS: Set[str] = {
    "matched_job_001",
    "matched_job_002",
}

# Regex to catch silent default patterns like `or "Tech Employer"`, `or 'Remote'` in match/search/orchestrator
SILENT_DEFAULT_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r'or\s+["\']Tech Employer["\']', re.IGNORECASE), 'Silent default company: or "Tech Employer"'),
    (re.compile(r'or\s+["\']Target Employer["\']', re.IGNORECASE), 'Silent default company: or "Target Employer"'),
]

# Patterns for silent remote default specifically in match / job object extraction paths
SILENT_REMOTE_IN_MATCH_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r'["\']location["\']\s*:\s*job\.location\s+or\s+["\']Remote["\']', re.IGNORECASE), 'Silent default location: job.location or "Remote"'),
    (re.compile(r'company_name\s+or\s+["\']Tech Employer["\']', re.IGNORECASE), 'Silent default company: company_name or "Tech Employer"'),
]


def _is_allowed(filepath: Path, line_content: str) -> bool:
    rel_path = filepath.as_posix().replace("\\", "/")
    # Extract path relative to project root
    for key in ALLOWLIST:
        if rel_path.endswith(key):
            for allowed_snippet, _ in ALLOWLIST[key]:
                if allowed_snippet in line_content:
                    return True
    return False


def test_no_hardcoded_companies_or_jobs():
    """Scans all python files in app/ to verify no fabricated company names or job IDs exist."""
    violations: List[str] = []

    py_files = list(APP_DIR.rglob("*.py"))
    assert len(py_files) > 0, "Expected to find python files in app/"

    for py_file in py_files:
        with open(py_file, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                if _is_allowed(py_file, line):
                    continue

                for comp in FORBIDDEN_COMPANIES:
                    if comp in line:
                        rel = py_file.relative_to(APP_DIR.parent).as_posix()
                        violations.append(f"{rel}:{line_no} contains forbidden company '{comp}': {line.strip()}")

                for jid in FORBIDDEN_JOB_IDS:
                    if jid in line:
                        rel = py_file.relative_to(APP_DIR.parent).as_posix()
                        violations.append(f"{rel}:{line_no} contains forbidden job_id '{jid}': {line.strip()}")

    assert not violations, "Found fabricated fallback data in production code:\n" + "\n".join(violations)


def test_no_silent_defaults_in_orchestrators():
    """Scans all python files in app/ to verify no silent defaults exist in match/orchestration code."""
    violations: List[str] = []

    py_files = list(APP_DIR.rglob("*.py"))
    for py_file in py_files:
        rel = py_file.relative_to(APP_DIR.parent).as_posix()
        with open(py_file, "r", encoding="utf-8") as f:
            content = f.read()

        for pattern, desc in SILENT_DEFAULT_PATTERNS:
            matches = list(pattern.finditer(content))
            for m in matches:
                violations.append(f"{rel} matches {desc}: '{m.group(0)}'")

        for pattern, desc in SILENT_REMOTE_IN_MATCH_PATTERNS:
            matches = list(pattern.finditer(content))
            for m in matches:
                violations.append(f"{rel} matches {desc}: '{m.group(0)}'")

    assert not violations, "Found silent defaults in production code:\n" + "\n".join(violations)
