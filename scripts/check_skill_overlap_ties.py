"""Measure skill overlap ties before and after coverage-aware scoring."""

from collections import Counter
import glob
import pypdf

from app.core.taxonomy import SOFT_SKILLS, extract_canonical_skills
from app.services.anonymizer import anonymize_resume
from app.services.parser_agent import parser_agent
from scripts.job_snapshot import load_snapshot


def prepare_resume(glob_pattern: str, candidate_name: str) -> dict:
    fpath = glob.glob(glob_pattern)[0]
    reader = pypdf.PdfReader(fpath)
    raw = "\n".join([p.extract_text() or "" for p in reader.pages])
    anon_text = anonymize_resume(raw, candidate_name=candidate_name)
    parsed = parser_agent._parse_with_rules(anon_text)
    return {
        "candidate_name": candidate_name,
        "raw_text": anon_text,
        "summary": parsed.summary or "",
        "skills": parsed.skills,
    }


def extract_skills_set(resume):
    combined = " ".join([resume.get("summary", ""), resume.get("raw_text", "")] + [str(s) for s in (resume.get("skills") or [])])
    return set(s.lower() for s in extract_canonical_skills(combined))


def extract_job_skills(job):
    title = job.get("title") or ""
    desc = job.get("description") or ""
    raw_skills = job.get("skills") or []
    skills_str = " ".join(str(s) for s in raw_skills) if isinstance(raw_skills, list) else str(raw_skills)
    all_found = set(s.lower() for s in extract_canonical_skills(f"{title}\n{skills_str}\n{desc}"))
    soft = {s for s in all_found if s in SOFT_SKILLS}
    hard = all_found - soft
    return hard, set(), soft


def score_before(cand_skills, job):
    must_hard, nice_hard, soft_found = extract_job_skills(job)
    must_m = len(cand_skills.intersection(must_hard))
    tot = len(must_hard) * 1.0 + len(nice_hard) * 0.5 + len(soft_found) * 0.25
    if tot > 0:
        return round((must_m * 1.0) / tot, 4)
    return 0.0


def score_after(cand_skills, job, min_skills=4):
    must_hard, nice_hard, soft_found = extract_job_skills(job)
    must_m = len(cand_skills.intersection(must_hard))
    tot = len(must_hard) * 1.0 + len(nice_hard) * 0.5 + len(soft_found) * 0.25
    den = max(tot, min_skills * 1.0)
    if den > 0:
        return round((must_m * 1.0) / den, 4)
    return 0.0


def main():
    records, _ = load_snapshot("data/snapshots/test_snap_1.json")
    cand_a = prepare_resume("uploads/resumes/*candidate_a*", "Candidate A")
    cand_b = prepare_resume("uploads/resumes/*candidate_b*", "Candidate B")

    for name, resume in [("Candidate A", cand_a), ("Candidate B", cand_b)]:
        cand_skills = extract_skills_set(resume)
        scores_b = [score_before(cand_skills, j) for j in records]
        scores_a = [score_after(cand_skills, j, min_skills=4) for j in records]

        ties_at_1_b = sum(1 for s in scores_b if s == 1.0)
        ties_at_1_a = sum(1 for s in scores_a if s == 1.0)

        # Count total duplicated scores
        counts_b = Counter(scores_b)
        counts_a = Counter(scores_a)

        print(f"\n===== Skill Overlap Score Distribution for {name} ({len(records)} jobs) =====")
        print(f"Jobs with perfect 1.00 score BEFORE (sparse jobs): {ties_at_1_b}")
        print(f"Jobs with perfect 1.00 score AFTER (coverage-aware): {ties_at_1_a}")
        print(f"Top 5 unique scores BEFORE: {sorted(counts_b.keys(), reverse=True)[:5]}")
        print(f"Top 5 unique scores AFTER:  {sorted(counts_a.keys(), reverse=True)[:5]}")


if __name__ == "__main__":
    main()
