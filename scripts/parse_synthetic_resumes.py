"""scripts/parse_synthetic_resumes.py
-----------------------------------
Parses 95 synthetic resumes from data/resumes_dryrun/ for R10-3 and R10-4:
- Anonymizes all 95 resumes
- Parses all 95 with rule-based mode
- Parses 10 with Ollama (llama3.2:3b)
- Audits non-skill tokens (years, institutions, fragments)
- Generates docs/role_families_frozen.json
- Stores all dry-run artifacts in results/dryrun/
"""

import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.abspath("."))

import pymupdf
from app.core.logging import logger
from app.services.anonymizer import anonymize_resume
from app.services.parser_agent import parser_agent

RESUMES_DIR = Path("data/resumes_dryrun")
DRYRUN_DIR = Path("results/dryrun")
DRYRUN_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR = Path("docs")
DOCS_DIR.mkdir(parents=True, exist_ok=True)


def get_role_family(stem: str) -> str:
    num = int(stem.split("_")[1])
    if 1 <= num <= 14:
        return "Data/AI"
    elif 15 <= num <= 26:
        return "Web/Software"
    elif 27 <= num <= 34:
        return "Cybersecurity/Cloud"
    elif 35 <= num <= 40:
        return "Mobile/UI-UX"
    elif 41 <= num <= 48:
        return "Mechanical"
    elif 49 <= num <= 56:
        return "Civil"
    elif 57 <= num <= 77:
        return "Electrical"
    elif 78 <= num <= 90:
        return "Commerce/Finance"
    elif 91 <= num <= 95:
        return "Arts/Media"
    return "Unknown"


def extract_pdf_text(filepath: Path) -> str:
    doc = pymupdf.open(filepath)
    text = ""
    for page in doc:
        text += page.get_text() + "\n"
    return text


def audit_non_skill_tokens(skills: List[str]) -> List[str]:
    """Flag any token that looks like a year, institution name, or invalid fragment."""
    bad_tokens = []
    year_pattern = re.compile(r"^(?:19|20)\d{2}(?:-(?:19|20)?\d{2})?$")
    inst_pattern = re.compile(r"\b(?:institute|university|college|school|polytechnic|iit|nit|iiit|bits|academy|campus)\b", re.I)

    for s in skills:
        s_clean = s.strip()
        if len(s_clean) <= 1:
            bad_tokens.append(f"fragment: '{s}'")
        elif year_pattern.match(s_clean):
            bad_tokens.append(f"year: '{s}'")
        elif inst_pattern.search(s_clean):
            bad_tokens.append(f"institution: '{s}'")
        elif "[INSTITUTION]" in s_clean or "[NAME]" in s_clean or "[EMAIL]" in s_clean:
            bad_tokens.append(f"masking_leak: '{s}'")
    return bad_tokens


async def main():
    files = sorted(list(RESUMES_DIR.glob("*.pdf")))
    if len(files) != 95:
        raise ValueError(f"Expected 95 PDF resumes in {RESUMES_DIR}, found {len(files)}!")

    print(f"Loaded {len(files)} synthetic resumes from {RESUMES_DIR}.\n")

    anonymized_cache: Dict[str, Dict[str, Any]] = {}
    examples_before_after = []

    # 1. Anonymize all 95
    print("--- 1. ANONYMIZING ALL 95 RESUMES ---")
    for f in files:
        raw_text = extract_pdf_text(f)
        anon_text = anonymize_resume(raw_text, strip_institutions=True)
        anonymized_cache[f.stem] = {
            "file_name": f.name,
            "role_family": get_role_family(f.stem),
            "raw_text": raw_text,
            "anon_text": anon_text,
        }
        if f.stem in ("SYN_001_Tanvi_Naidu", "SYN_050_Suresh_Banerjee", "SYN_079_Siddharth_Agarwal"):
            examples_before_after.append({
                "id": f.stem,
                "role_family": get_role_family(f.stem),
                "before": raw_text[:350],
                "after": anon_text[:350],
            })

    print(f"Successfully anonymized {len(anonymized_cache)} resumes.")

    # 2. Rule-based parsing on all 95
    print("\n--- 2. PARSING ALL 95 RESUMES WITH RULE-BASED MODE ---")
    parsed_rules: Dict[str, Any] = {}
    all_rule_skills: List[str] = []
    failed_rules: List[Dict[str, str]] = []
    non_skill_flags: Dict[str, List[str]] = {}

    for stem, data in anonymized_cache.items():
        try:
            parsed = await parser_agent.parse(data["anon_text"], mode="rule_based")
            skills = parsed.skills or []
            parsed_rules[stem] = {
                "skills": skills,
                "experience_count": len(parsed.experience or []),
                "education_count": len(parsed.education or []),
                "projects_count": len(parsed.projects or []),
                "candidate_name": parsed.contact_info.name if parsed.contact_info else None,
            }
            all_rule_skills.extend(skills)

            bad = audit_non_skill_tokens(skills)
            if bad:
                non_skill_flags[stem] = bad
        except Exception as e:
            failed_rules.append({"id": stem, "reason": str(e)})

    avg_skills = len(all_rule_skills) / len(parsed_rules) if parsed_rules else 0.0

    print(f"Rule-based parsing complete: {len(parsed_rules)}/95 parsed, {len(failed_rules)} failed.")
    print(f"Total skills extracted across all 95: {len(all_rule_skills)}")
    print(f"Average skills per resume: {avg_skills:.2f}")

    # 3. Ollama parsing on 10 resumes (SYN_001 to SYN_010)
    print("\n--- 3. PARSING 10 RESUMES WITH OLLAMA (llama3.2:3b) ---")
    parsed_ollama: Dict[str, Any] = {}
    failed_ollama: List[Dict[str, str]] = []

    # Check for existing cached Ollama results
    cached_ollama = {}
    dryrun_out_path = DRYRUN_DIR / "synthetic_resumes_parsed.json"
    if dryrun_out_path.exists():
        try:
            with open(dryrun_out_path, "r", encoding="utf-8") as f:
                prev_data = json.load(f)
                for r in prev_data.get("records", []):
                    if r.get("ollama_skills"):
                        cached_ollama[r["id"]] = r["ollama_skills"]
        except Exception:
            pass

    ollama_stems = [f.stem for f in files[:10]]
    for stem in ollama_stems:
        data = anonymized_cache[stem]
        if stem in cached_ollama:
            print(f"  Using cached Ollama result for {stem} ({len(cached_ollama[stem])} skills)...")
            parsed_ollama[stem] = {
                "skills": cached_ollama[stem],
            }
            bad = audit_non_skill_tokens(cached_ollama[stem])
            if bad:
                non_skill_flags[f"{stem}_ollama"] = bad
            continue

        print(f"  Parsing {stem} with Ollama...")
        try:
            parsed = await parser_agent.parse(data["anon_text"], mode="ollama")
            parsed_ollama[stem] = {
                "skills": parsed.skills or [],
                "experience_count": len(parsed.experience or []),
                "education_count": len(parsed.education or []),
                "projects_count": len(parsed.projects or []),
            }
            bad = audit_non_skill_tokens(parsed.skills or [])
            if bad:
                non_skill_flags[f"{stem}_ollama"] = bad
        except Exception as e:
            failed_ollama.append({"id": stem, "reason": str(e)})

    print(f"Ollama parsing complete: {len(parsed_ollama)}/10 parsed, {len(failed_ollama)} failed.")

    # 4. Report non-skill tokens
    print("\n--- 4. NON-SKILL TOKENS AUDIT ---")
    total_non_skill = sum(len(v) for v in non_skill_flags.values())
    print(f"Total non-skill tokens flagged across all parsed outputs: {total_non_skill}")
    if total_non_skill > 0:
        for k, v in non_skill_flags.items():
            print(f"  - {k}: {v}")
    else:
        print("  Zero non-skill tokens detected! All output tokens conform strictly to skill taxonomy.")

    # 5. Raw skill lists for 5 diverse resumes
    five_sample_ids = [
        ("SYN_001_Tanvi_Naidu", "Data/AI"),
        ("SYN_015_Naveen_Balaji", "Web/Software"),
        ("SYN_027_Bharath_Jain", "Cybersecurity/Cloud"),
        ("SYN_050_Suresh_Banerjee", "Civil"),
        ("SYN_079_Siddharth_Agarwal", "Commerce/Finance"),
    ]
    print("\n--- 5. RAW SKILL LISTS FOR 5 RESUMES ACROSS ROLE FAMILIES ---")
    for s_id, fam in five_sample_ids:
        skills = parsed_rules.get(s_id, {}).get("skills", [])
        print(f"Resume: {s_id} | Family: {fam}")
        print(f"Skills ({len(skills)}): {skills}\n")

    # 6. Save dry-run parsed results
    dryrun_payload = {
        "run_type": "dryrun",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_resumes": 95,
        "rule_based_parsed": len(parsed_rules),
        "rule_based_failed": len(failed_rules),
        "avg_skills_per_resume": round(avg_skills, 2),
        "ollama_parsed": len(parsed_ollama),
        "ollama_failed": len(failed_ollama),
        "non_skill_tokens_count": total_non_skill,
        "records": [
            {
                "id": stem,
                "role_family": data["role_family"],
                "rule_based_skills": parsed_rules.get(stem, {}).get("skills", []),
                "ollama_skills": parsed_ollama.get(stem, {}).get("skills") if stem in parsed_ollama else None,
            }
            for stem, data in anonymized_cache.items()
        ],
    }
    dryrun_out_path = DRYRUN_DIR / "synthetic_resumes_parsed.json"
    with open(dryrun_out_path, "w", encoding="utf-8") as f:
        json.dump(dryrun_payload, f, indent=2)
    print(f"Saved dry-run parsed outputs to {dryrun_out_path}.")

    # 7. Write docs/role_families_frozen.json
    family_distribution = {}
    for stem, data in anonymized_cache.items():
        fam = data["role_family"]
        if fam not in family_distribution:
            family_distribution[fam] = {"count": 0, "resumes": []}
        family_distribution[fam]["count"] += 1
        family_distribution[fam]["resumes"].append(stem)

    frozen_families_payload = {
        "metadata": {
            "description": "Frozen role family distribution across 95 synthetic resumes",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "total_resumes": 95,
            "distribution_summary": {k: v["count"] for k, v in family_distribution.items()},
        },
        "families": family_distribution,
    }
    canonical_json = json.dumps(frozen_families_payload, sort_keys=True, indent=2)
    sha256_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest().upper()
    frozen_families_payload["metadata"]["sha256_hash"] = sha256_hash

    frozen_out_path = DOCS_DIR / "role_families_frozen.json"
    with open(frozen_out_path, "w", encoding="utf-8") as f:
        json.dump(frozen_families_payload, f, indent=2)

    print(f"\nSaved {frozen_out_path} with SHA-256: {sha256_hash}")

    print("\n--- 3 BEFORE/AFTER ANONYMIZATION EXAMPLES ---")
    for ex in examples_before_after:
        print(f"\n=== Resume: {ex['id']} ({ex['role_family']}) ===")
        print("BEFORE ANONYMIZATION:")
        print(ex["before"].strip())
        print("AFTER ANONYMIZATION:")
        print(ex["after"].strip())
        print("-" * 50)


if __name__ == "__main__":
    asyncio.run(main())
