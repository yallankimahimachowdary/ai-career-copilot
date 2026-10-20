"""
app.core.seniority
------------------
Seniority detection and classification module for job postings and resume titles.

Provides standalone-token matching that blocks adjacent word characters and slashes:
- Entry-level indicators: intern, junior/jr, entry-level/entry, trainee, fresher, 1, I (Level I, Engineer I).
- Senior-level indicators: senior/sr, principal, lead, staff, director, head, chief, vp.
- Blocks accidental matches inside words or across slashes (e.g. Internal, Interior, I/O, Misleading).
- Senior precedence: If both entry and senior indicators match, senior takes precedence.
"""

from enum import Enum
import re
from typing import List, Pattern

# Standalone boundary delimiters: block adjacent word characters (\w) and forward slashes (/)
# Lookbehind: (?<![\w/])
# Lookahead:  (?![\w/])

ENTRY_PATTERNS: List[Pattern[str]] = [
    re.compile(r"(?<![\w/])intern(?![\w/])", re.IGNORECASE),
    re.compile(r"(?<![\w/])(?:junior|jr\.?)(?![\w/])", re.IGNORECASE),
    re.compile(r"(?<![\w/])entry(?:[\s-]level)?(?![\w/])", re.IGNORECASE),
    re.compile(r"(?<![\w/])trainee(?![\w/])", re.IGNORECASE),
    re.compile(r"(?<![\w/])fresher(?![\w/])", re.IGNORECASE),
    re.compile(
        r"(?<![\w/])(?:level\s*[1i]|(?:engineer|analyst|developer)\s*(?:level\s*)?[1i])(?![\w/])",
        re.IGNORECASE,
    ),
]

SENIOR_PATTERNS: List[Pattern[str]] = [
    re.compile(r"(?<![\w/])(?:senior|sr\.?)(?![\w/])", re.IGNORECASE),
    re.compile(r"(?<![\w/])principal(?![\w/])", re.IGNORECASE),
    re.compile(r"(?<![\w/])lead(?![\w/])", re.IGNORECASE),
    re.compile(r"(?<![\w/])director(?![\w/])", re.IGNORECASE),
    re.compile(r"(?<![\w/])staff(?![\w/])", re.IGNORECASE),
    re.compile(r"(?<![\w/])head(?![\w/])", re.IGNORECASE),
    re.compile(r"(?<![\w/])chief(?![\w/])", re.IGNORECASE),
    re.compile(r"(?<![\w/])vp(?![\w/])", re.IGNORECASE),
]


INTERN_PATTERNS: List[Pattern[str]] = [
    re.compile(r"(?<![\w/])intern(?:ship)?(?![\w/])", re.IGNORECASE),
    re.compile(r"(?<![\w/])trainee(?![\w/])", re.IGNORECASE),
]

JUNIOR_PATTERNS: List[Pattern[str]] = [
    re.compile(r"(?<![\w/])(?:junior|jr\.?)(?![\w/])", re.IGNORECASE),
    re.compile(r"(?<![\w/])entry(?:[\s-]level)?(?![\w/])", re.IGNORECASE),
    re.compile(r"(?<![\w/])fresher(?![\w/])", re.IGNORECASE),
    re.compile(
        r"(?<![\w/])(?:level\s*[1i]|(?:engineer|analyst|developer)\s*(?:level\s*)?[1i])(?![\w/])",
        re.IGNORECASE,
    ),
]

LEAD_PATTERNS: List[Pattern[str]] = [
    re.compile(r"(?<![\w/])principal(?![\w/])", re.IGNORECASE),
    re.compile(r"(?<![\w/])lead(?![\w/])", re.IGNORECASE),
    re.compile(r"(?<![\w/])director(?![\w/])", re.IGNORECASE),
    re.compile(r"(?<![\w/])staff(?![\w/])", re.IGNORECASE),
    re.compile(r"(?<![\w/])head(?![\w/])", re.IGNORECASE),
    re.compile(r"(?<![\w/])chief(?![\w/])", re.IGNORECASE),
    re.compile(r"(?<![\w/])vp(?![\w/])", re.IGNORECASE),
]

SENIOR_ONLY_PATTERNS: List[Pattern[str]] = [
    re.compile(r"(?<![\w/])(?:senior|sr\.?)(?![\w/])", re.IGNORECASE),
    re.compile(
        r"(?<![\w/])(?:level\s*(?:[3-5]|iii|iv|v)|(?:engineer|analyst|developer)\s*(?:level\s*)?(?:[3-5]|iii|iv|v))(?![\w/])",
        re.IGNORECASE,
    ),
]


class SeniorityLevel(str, Enum):
    SENIOR = "senior"
    ENTRY = "entry"
    NONE = "none"


class FineSeniority(str, Enum):
    INTERN = "intern"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"


def is_senior(text: str) -> bool:
    """Check if text contains any senior-level indicator token."""
    if not text:
        return False
    return any(p.search(text) for p in SENIOR_PATTERNS)


def is_entry_level(text: str) -> bool:
    """Check if text contains any entry-level indicator token."""
    if not text:
        return False
    return any(p.search(text) for p in ENTRY_PATTERNS)


def classify_seniority(text: str) -> str:
    """Classify text seniority into 'senior', 'entry', or 'none'.

    Standalone-token matching is used to prevent accidental substring matches.
    If both senior and entry-level indicators are present, senior takes precedence.
    """
    if not text:
        return SeniorityLevel.NONE.value

    # Senior indicators take precedence over entry indicators
    if is_senior(text):
        return SeniorityLevel.SENIOR.value
    if is_entry_level(text):
        return SeniorityLevel.ENTRY.value
    return SeniorityLevel.NONE.value


def classify_job_seniority(title: str, description: str = "") -> str:
    """Deterministic seniority classifier for job postings: intern | junior | mid | senior | lead.

    Precedence order:
    1. Lead / Executive / Staff (highest)
    2. Senior / Level III+
    3. Intern / Trainee
    4. Junior / Entry / Level I
    5. Mid (default when no explicit polarity found, or boundary like 'Engineer II')

    Boundary Rule:
    - 'Engineer II' / 'Level 2' / 'Level II' represents a mid-level role with ~2-4 years
      expected experience. It does NOT match entry/junior (Level I) and does NOT match
      senior (Level III+ / Senior). It is strictly classified as 'mid'.
    """
    combined = f"{title or ''} {(description or '')[:500]}"
    t = title or ""

    # Check title first for high-precision role level
    if any(p.search(t) for p in LEAD_PATTERNS):
        return FineSeniority.LEAD.value
    if any(p.search(t) for p in SENIOR_ONLY_PATTERNS):
        return FineSeniority.SENIOR.value
    if any(p.search(t) for p in INTERN_PATTERNS):
        return FineSeniority.INTERN.value
    if any(p.search(t) for p in JUNIOR_PATTERNS):
        return FineSeniority.JUNIOR.value

    # If title didn't match, check description snippet
    if any(p.search(combined) for p in LEAD_PATTERNS):
        return FineSeniority.LEAD.value
    if any(p.search(combined) for p in SENIOR_ONLY_PATTERNS):
        return FineSeniority.SENIOR.value
    if any(p.search(combined) for p in INTERN_PATTERNS):
        return FineSeniority.INTERN.value
    if any(p.search(combined) for p in JUNIOR_PATTERNS):
        return FineSeniority.JUNIOR.value

    return FineSeniority.MID.value


def classify_candidate_seniority(resume_data: dict) -> str:
    """Deterministic seniority classifier for candidate resumes: intern | junior | mid | senior | lead.

    Evaluates:
    1. Explicit 'level' key if provided in synthetic/benchmark schema.
    2. Years of experience derived from experience records or summary.
    3. Seniority tokens in past job titles.

    Heuristic Mapping:
    - 0-1.5 years or explicit 'intern': intern / junior
    - 1.5 - 5 years: mid
    - 5 - 8 years: senior
    - 8+ years or past lead/principal/director/staff title: lead
    """
    if not resume_data:
        return FineSeniority.MID.value

    explicit_level = str(resume_data.get("level") or "").lower()
    if explicit_level in ("intern", "internship"):
        return FineSeniority.INTERN.value
    if explicit_level in ("junior", "entry", "fresher"):
        return FineSeniority.JUNIOR.value
    if explicit_level in ("mid", "mid_level"):
        return FineSeniority.MID.value
    if explicit_level in ("senior", "sr"):
        return FineSeniority.SENIOR.value
    if explicit_level in ("lead", "principal", "staff", "director"):
        return FineSeniority.LEAD.value

    # Evaluate title history
    experiences = resume_data.get("experience", [])
    past_titles = []
    if isinstance(experiences, list):
        for exp in experiences:
            if isinstance(exp, dict) and exp.get("title"):
                past_titles.append(str(exp["title"]))

    has_lead_title = any(any(p.search(t) for p in LEAD_PATTERNS) for t in past_titles)
    has_senior_title = any(any(p.search(t) for p in SENIOR_ONLY_PATTERNS) for t in past_titles)
    has_intern_title = any(any(p.search(t) for p in INTERN_PATTERNS) for t in past_titles)

    # Estimate years
    years = 0.0
    if "years_of_experience" in resume_data:
        try:
            years = float(resume_data["years_of_experience"])
        except (ValueError, TypeError):
            years = 0.0
    elif experiences:
        years = len(experiences) * 1.5  # conservative tenure approximation

    if has_lead_title or years >= 8.0:
        return FineSeniority.LEAD.value
    if has_senior_title or years >= 5.0:
        return FineSeniority.SENIOR.value
    if years >= 2.0:
        return FineSeniority.MID.value
    if has_intern_title or years < 1.0:
        return FineSeniority.INTERN.value
    return FineSeniority.JUNIOR.value


def is_seniority_compatible(candidate_seniority: str, job_seniority: str) -> bool:
    """Check if candidate and job seniority are compatible under the seniority gate.

    Rule:
    - Junior / Intern candidates CANNOT match Senior / Lead roles.
    - Senior / Lead candidates CANNOT match Junior / Intern roles.
    - Mid candidates can match Mid, Junior, or Senior (bridging).
    - Boundary cases (e.g. Mid matching Mid) are always compatible.
    """
    cand = candidate_seniority.lower()
    job = job_seniority.lower()

    if cand in (FineSeniority.INTERN.value, FineSeniority.JUNIOR.value):
        if job in (FineSeniority.SENIOR.value, FineSeniority.LEAD.value):
            return False
    if cand in (FineSeniority.SENIOR.value, FineSeniority.LEAD.value):
        if job in (FineSeniority.INTERN.value, FineSeniority.JUNIOR.value):
            return False

    return True
