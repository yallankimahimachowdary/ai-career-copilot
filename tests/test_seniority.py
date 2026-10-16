"""
tests/test_seniority.py
-----------------------
Unit tests for seniority detection and classification module (P1B).

Covers:
1. 20 required benchmark test cases
2. Precedence rules (senior takes precedence over entry)
3. Standalone-token boundary checks (blocking adjacent word characters and slashes)
4. Level I / Engineer I vs. Level II / Engineer II
5. Pinned known limitations (Staff Accountant, Head Office Clerk)
"""

import pytest
from app.core.seniority import (
    classify_seniority,
    is_entry_level,
    is_senior,
    SeniorityLevel,
)


# ==============================================================================
# 1. 20 Required Benchmark Test Cases (Task 2)
# ==============================================================================

BENCHMARK_CASES = [
    ("Intern Data Analyst", "entry"),
    ("Internship Coordinator", "none"),
    ("Internal Auditor", "none"),
    ("Software Engineer", "none"),
    ("Junior Developer", "entry"),
    ("Jr. Developer", "entry"),
    ("Entry-Level Engineer", "entry"),
    ("Engineer I", "entry"),
    ("Analyst 1", "entry"),
    ("Engineer II", "none"),
    ("Sr. Engineer", "senior"),
    ("Sr Developer", "senior"),
    ("Senior Engineer", "senior"),
    ("Principal Engineer", "senior"),
    ("Misleading Analyst", "none"),
    ("Associate Director", "senior"),
    ("Associate Engineer", "none"),
    ("I/O Engineer", "none"),
    ("Interior Designer", "none"),
    ("Staff Accountant", "senior"),
]


@pytest.mark.parametrize("title,expected", BENCHMARK_CASES)
def test_seniority_benchmark_cases(title: str, expected: str):
    """Test the exact 20 benchmark examples specified in P1B requirements."""
    result = classify_seniority(title)
    assert result == expected, f"Expected {title!r} to be classified as {expected!r}, but got {result!r}"


# ==============================================================================
# 2. Pinned Known Limitations (Task 3)
# ==============================================================================

def test_pinned_limitation_staff_accountant():
    """Known Limitation: 'Staff Accountant' is classified as 'senior' due to tech-oriented

    seniority heuristic ('staff'), despite being an entry/intermediate role in accounting.
    This test pins the known limitation as required by P1B specifications; it is NOT correct
    domain behavior for accounting.
    """
    assert classify_seniority("Staff Accountant") == "senior"
    assert is_senior("Staff Accountant") is True


def test_pinned_limitation_head_office_clerk():
    """Known Limitation: 'Head Office Clerk' is classified as 'senior' due to leadership

    token heuristic ('head'), despite referring to a corporate office location rather
    than a leadership rank.
    This test pins the known limitation as required by P1B specifications; it is NOT correct
    domain behavior for clerical roles.
    """
    assert classify_seniority("Head Office Clerk") == "senior"
    assert is_senior("Head Office Clerk") is True


# ==============================================================================
# 3. Precedence & Boundary Rules
# ==============================================================================

def test_senior_precedence_over_entry():
    """If both senior and entry-level indicators are present, senior must take precedence."""
    assert classify_seniority("Senior Intern") == "senior"
    assert classify_seniority("Junior Director") == "senior"
    assert classify_seniority("Lead Trainee Engineer") == "senior"
    assert classify_seniority("Associate Director") == "senior"


def test_level_i_vs_level_ii():
    """Level I / Engineer I indicate entry level; Level II / Engineer II indicate none."""
    assert classify_seniority("Level I") == "entry"
    assert classify_seniority("Level I Engineer") == "entry"
    assert classify_seniority("Engineer I") == "entry"
    assert classify_seniority("Analyst 1") == "entry"

    assert classify_seniority("Level II") == "none"
    assert classify_seniority("Level II Engineer") == "none"
    assert classify_seniority("Engineer II") == "none"
    assert classify_seniority("Level III") == "none"
    assert classify_seniority("Engineer III") == "none"


def test_unrelated_numeral_i_not_entry():
    """Prevent unrelated titles containing a standalone Roman numeral I from being automatically classified as entry-level."""
    assert classify_seniority("Product Manager I") == "none"
    assert not is_entry_level("Product Manager I")
    assert classify_seniority("Project Manager I") == "none"
    assert not is_entry_level("Project Manager I")
    assert classify_seniority("Sales Representative I") == "none"


def test_standalone_token_blocking_adjacent_characters():
    """Avoid accidental matches inside words (Internal, Interior, Misleading, I/O)."""
    # 'Internal' must not match 'intern' or 'I'
    assert classify_seniority("Internal Auditor") == "none"
    assert not is_entry_level("Internal Auditor")

    # 'Interior' must not match 'I'
    assert classify_seniority("Interior Designer") == "none"
    assert not is_entry_level("Interior Designer")

    # 'I/O' must not match 'I' (slashes must be blocked as delimiters)
    assert classify_seniority("I/O Engineer") == "none"
    assert not is_entry_level("I/O Engineer")

    # 'Misleading' must not match 'lead'
    assert classify_seniority("Misleading Analyst") == "none"
    assert not is_senior("Misleading Analyst")


def test_principal_indicates_seniority():
    """Principal indicates seniority."""
    assert classify_seniority("Principal Engineer") == "senior"
    assert classify_seniority("Principal Scientist") == "senior"
    assert is_senior("Principal Architect") is True
