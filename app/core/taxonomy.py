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
# 2b. Canonical Soft Skills Set
# ---------------------------------------------------------------------------
# Shared across Matcher, Coach, and Parser to guarantee consistency.
# Soft skills are treated as nice-to-have/growth gaps and never as hard technical blockers.
SOFT_SKILLS: Set[str] = {
    "communication",
    "leadership",
    "problem solving",
    "teamwork",
    "collaboration",
    "interpersonal",
    "time management",
    "critical thinking",
    "agile/scrum",
    "mentoring",
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
    "C": r"(?:\b(?:c\s*programming|ansi\s*c)\b|(?<![a-zA-Z0-9_#+])c(?![a-zA-Z0-9_#+]))",
    "C/C++": r"\b(c\+\+|c\s*programming|embedded\s*c)\b",
    "C#": r"\b(c#|c\s*sharp|\.net)\b",
    "Go": r"\b(golang|go\s*programming)\b",
    "Rust": r"\brust\b",
    "SQL": r"\b(sql|mysql|postgresql|postgres|sqlite|pl\/sql)\b",
    "MySQL": r"\bmysql\b",
    "DBMS": r"\b(dbms|database\s*management(?:\s*systems?)?)\b",
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
    "Software Engineering": r"\bsoftware\s*engineering\b",
    "Web Technologies": r"\bweb\s*technologies\b",
    "Figma": r"\bfigma\b",
    "Canva": r"\bcanva\b",
    "Blender": r"\bblender(?:\s*\(basics?\))?\b",
    "VS Code": r"\b(vs\s*code|visual\s*studio\s*code)\b",
    "Eclipse IDE": r"\beclipse(?:\s*ide)?\b",
    "Agile/Scrum": r"\b(agile|scrum|kanban|jira)\b",
    "CI/CD": r"\b(ci\/cd|continuous\s*integration|jenkins|github\s*actions)\b",
    "Communication": r"\b(communication|interpersonal)\b",
    "Team Collaboration": r"\b(team\s*collaboration|teamwork|collaborative\s*work)\b",
    "Problem Solving": r"\b(problem.solving|analytical|critical\s*thinking)\b",
    "Leadership": r"\b(leadership|mentoring|team\s*lead)\b",
    "Time Management": r"\btime\s*management\b",

    # --- Biotechnology & Life Sciences ---
    "PCR": r"\b(pcr|polymerase\s*chain\s*reaction|qpcr|rt-pcr)\b",
    "Gel Electrophoresis": r"\b(gel\s*electrophoresis|agarose\s*gel|sds-page)\b",
    "Cell Culture": r"\b(cell\s*culture|tissue\s*culture|cell\s*lines?)\b",
    "Molecular Biology": r"\bmolecular\s*biology\b",
    "Microbiology": r"\bmicrobiology\b",
    "CRISPR / Gene Editing": r"\b(crispr(?:-cas9)?|gene\s*editing|genome\s*editing)\b",
    "Bioinformatics": r"\b(bioinformatics|computational\s*biology|blast|biopython)\b",
    "Next-Generation Sequencing (NGS)": r"\b(next[- ]generation\s*sequencing|ngs|rna[- ]seq|genomics?|proteomics?)\b",
    "ELISA": r"\belisa\b",
    "Fermentation / Bioprocessing": r"\b(fermentation|bioprocess(?:ing)?|bioreactor)\b",
    "Chromatography": r"\b(chromatography|hplc|fplc|gas\s*chromatography)\b",
    "Flow Cytometry": r"\b(flow\s*cytometry|facs)\b",
    "Agricultural Practices": r"\b(agricultural\s*practices?|biofertilizer|agritech|soil\s*fertility)\b",

    # --- Pharmaceutical & Clinical Research ---
    "GMP / GLP": r"\b(gmp|good\s*manufacturing\s*practice|glp|gcp)\b",
    "Clinical Trials": r"\b(clinical\s*trials?|clinical\s*research|clinical\s*data)\b",
    "Formulation": r"\b(drug\s*formulation|formulation|encapsulation)\b",
    "Drug Discovery": r"\b(drug\s*discovery|medicinal\s*chemistry|pharmacology)\b",
    "HPLC": r"\b(hplc|high[- ]performance\s*liquid\s*chromatography)\b",
    "Pharmacovigilance": r"\b(pharmacovigilance|regulatory\s*affairs)\b",

    # --- Core Engineering & CAD/Simulation ---
    "MATLAB": r"\bmatlab\b",
    "Simulink": r"\bsimulink\b",
    "R Programming": r"\b(r\s*programming|\br\s*language|\br\s*stats)\b",
    "AutoCAD": r"\b(autocad|cad\s*drafting)\b",
    "SolidWorks": r"\bsolidworks\b",
    "ANSYS / FEA": r"\b(ansys|finite\s*element|fea|cfd)\b",
    "CATIA": r"\bcatia\b",
    "PLC / SCADA": r"\b(plc|scada|industrial\s*automation)\b",
    "Embedded Systems": r"\b(embedded\s*systems?|microcontroller|arduino|raspberry\s*pi)\b",
    "VLSI": r"\b(vlsi|verilog|vhdl|fpga)\b",
    "Revit / BIM": r"\b(revit|bim|civil\s*3d)\b",
    "CNC Machining": r"\b(cnc|machining|cam)\b",
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


# ---------------------------------------------------------------------------
# 5. Natural / Spoken Languages & Non-Skill Token Classification
# ---------------------------------------------------------------------------

SPOKEN_LANGUAGES: Set[str] = {
    "english", "tamil", "telugu", "hindi", "spanish", "french", "german",
    "mandarin", "japanese", "korean", "arabic", "bengali", "marathi",
    "kannada", "malayalam", "gujarati", "punjabi", "urdu", "russian",
}

IGNORED_HEADING_PATTERNS: List[str] = [
    r"^(?:summary|projects?|education|academic|skills?|technical skills?|certificates?|certifications?|languages?)$",
    r"^(?:professional languages?|tools[\s/]+frameworks?|databases?|professional skills?|computer skills?)$",
]

def extract_spoken_languages(text: str) -> List[str]:
    """Extract natural / spoken languages from text."""
    if not text:
        return []
    found = []
    text_lower = text.lower()
    for lang in SPOKEN_LANGUAGES:
        if re.search(r"\b" + re.escape(lang) + r"\b", text_lower):
            found.append(lang.capitalize())
    return sorted(list(set(found)))


def is_ignored_token(token: str) -> bool:
    """
    Identify non-skill tokens such as years, institutions, degrees, course listings,
    section headings, and descriptive bullet fragments.
    """
    if not token or not isinstance(token, str):
        return True
    t = token.strip()
    if not t or len(t) < 2:
        return True
    t_lower = t.lower()

    # Years or year ranges: '2025', '2024 - 2028', '2022'
    if re.match(r"^\d{4}(?:\s*[-–]\s*\d{4})?$", t):
        return True

    # Section headings
    for p in IGNORED_HEADING_PATTERNS:
        if re.match(p, t_lower):
            return True

    # Institutions
    if any(inst in t_lower for inst in ["university", "college", "school", "institute", "vel tech"]):
        return True

    # Degrees & course headers
    if any(t_lower.startswith(prefix) for prefix in [
        "bachelor", "master", "b.tech", "m.tech", "b.s", "m.s", "ph.d",
        "hsc", "sslc", "cgpa", "percentage", "relevant courses"
    ]):
        return True

    # Common resume bullet fragments or descriptive sentences (length > 30 with verbs/prepositions)
    if len(t.split()) >= 4 and any(w in t_lower for w in ["developed", "created", "designed", "explored", "techniques", "project", "composition"]):
        return True

    # Generic labels
    if t_lower in {"professional", "basics", "computer skills", "relevant courses"}:
        return True

    return False

