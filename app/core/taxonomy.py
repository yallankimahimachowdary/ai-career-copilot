"""
app/core/taxonomy.py
--------------------
Centralized Domain Skill Taxonomy and Text Preprocessing Utilities.

Author: AI Career Copilot Engineering Team (Bala Maan Shree M & Yallanki Mahima Chowdary)

Rationale:
The Kaggle LinkedIn Job Postings dataset contains internal LinkedIn classification
abbreviations (e.g. 'ENG', 'QA', 'IT', 'MGMT') encoded as skill tags. If ingested
naively, these 2-to-4 letter noise tokens introduce substantial false-positive
substring matches and distort TreeSHAP feature-level attribution in the XGBoost
re-ranking pipeline.

This module centralizes:
  1. Categorical exclusion sets (LinkedIn noise codes).
  2. Canonical regex skill boundary patterns.
  3. Reusable normalization and filtering routines for Matcher, Coach, and Market services.
"""

from typing import Dict, List, Optional, Set
import re

# ---------------------------------------------------------------------------
# 1. LinkedIn Noise & Non-Skill Category Codes
# ---------------------------------------------------------------------------
# These codes represent LinkedIn job function codes, NOT technical competencies.
LINKEDIN_CATEGORY_CODES: Set[str] = {
    "ART", "DSGN", "ADVR", "PRDM", "DIST", "EDU", "TRNG", "PRJM",
    "CNSL", "PRCH", "SUPL", "ANLS", "HCPR", "RSCH", "SCI", "GENB",
    "CUST", "STRA", "FIN", "OTHR", "LGL", "ENG", "QA", "BD",
    "IT", "ADM", "PROD", "MRKT", "PR", "WRT", "ACCT", "HR",
    "MNFC", "SALE", "MGMT",
}

# ---------------------------------------------------------------------------
# 2. General Stop Words for Skill and Requirement Parsing
# ---------------------------------------------------------------------------
COMMON_STOP_WORDS: Set[str] = {
    "and", "or", "in", "to", "for", "of", "a", "an", "the",
    "with", "by", "is", "are", "was", "be", "have", "has", "from", "that",
    "this", "it", "as", "we", "our", "your", "their", "will", "can", "may",
    "including", "experience", "skills", "knowledge", "ability", "work",
    "team", "strong", "must", "preferred", "required", "proven",
}

# ---------------------------------------------------------------------------
# 3. Canonical Regex Skill Taxonomy (with Word Boundaries)
# ---------------------------------------------------------------------------
# Strict boundary regexes prevent dangerous sub-token collisions:
# e.g., 'C' matching 'CSS' or 'JavaScript' matching 'Java'.
CANONICAL_SKILL_PATTERNS: Dict[str, str] = {
    "Python": r"\bpython\b",
    "Java": r"\bjava\b(?!\s*script)",
    "JavaScript": r"\b(javascript|js|ecmascript)\b",
    "TypeScript": r"\b(typescript|ts)\b",
    "C/C++": r"\b(c\+\+|c\s*programming|embedded\s*c)\b",
    "C#": r"\b(c#|c\s*sharp|\.net)\b",
    "Go": r"\b(golang|go\s*programming)\b",
    "Rust": r"\brust\b",
    "SQL": r"\b(sql|mysql|postgresql|postgres|sqlite|pl\/sql)\b",
    "HTML/CSS": r"\b(html5?|css3?)\b",
    "React": r"\breact(?:\.js|js|\s*native)?\b",
    "FastAPI": r"\b(fastapi|fast\s*api)\b",
    "Django": r"\bdjango\b",
    "Flask": r"\bflask\b",
    "Spring Boot": r"\b(spring\s*boot|spring\s*framework)\b",
    "Node.js": r"\b(node(?:\.js|js)?)\b",
    "Docker": r"\bdocker\b",
    "Kubernetes": r"\b(kubernetes|k8s)\b",
    "AWS": r"\b(aws|amazon\s*web\s*services)\b",
    "Azure": r"\bazure\b",
    "GCP": r"\b(gcp|google\s*cloud)\b",
    "Git/GitHub": r"\b(git|github|gitlab)\b",
    "Linux": r"\b(linux|unix|ubuntu|centos)\b",
    "GraphQL": r"\bgraphql\b",
    "Kafka": r"\b(kafka|apache\s*kafka)\b",
    "Redis": r"\bredis\b",
    "REST API": r"\b(rest(?:\s*api|\s*framework)?|restful|microservices)\b",
    "Machine Learning": r"\b(machine\s*learning|deep\s*learning|pytorch|tensorflow|keras|scikit.learn|nlp|computer\s*vision)\b",
    "Data Science": r"\b(data\s*science|data\s*analytics?|pandas|numpy|spark)\b",
    "Agile/Scrum": r"\b(agile|scrum|kanban|jira)\b",
    "CI/CD": r"\b(ci\/cd|continuous\s*integration|jenkins|github\s*actions)\b",
    "Communication": r"\b(communication|collaboration|teamwork|interpersonal)\b",
    "Problem Solving": r"\b(problem.solving|analytical|critical\s*thinking)\b",
    "Leadership": r"\b(leadership|mentoring|team\s*lead)\b",
}


# ---------------------------------------------------------------------------
# 4. Utility Functions
# ---------------------------------------------------------------------------

def is_category_code(token: str) -> bool:
    """Return True if the token is an internal LinkedIn non-skill category code."""
    if not token or not isinstance(token, str):
        return False
    return token.strip().upper() in LINKEDIN_CATEGORY_CODES


def filter_category_codes(tokens: List[str]) -> List[str]:
    """Filter out LinkedIn category codes and trivial single-char tokens."""
    cleaned = []
    for t in tokens:
        if not t or not isinstance(t, str):
            continue
        trimmed = t.strip()
        if len(trimmed) > 1 and trimmed.upper() not in LINKEDIN_CATEGORY_CODES:
            cleaned.append(trimmed)
    return cleaned


def extract_canonical_skills(text: str) -> List[str]:
    """
    Extract canonical technical and professional skills from raw text using
    precompiled boundary regex patterns.
    """
    if not text:
        return []

    found_skills = []
    text_lower = text.lower()

    for canonical_name, pattern in CANONICAL_SKILL_PATTERNS.items():
        if re.search(pattern, text_lower, re.IGNORECASE):
            found_skills.append(canonical_name)

    return sorted(list(set(found_skills)))
