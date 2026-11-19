"""
scripts/college_report/diagnose_table_2.py
-----------------------------------------
Diagnostic script for Table 2 parsing discrepancies.
Performs:
1. Inspects SYN_DEMO_013 and SYN_DEMO_020 (expected skills, extracted skills, raw text).
2. For all 20 resumes, classifies each mismatched skill into:
   - Soft skill extracted (Communication, Team Collaboration, Problem Solving, Leadership, Time Management, etc.)
   - Alias / naming mismatch (e.g. Scikit-Learn vs Scikit-learn, React vs React.js)
   - Skill not in Taxonomy v2.1 (skills generated in ground truth that do not exist in CANONICAL_SKILL_PATTERNS)
   - True parser miss (skill was in resume text and in taxonomy, but parser failed to extract)
3. Computes counts per category per role family.
"""

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.services.parser_agent import parser_agent
from app.core.taxonomy import CANONICAL_SKILL_PATTERNS, SOFT_SKILLS

DEMO_DIR = PROJECT_ROOT / "data" / "college_demo"
GT_FILE = DEMO_DIR / "ground_truth.json"

with open(GT_FILE, "r", encoding="utf-8") as f:
    gt_data = json.load(f)

candidates = gt_data["candidates"]

# -----------------------------------------------------------------------------
# Part A: SYN_DEMO_013 and SYN_DEMO_020 Inspection
# -----------------------------------------------------------------------------
print("=================================================================")
print("   ITEM 1b (a): DIAGNOSIS OF SYN_DEMO_013 & SYN_DEMO_020       ")
print("=================================================================")

target_ids = ["SYN_DEMO_013", "SYN_DEMO_020"]
for cand in candidates:
    if cand["candidate_id"] in target_ids:
        cid = cand["candidate_id"]
        cname = cand["candidate_name"]
        cfam = cand["role_family"]
        txt_path = Path(cand["file_path"])
        raw_text = txt_path.read_text(encoding="utf-8")
        parsed = parser_agent._parse_with_rules(raw_text)
        extracted = parsed.skills or []
        expected = cand["expected_skills"]

        print(f"\n--- Candidate: {cid} ({cname}) | Family: {cfam} ---")
        print(f"Resume File Path: {txt_path}")
        print(f"Expected Skills ({len(expected)}): {expected}")
        print(f"Extracted Skills ({len(extracted)}): {extracted}")
        print("\n--- Resume Text Seen by Parser ---")
        print(raw_text.strip())
        print("-----------------------------------------------------------------")


# -----------------------------------------------------------------------------
# Part B: Classification of Mismatched Skills across all 20 resumes
# -----------------------------------------------------------------------------
print("\n=================================================================")
print("   ITEM 1b (b): MISMATCH CLASSIFICATION ACROSS ALL 20 RESUMES   ")
print("=================================================================")

# Map of lower-cased canonical taxonomy keys
canonical_lower_map = {k.lower(): k for k in CANONICAL_SKILL_PATTERNS.keys()}

# Taxonomy alias / alternate spellings
alias_map = {
    "react.js": "React",
    "reactjs": "React",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "vue.js": "Vue.js",
    "vuejs": "Vue.js",
    "scikit-learn": "Scikit-Learn",
    "sklearn": "Scikit-Learn",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "aws": "AWS",
    "gcp": "Google Cloud",
    "k8s": "Kubernetes",
    "golang": "Go",
    "ui/ux": "UI/UX Design",
    "ui/ux design": "UI/UX Design",
    "rest apis": "REST APIs",
    "rest api": "REST APIs",
    "ci/cd": "CI/CD",
    "generative ai": "Generative AI",
    "genai": "Generative AI",
    "llms": "LLMs",
    "llm": "LLMs",
}

# Add soft skills lower
soft_skills_lower = {s.lower() for s in SOFT_SKILLS}
soft_skills_lower.update({"communication", "team collaboration", "problem solving", "leadership", "time management", "teamwork", "collaboration", "interpersonal"})

categories_by_family = {}

for cand in candidates:
    cid = cand["candidate_id"]
    cfam = cand["role_family"]
    if cfam not in categories_by_family:
        categories_by_family[cfam] = {
            "soft_skill_extracted": 0,
            "alias_or_naming_mismatch": 0,
            "skill_not_in_taxonomy": 0,
            "true_parser_miss": 0,
            "details": []
        }

    raw_text = Path(cand["file_path"]).read_text(encoding="utf-8")
    parsed = parser_agent._parse_with_rules(raw_text)
    extracted = set(parsed.skills or [])
    expected = set(cand["expected_skills"])

    ext_lower = {s.lower(): s for s in extracted}
    exp_lower = {s.lower(): s for s in expected}

    # Analyze False Positives (in extracted, but not in expected)
    for s_low, s_orig in ext_lower.items():
        if s_low not in exp_lower:
            # Check if it's a soft skill
            if s_low in soft_skills_lower:
                categories_by_family[cfam]["soft_skill_extracted"] += 1
                categories_by_family[cfam]["details"].append((cid, "soft_skill_extracted", s_orig))
            # Check if it's an alias of an expected skill
            elif alias_map.get(s_low, s_low).lower() in exp_lower or any(alias_map.get(exp_l, exp_l).lower() == s_low for exp_l in exp_lower):
                categories_by_family[cfam]["alias_or_naming_mismatch"] += 1
                categories_by_family[cfam]["details"].append((cid, "alias_or_naming_mismatch", s_orig))
            else:
                # Extracted by taxonomy regex from text (valid keyword in resume, but not in synthetic expected list)
                categories_by_family[cfam]["details"].append((cid, "extra_canonical_extracted", s_orig))

    # Analyze False Negatives (in expected, but not in extracted)
    for s_low, s_orig in exp_lower.items():
        if s_low not in ext_lower:
            # Check if it's an alias that was actually extracted under another name
            norm_exp = alias_map.get(s_low, s_low).lower()
            if norm_exp in ext_lower or any(alias_map.get(ext_l, ext_l).lower() == norm_exp for ext_l in ext_lower):
                categories_by_family[cfam]["alias_or_naming_mismatch"] += 1
                categories_by_family[cfam]["details"].append((cid, "alias_or_naming_mismatch", s_orig))
            # Check if skill exists in canonical taxonomy
            elif norm_exp not in canonical_lower_map and s_low not in canonical_lower_map:
                categories_by_family[cfam]["skill_not_in_taxonomy"] += 1
                categories_by_family[cfam]["details"].append((cid, "skill_not_in_taxonomy", s_orig))
            else:
                # Skill IS in taxonomy and was in expected list, did parser miss it?
                # Check if it was actually in raw_text
                if s_low in raw_text.lower():
                    categories_by_family[cfam]["true_parser_miss"] += 1
                    categories_by_family[cfam]["details"].append((cid, "true_parser_miss", s_orig))
                else:
                    categories_by_family[cfam]["details"].append((cid, "expected_not_in_text", s_orig))

print(f"{'Role Family':<22} | {'Soft Skills':<12} | {'Alias Mismatch':<15} | {'Not in Taxonomy':<16} | {'True Miss':<10}")
print("-" * 85)
for fam, counts in sorted(categories_by_family.items()):
    print(f"{fam:<22} | {counts['soft_skill_extracted']:<12} | {counts['alias_or_naming_mismatch']:<15} | {counts['skill_not_in_taxonomy']:<16} | {counts['true_parser_miss']:<10}")

print("\n--- Detailed Breakdown of Mismatches ---")
for fam, counts in sorted(categories_by_family.items()):
    print(f"\n[{fam}]")
    for item in counts["details"]:
        print(f"  - {item[0]}: {item[1]} -> '{item[2]}'")
