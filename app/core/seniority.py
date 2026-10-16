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


class SeniorityLevel(str, Enum):
    SENIOR = "senior"
    ENTRY = "entry"
    NONE = "none"


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
