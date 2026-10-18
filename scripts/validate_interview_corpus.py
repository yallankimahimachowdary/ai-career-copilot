"""Validate interview_corpus_v1.jsonl against Stage 3 requirements.

Checks:
- File exists and parses as valid JSONL
- Total items >= 150
- >= 15 items per role family (across 5 families)
- >= 20 behavioral / HR / situational questions
- All non-null skills belong to canonical skills taxonomy
- Each question has 3 to 6 key points
- Valid difficulty and question_type enum values
- SHA-256 matches metadata.json
"""

import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.services.coach_service import _SKILL_PATTERNS

CANONICAL_SKILLS = set(_SKILL_PATTERNS.keys())
ALLOWED_FAMILIES = {
    "web_software",
    "data_ai",
    "cloud_devops",
    "core_engineering",
    "business_nontech",
}
ALLOWED_TYPES = {"technical", "behavioral", "situational", "hr", "system_design", "senior"}
ALLOWED_DIFFICULTIES = {"junior", "mid", "senior", "lead"}

CORPUS_PATH = Path("data/interview_corpus/interview_corpus_v1.jsonl")
META_PATH = Path("data/interview_corpus/metadata.json")


def validate():
    if not CORPUS_PATH.exists():
        raise FileNotFoundError(f"{CORPUS_PATH} missing")
    if not META_PATH.exists():
        raise FileNotFoundError(f"{META_PATH} missing")

    with open(CORPUS_PATH, "rb") as f:
        corpus_bytes = f.read()
    actual_sha = hashlib.sha256(corpus_bytes).hexdigest().upper()

    with open(META_PATH, "r", encoding="utf-8") as f:
        meta = json.load(f)

    if meta.get("sha256") != actual_sha:
        raise ValueError(
            f"SHA256 mismatch: meta has {meta.get('sha256')}, file has {actual_sha}"
        )

    lines = corpus_bytes.decode("utf-8").strip().split("\n")
    items = [json.loads(line) for line in lines if line.strip()]

    print(f"Total items parsed: {len(items)}")
    if len(items) < 150:
        raise ValueError(f"Expected >= 150 items, got {len(items)}")

    family_counts = {fam: 0 for fam in ALLOWED_FAMILIES}
    type_counts = {}
    difficulty_counts = {}
    seen_ids = set()

    for idx, item in enumerate(items):
        item_id = item.get("id")
        if not item_id or item_id in seen_ids:
            raise ValueError(f"Duplicate or empty ID: {item_id} at line {idx+1}")
        seen_ids.add(item_id)

        # Family check
        fam = item.get("role_family")
        if fam not in ALLOWED_FAMILIES:
            raise ValueError(f"Invalid family {fam} for {item_id}")
        family_counts[fam] += 1

        # Type check
        qtype = item.get("question_type")
        if qtype not in ALLOWED_TYPES:
            raise ValueError(f"Invalid question_type {qtype} for {item_id}")
        type_counts[qtype] = type_counts.get(qtype, 0) + 1

        # Difficulty check
        diff = item.get("difficulty")
        if diff not in ALLOWED_DIFFICULTIES:
            raise ValueError(f"Invalid difficulty {diff} for {item_id}")
        difficulty_counts[diff] = difficulty_counts.get(diff, 0) + 1

        # Skill check
        tags = item.get("skill_tags", [])
        if not isinstance(tags, list):
            raise ValueError(f"skill_tags must be list for {item_id}")
        for skill in tags:
            if skill not in CANONICAL_SKILLS:
                raise ValueError(f"Non-canonical skill '{skill}' in {item_id}")

        # Key points check (3 to 6)
        key_points = item.get("key_points")
        if not isinstance(key_points, list) or len(key_points) < 3 or len(key_points) > 6:
            raise ValueError(
                f"Item {item_id} must have 3-6 key_points, found {len(key_points) if isinstance(key_points, list) else None}"
            )

        # Text checks
        if not item.get("question") or len(item["question"]) < 15:
            raise ValueError(f"Question text too short for {item_id}")

    for fam, cnt in family_counts.items():
        if cnt < 15:
            raise ValueError(f"Family {fam} has only {cnt} items (< 15)")

    behavioral_count = sum(
        type_counts.get(t, 0) for t in ("behavioral", "hr", "situational")
    )
    if behavioral_count < 20:
        raise ValueError(
            f"Expected >= 20 behavioral/hr/situational questions, got {behavioral_count}"
        )

    print("Family breakdown:")
    for fam, cnt in family_counts.items():
        print(f"  {fam}: {cnt}")

    print("Type breakdown:")
    for t, cnt in type_counts.items():
        print(f"  {t}: {cnt}")

    print("Difficulty breakdown:")
    for d, cnt in difficulty_counts.items():
        print(f"  {d}: {cnt}")

    print("Interview corpus successfully validated! All checks passed.")


if __name__ == "__main__":
    validate()
