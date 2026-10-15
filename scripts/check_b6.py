"""B6 Checkpoint: Counterfactual Skill-Gap Test with Absent Controls & Multi-Draw Evaluation.

Requirements:
- Random control skills strictly absent from candidate resume AND not required by target job.
- At least 20 random draws per resume-job pair.
- At least 3 target jobs per resume.
- Report mean ± standard deviation for score change and rank change (suggested vs random).
"""

import glob
from pathlib import Path
from typing import Any, Dict, List
import pypdf

from app.ranking.baselines import SbertRanker
from app.ranking.counterfactual import CounterfactualTester
from app.ranking.hybrid import HybridRanker
from app.services.anonymizer import anonymize_resume
from app.services.parser_agent import parser_agent
from scripts.job_snapshot import load_snapshot


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
        "experience": [e.model_dump() for e in parsed.experience],
    }


def main():
    records, meta = load_snapshot("data/snapshots/test_snap_1.json")
    pool = records[:100]

    mahi_res = prepare_resume("uploads/resumes/*Mahima*", "Mahima")
    deepika_res = prepare_resume("uploads/resumes/*Deepika*", "Deepika")

    sbert = SbertRanker()
    hybrid = HybridRanker(sbert_ranker=sbert)
    tester = CounterfactualTester(hybrid_ranker=hybrid, sbert_ranker=sbert, seed=42)

    # 3 target jobs per resume
    # Pick jobs with relevant titles and some missing requirements
    mahi_targets = [
        (pool[0], ["Docker", "AWS", "FastAPI"]),
        (pool[3], ["React", "TypeScript", "Node.js"]),
        (pool[7], ["Kubernetes", "CI/CD", "Redis"]),
    ]

    deepika_targets = [
        (pool[1], ["Bioinformatics", "Microbiology", "Data Science"]),
        (pool[4], ["PCR", "Cell Culture", "Molecular Biology"]),
        (pool[8], ["Machine Learning", "Python", "Data Science"]),
    ]

    all_results = []

    print("\n================ Counterfactual Skill-Gap Evaluation (20 Draws, 3 Jobs/Resume) ================")

    for cand_name, resume, targets in [("Mahi", mahi_res, mahi_targets), ("Deepika", deepika_res, deepika_targets)]:
        print(f"\nCandidate: {cand_name}")
        print("-" * 80)
        for job_idx, (job, suggested_skills) in enumerate(targets, 1):
            res = tester.run_multi_draw_test(
                resume=resume,
                target_job=job,
                suggested_missing_skills=suggested_skills,
                job_pool=pool,
                n_draws=20,
            )
            res["candidate"] = cand_name
            res["job_index"] = job_idx
            all_results.append(res)

            print(f"Target Job #{job_idx}: {res['target_title'][:35]} (ID: {res['target_job_id'][:8]}...)")
            print(f"  Suggested Missing Skills ({len(suggested_skills)}): {suggested_skills}")
            print(f"  Base Hybrid Rank: #{res['base_hybrid_rank']} (Score: {res['base_hybrid_score']:.4f})")
            print(f"  Condition (a) Suggested Skills Added:")
            print(f"    - Hybrid: Delta Score = {res['suggested_delta_hybrid_score']:+.4f} | Delta Rank = {res['suggested_delta_hybrid_rank']:+d}")
            print(f"    - SBERT : Delta Score = {res['suggested_delta_sbert_score']:+.4f} | Delta Rank = {res['suggested_delta_sbert_rank']:+d}")
            print(f"  Condition (b) Random Control Skills (20 draws, mean +/- std):")
            print(f"    - Hybrid: Delta Score = {res['random_delta_hybrid_score_mean']:+.4f} +/- {res['random_delta_hybrid_score_std']:.4f} | Delta Rank = {res['random_delta_hybrid_rank_mean']:+.2f} +/- {res['random_delta_hybrid_rank_std']:.2f}")
            print(f"    - SBERT : Delta Score = {res['random_delta_sbert_score_mean']:+.4f} +/- {res['random_delta_sbert_score_std']:.4f} | Delta Rank = {res['random_delta_sbert_rank_mean']:+.2f} +/- {res['random_delta_sbert_rank_std']:.2f}")
            print()

    csv_path = Path("artifacts/experiments/counterfactual_results.csv")
    tester.export_csv(all_results, csv_path)
    print(f"Results exported to {csv_path}")


if __name__ == "__main__":
    main()
