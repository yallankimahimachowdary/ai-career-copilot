"""Script to generate results/fairness_v2b.json covering:
BM25Ranker, SbertRanker, HybridRanker, and CompositeXGBRanker
for BOTH Masking ON and Masking OFF, evaluating both name/gender-cue swaps and institution-tier swaps.
"""

import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath("."))

from app.ranking.baselines import BM25Ranker, SbertRanker
from app.ranking.hybrid import CompositeXGBRanker, HybridRanker
from scripts.evaluate_fairness_v2 import (
    SNAPSHOT_FILE,
    SYNTHETIC_RESUMES_FILE,
    PERTURBATIONS_FILE,
    run_demographic_fairness_audit,
    run_institution_tier_audit,
)
from scripts.job_snapshot import load_snapshot

OUTPUT_FILE = Path("results/fairness_v2b.json")


def main():
    print("=================================================================")
    print("Generating results/fairness_v2b.json (R7 Stage 0 Fairness Gaps)")
    print("=================================================================")

    jobs, _ = load_snapshot(str(SNAPSHOT_FILE))
    pool = jobs[:50]

    # Pre-embed pool
    from app.services.embedding_service import get_sentence_transformer
    st_model = get_sentence_transformer()
    job_texts = [
        f"{j.get('title','')} {j.get('company','')} {' '.join(j.get('skills',[]))} {j.get('description','')[:500]}"
        for j in pool
    ]
    embs = st_model.encode(job_texts, batch_size=64, convert_to_numpy=True, normalize_embeddings=True)
    for j, emb in zip(pool, embs):
        j["embedding"] = emb.tolist()

    resumes = []
    with open(SYNTHETIC_RESUMES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                resumes.append(json.loads(line))

    with open(PERTURBATIONS_FILE, "r", encoding="utf-8") as f:
        perturbations = json.load(f)

    rankers = [
        ("bm25", BM25Ranker()),
        ("sbert", SbertRanker()),
        ("hybrid", HybridRanker()),
        ("composite_xgb", CompositeXGBRanker()),
    ]

    out_data = {
        "metadata": {
            "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
            "synthetic_resumes_count": len(resumes),
            "perturbations_count": len(perturbations["demographic_name_sets"]),
            "institution_tiers_count": 3,
            "job_pool_size": len(pool),
            "rankers_evaluated": [name for name, _ in rankers],
            "equivalence_margin": {
                "kendall_tau_threshold": 0.90,
                "top5_jaccard_threshold": 0.90,
                "score_delta_epsilon": 0.05,
                "tier_score_gap_epsilon": 0.05,
                "justification": "Equivalence margin epsilon=0.05 corresponds to 5% score deviation, ensuring candidate ranking order is statistically and practically invariant to protected demographic attributes."
            }
        },
        "evaluations": {}
    }

    for name, r in rankers:
        print(f"\n--- Evaluating {name} ---")
        out_data["evaluations"][name] = {}

        for masking_state in (True, False):
            m_label = "masking_on" if masking_state else "masking_off"
            print(f"  [{name}] {m_label}...")
            demo_eval = run_demographic_fairness_audit(r, resumes, perturbations, pool, apply_masking=masking_state)
            tier_eval = run_institution_tier_audit(r, resumes, perturbations, pool, apply_masking=masking_state)

            out_data["evaluations"][name][m_label] = {
                "demographic_fairness": demo_eval,
                "institution_tier_fairness": tier_eval,
            }
            print(f"    DPD: {demo_eval['fairlearn_demographic_parity_difference']}, DPR: {demo_eval['fairlearn_demographic_parity_ratio']}")
            print(f"    Tier gap (T1 - T3): {tier_eval['tier_score_gap_t1_minus_t3']}")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(out_data, f, indent=2)

    print(f"\nSaved comprehensive fairness evaluations to {OUTPUT_FILE}")
    print("=================================================================")


if __name__ == "__main__":
    main()
