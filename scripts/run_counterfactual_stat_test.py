"""B6 Counterfactual Evaluation with Statistical Tests (Round 2 Fixes).

- Target jobs chosen from LLM re-ranker's top 10 (excluding rank 1).
- rank_gain = old_rank - new_rank (positive means improved rank).
- Evaluates Condition (a) suggested skills vs Condition (b) 20 random control draws.
- Reports improvement rate, mean rank gain, lift over control with 95% CI, and Wilcoxon signed-rank test.
"""

import glob
from pathlib import Path
from typing import Any, Dict, List
import numpy as np
import pypdf
from scipy import stats

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
    job_map = {str(j.get("id") or j.get("external_id")): j for j in pool}

    mahi_res = prepare_resume("uploads/resumes/*Mahima*", "Mahima")
    deepika_res = prepare_resume("uploads/resumes/*Deepika*", "Deepika")

    sbert = SbertRanker()
    hybrid = HybridRanker(sbert_ranker=sbert)
    tester = CounterfactualTester(hybrid_ranker=hybrid, sbert_ranker=sbert, seed=42)

    # Pick 3 target jobs per candidate from LLM re-ranker's top 10 (excluding Rank 1):
    # Mahi LLM Top 10 ranks:
    # Rank 2: 09db5aa5-b74a-4c37-9f7f-b64a207eb2bc (Java Backend)
    # Rank 3: 60cc8518-539a-40ec-a64e-44e977668905 (Fullstack)
    # Rank 4: a87e149f-ddb4-4612-8a10-f9e67e1619aa (Python Developer)
    mahi_targets = [
        (job_map.get("09db5aa5-b74a-4c37-9f7f-b64a207eb2bc") or pool[2], ["Spring Boot", "Microservices", "REST API"]),
        (job_map.get("60cc8518-539a-40ec-a64e-44e977668905") or pool[3], ["React", "TypeScript", "Node.js"]),
        (job_map.get("a87e149f-ddb4-4612-8a10-f9e67e1619aa") or pool[5], ["Django", "FastAPI", "Docker"]),
    ]

    # Deepika LLM Top 10 ranks (excluding Rank 1: 4b7cb06f):
    # Rank 2: 54d2b933-a4f8-4142-9a68-929dba9d89d5 (Data Scientist Intern)
    # Rank 3: dd5c8a5a-c0a0-4edb-945c-3f0b99dbaf63 (Python Developer Intern)
    # Rank 4: b039b9cf-1ea4-4168-b1be-e0ba370b87d1 (Senior Scientist - Biologist)
    deepika_targets = [
        (job_map.get("54d2b933-a4f8-4142-9a68-929dba9d89d5") or pool[1], ["Machine Learning", "Data Science", "SQL"]),
        (job_map.get("dd5c8a5a-c0a0-4edb-945c-3f0b99dbaf63") or pool[4], ["Django", "FastAPI", "REST API"]),
        (job_map.get("b039b9cf-1ea4-4168-b1be-e0ba370b87d1") or pool[8], ["Cell Culture", "Molecular Biology", "PCR"]),
    ]

    all_records = []
    hybrid_sug_gains = []
    hybrid_ctrl_gains = []
    sbert_sug_gains = []
    sbert_ctrl_gains = []

    print("\n================ Counterfactual Skill-Gap Test (LLM Top 10 Targets, Ranks Excl. Rank 1) ================")

    for cand_name, resume, targets in [("Mahi", mahi_res, mahi_targets), ("Deepika", deepika_res, deepika_targets)]:
        print(f"\nCandidate: {cand_name}")
        print("-" * 85)
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
            all_records.append(res)

            hy_sug = res["suggested_rank_gain_hybrid"]
            hy_ctrl = res["random_rank_gain_hybrid_mean"]
            sb_sug = res["suggested_rank_gain_sbert"]
            sb_ctrl = res["random_rank_gain_sbert_mean"]

            hybrid_sug_gains.append(hy_sug)
            hybrid_ctrl_gains.append(hy_ctrl)
            sbert_sug_gains.append(sb_sug)
            sbert_ctrl_gains.append(sb_ctrl)

            print(f"Target Job #{job_idx}: {res['target_title'][:32]} (ID: {res['target_job_id'][:8]}...)")
            print(f"  Suggested Skills ({len(suggested_skills)}): {suggested_skills}")
            print(f"  Base Hybrid Rank: #{res['base_hybrid_rank']} | Base SBERT Rank: #{res['base_sbert_rank']}")
            print(f"  Condition (a) Suggested Skills Added:")
            print(f"    - Hybrid rank_gain: {hy_sug:+d} (old={res['base_hybrid_rank']} -> new={res['base_hybrid_rank'] - hy_sug})")
            print(f"    - SBERT  rank_gain: {sb_sug:+d} (old={res['base_sbert_rank']} -> new={res['base_sbert_rank'] - sb_sug})")
            print(f"  Condition (b) Random Control Draws (20 draws, mean +/- std):")
            print(f"    - Hybrid rank_gain: {hy_ctrl:+.2f} +/- {res['random_rank_gain_hybrid_std']:.2f}")
            print(f"    - SBERT  rank_gain: {sb_ctrl:+.2f} +/- {res['random_rank_gain_sbert_std']:.2f}")

    # Export updated CSV
    csv_path = Path("artifacts/experiments/counterfactual_results.csv")
    tester.export_csv(all_records, csv_path)
    print(f"\nExported {len(all_records)} evaluation rows to {csv_path}")

    # Statistical Evaluation across pairs
    def analyze_stats(sug_list, ctrl_list, name):
        sug_arr = np.array(sug_list, dtype=float)
        ctrl_arr = np.array(ctrl_list, dtype=float)
        diff = sug_arr - ctrl_arr
        n = len(diff)
        mean_lift = float(np.mean(diff))
        std_lift = float(np.std(diff, ddof=1)) if n > 1 else 0.0
        se_lift = std_lift / np.sqrt(n) if n > 0 else 0.0
        ci_lower = mean_lift - 1.96 * se_lift
        ci_upper = mean_lift + 1.96 * se_lift

        improved_rate = float(np.mean(sug_arr > 0)) * 100.0
        improved_over_ctrl_rate = float(np.mean(diff > 0)) * 100.0

        # Wilcoxon signed-rank test
        # When sample has zeros or ties, use pratt or wilcoxon with zero_method
        try:
            w_stat, p_val = stats.wilcoxon(sug_arr, ctrl_arr, zero_method="wilcox")
        except Exception:
            w_stat, p_val = 0.0, 1.0

        print(f"\n=== Statistical Summary: {name} ===")
        print(f"  Pairs evaluated              : {n}")
        print(f"  Improvement Rate (gain > 0)   : {improved_rate:.1f}%")
        print(f"  Mean Suggested rank_gain      : {np.mean(sug_arr):+.2f}")
        print(f"  Mean Control rank_gain        : {np.mean(ctrl_arr):+.2f}")
        print(f"  Mean Lift Over Control        : {mean_lift:+.2f} (95% CI: [{ci_lower:.2f}, {ci_upper:.2f}])")
        print(f"  Wilcoxon signed-rank test p   : {p_val:.4f} (W-statistic={w_stat})")

    analyze_stats(hybrid_sug_gains, hybrid_ctrl_gains, "HYBRID RANKER")
    analyze_stats(sbert_sug_gains, sbert_ctrl_gains, "SBERT (EMBEDDING-ONLY) SCORER")


if __name__ == "__main__":
    main()
