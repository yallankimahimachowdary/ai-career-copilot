"""Verify parity between production Matcher scoring and composite_xgb arm on frozen snapshot."""

import glob
from pathlib import Path
import pypdf

from app.services.anonymizer import anonymize_resume
from app.services.parser_agent import parser_agent
from app.services.matcher_service import matcher_agent
from scripts.job_snapshot import load_snapshot, run_matching_on_snapshot
from app.ranking.hybrid import CompositeXGBRanker


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
        "experience": [e.model_dump() for e in parsed.experience],
        "education": [e.model_dump() for e in parsed.education],
    }


def run_production_matcher_on_snapshot(snapshot_records, resume_data, top_k=10):
    """Production Matcher algorithm running directly across snapshot job pool."""
    from app.services.embedding_service import get_sentence_transformer
    import numpy as np

    cand_emb = resume_data.get("embedding")
    if not cand_emb:
        text = resume_data.get("summary") or " ".join(resume_data.get("skills", []))
        st = get_sentence_transformer()
        cand_emb = st.encode(text, convert_to_numpy=True, normalize_embeddings=True).tolist()

    cand_vec = np.array(cand_emb, dtype=np.float32)
    norm_c = np.linalg.norm(cand_vec)
    if norm_c > 0:
        cand_vec = cand_vec / norm_c

    results = []
    for rec in snapshot_records:
        jid = str(rec.get("id") or rec.get("external_id") or "")
        title = rec.get("title") or ""
        desc = rec.get("description") or ""
        skills = rec.get("skills") or []
        if isinstance(skills, str):
            import json
            try:
                skills = json.loads(skills)
            except Exception:
                skills = []

        if "embedding" in rec and rec["embedding"]:
            job_emb = np.array(rec["embedding"], dtype=np.float32)
            norm_j = np.linalg.norm(job_emb)
            if norm_j > 0:
                job_emb = job_emb / norm_j
            cos_sim = float(np.dot(cand_vec, job_emb))
            cos_dist = max(0.0, 1.0 - cos_sim)
        else:
            cand_skills = resume_data.get("skills", [])
            from app.services.matcher_service import FeatureExtractor
            shared = sum(1 for s in cand_skills if FeatureExtractor.is_skill_match(s, title) or s.lower() in desc.lower())
            cos_sim = min(0.95, 0.40 + 0.05 * shared)
            cos_dist = 1.0 - cos_sim

        final_score, comp_score, xgb_score, feats, sk_breakdown, _ = matcher_agent.score_job(
            parsed_resume=resume_data,
            job_title=title,
            job_description=desc,
            job_skills=skills,
            semantic_distance=cos_dist,
        )

        results.append({
            "job_id": jid,
            "title": title,
            "company": rec.get("company"),
            "final_score": round(final_score, 4),
            "composite_score": round(comp_score, 4),
            "xgboost_score": round(xgb_score, 4),
        })

    results.sort(key=lambda x: (x["final_score"], x["composite_score"], str(x["job_id"])), reverse=True)
    return results[:top_k]


def main():
    records, meta = load_snapshot("data/snapshots/test_snap_1.json")
    print(f"Loaded snapshot: {len(records)} jobs")

    cand_a = prepare_resume("uploads/resumes/*candidate_a*", "Candidate A")
    cand_b = prepare_resume("uploads/resumes/*candidate_b*", "Candidate B")

    composite_xgb_arm = CompositeXGBRanker()

    for name, resume in [("Candidate A", cand_a), ("Candidate B", cand_b)]:
        print(f"\n==================== Parity Evaluation for {name} ====================")
        prod_top10 = run_production_matcher_on_snapshot(records, resume, top_k=10)
        arm_res = composite_xgb_arm.rank(resume, records, k=10)
        arm_top10_ids = arm_res.ranked_job_ids
        arm_scores = arm_res.scores

        prod_ids = [p["job_id"] for p in prod_top10]
        prod_scores = [p["final_score"] for p in prod_top10]

        matches = (prod_ids == arm_top10_ids)
        print(f"Parity Match: {'PERFECT 100% MATCH' if matches else 'MISMATCH'}")

        print(f"\n{'Rank':<5} | {'Production Matcher ID':<40} | {'Score':<8} | {'composite_xgb Arm ID':<40} | {'Score':<8} | {'Match'}")
        print("-" * 115)
        for i in range(10):
            p_id = prod_ids[i]
            p_sc = prod_scores[i]
            a_id = arm_top10_ids[i]
            a_sc = arm_scores.get(a_id, 0.0)
            status = "MATCH" if p_id == a_id and p_sc == a_sc else "DIFF"
            print(f"#{i+1:<4} | {p_id:<40} | {p_sc:<8.4f} | {a_id:<40} | {a_sc:<8.4f} | {status}")


if __name__ == "__main__":
    main()
