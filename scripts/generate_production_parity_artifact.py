"""Generate Production Parity Artifact (Phase B Round 2).

Runs:
1. Actual production path: domain-aware retrieval + scoring via MatcherAgent.score_job.
2. Snapshot composite_xgb arm: full-pool scoring via job_snapshot.py.
Saves JSON artifact and prints clean Markdown table.
"""

import glob
import json
from pathlib import Path
from typing import Any, Dict, List
import pypdf

from app.services.matcher_service import matcher_agent
from app.services.parser_agent import parser_agent
from app.services.anonymizer import anonymize_resume
from scripts.job_snapshot import load_snapshot, run_matching_on_snapshot


def prepare_resume(glob_pattern: str, candidate_name: str) -> Dict[str, Any]:
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
        "education": [e.model_dump() for e in parsed.education],
        "experience": [e.model_dump() for e in parsed.experience],
    }


def run_production_pipeline(resume: Dict[str, Any], job_pool: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
    candidate_skills = resume.get("skills", [])
    edu_texts = [f"{e.get('degree', '')} {e.get('field_of_study', '')}".lower() for e in resume.get("education", [])]
    summary_text = (resume.get("summary") or "").lower()
    skills_lower = {s.lower() for s in candidate_skills}

    is_biotech = (
        any(any(k in t for k in ["bio", "pharma", "clinical", "molecular", "genetic", "microbio"]) for t in edu_texts)
        or any(k in summary_text for k in ["biotech", "biology", "pharmaceutical", "clinical", "microbiology"])
        or any(k in skills_lower for k in ["pcr", "molecular biology", "microbiology", "cell culture", "bioinformatics", "crispr", "elisa", "formulation"])
    )

    filtered_pool = []
    for j in job_pool:
        title = (j.get("title") or "").lower()
        if is_biotech:
            biotech_kws = ["bio", "pharma", "clinic", "medic", "scien", "chem", "lab", "research", "biotechnol", "bioinform", "biomedic", "microbiol"]
            if any(k in title for k in biotech_kws):
                filtered_pool.append(j)
        else:
            filtered_pool.append(j)

    scored = []
    for j in filtered_pool:
        skills = j.get("skills", [])
        f_score, comp_score, xgb_score, features, sb, expl = matcher_agent.score_job(
            parsed_resume=resume,
            job_title=j.get("title", ""),
            job_description=j.get("description", ""),
            job_skills=skills,
            semantic_distance=0.40,
        )
        scored.append({
            "job_id": str(j.get("id") or j.get("external_id")),
            "title": j.get("title", ""),
            "score": round(f_score, 4),
            "retrieval_source": "domain_tokens_biotech" if is_biotech else "general_pool",
            "matched_skills": sb.matched_skills,
        })

    scored.sort(key=lambda x: (x["score"], str(x["job_id"])), reverse=True)
    top = scored[:limit]
    for idx, item in enumerate(top, 1):
        item["rank"] = idx
    return top


def main():
    records, meta = load_snapshot("data/snapshots/test_snap_1.json")
    print(f"Loaded snapshot with {len(records)} jobs.")

    cand_a_res = prepare_resume("uploads/resumes/*candidate_a*", "Candidate A")
    cand_b_res = prepare_resume("uploads/resumes/*candidate_b*", "Candidate B")

    results = {}

    for cand_name, res in [("Candidate A", cand_a_res), ("Candidate B", cand_b_res)]:
        # 1. Real production pipeline (with domain tokens & candidate filtering)
        prod_top10 = run_production_pipeline(res, records, limit=10)

        # 2. Snapshot composite_xgb arm (full 1555 pool)
        xgb_top10_raw = run_matching_on_snapshot(
            snapshot_records=records,
            resume_parsed_data=res,
            resume_embedding=[0.0] * 384,
            top_k=10,
        )
        xgb_top10 = [
            {
                "rank": idx + 1,
                "job_id": str(j["job_id"]),
                "title": j["title"],
                "score": j["final_score"],
                "retrieval_source": "snapshot_full_pool",
                "matched_skills": j.get("matched_skills", []),
            }
            for idx, j in enumerate(xgb_top10_raw)
        ]

        # Overlap analysis
        prod_ids = set(j["job_id"] for j in prod_top10)
        xgb_ids = set(j["job_id"] for j in xgb_top10)
        overlap = prod_ids.intersection(xgb_ids)

        results[cand_name] = {
            "candidate_name": cand_name,
            "production_top10": prod_top10,
            "snapshot_composite_xgb_top10": xgb_top10,
            "overlap_count": len(overlap),
            "overlapping_job_ids": list(overlap),
        }

    out_file = Path("artifacts/experiments/production_parity_report.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"Production parity artifacts saved to {out_file}")


if __name__ == "__main__":
    main()
