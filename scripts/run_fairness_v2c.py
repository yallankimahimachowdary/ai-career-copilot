"""Script to generate results/fairness_v2c.json covering:
BM25Ranker, SbertRanker, HybridRanker, and CompositeXGBRanker
for BOTH Masking ON and Masking OFF, evaluated on Indian regional student perturbations (perturbations_v2_indian.json).
Also includes Positive Controls A & B under the Indian student dataset to verify sensitivity.
"""

import copy
from datetime import datetime, timezone
import hashlib
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
    DemographicBiasedRanker,
    InstitutionPrestigeBiasedRanker,
    run_demographic_fairness_audit,
    run_institution_tier_audit,
)
from scripts.job_snapshot import load_snapshot

PERTURBATIONS_INDIAN_FILE = Path("data/fairness/perturbations_v2_indian.json")
OUTPUT_FILE = Path("results/fairness_v2c.json")


def compute_file_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()


def main():
    print("=================================================================")
    print("Generating results/fairness_v2c.json (Indian Student Perturbations)")
    print("=================================================================")

    dataset_hash = compute_file_sha256(PERTURBATIONS_INDIAN_FILE)
    print(f"Dataset: {PERTURBATIONS_INDIAN_FILE} (SHA-256: {dataset_hash})")

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

    with open(PERTURBATIONS_INDIAN_FILE, "r", encoding="utf-8") as f:
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
            "perturbations_file": str(PERTURBATIONS_INDIAN_FILE),
            "perturbations_sha256": dataset_hash,
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
        "evaluations": {},
        "positive_controls": {}
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

    # Positive controls
    print("\n--- Running Positive Controls ---")
    hybrid_r = HybridRanker()
    biased_demo_r = DemographicBiasedRanker(hybrid_r)
    biased_demo_audit = run_demographic_fairness_audit(biased_demo_r, resumes, perturbations, pool, apply_masking=False)
    assert not biased_demo_audit["dpr_threshold_passed"], "Control A should fail DPR threshold"
    assert biased_demo_audit["fairlearn_demographic_parity_difference"] > 0.10, "Control A should fail DPD threshold"
    out_data["positive_controls"]["demographic_biased_ranker"] = {
        "audit": biased_demo_audit,
        "failed_as_expected": True,
        "failure_reason": "DPR below 0.80 threshold and DPD above 0.10 threshold under Indian demographic perturbations."
    }

    biased_inst_r = InstitutionPrestigeBiasedRanker(hybrid_r)
    biased_inst_audit = run_institution_tier_audit(biased_inst_r, resumes, perturbations, pool, apply_masking=False)
    assert not biased_inst_audit["tier_dpr_threshold_passed"], "Control B should fail Tier DPR threshold"
    assert biased_inst_audit["tier_score_gap_t1_minus_t3"] > 0.05, "Control B should exhibit tier score gap"
    out_data["positive_controls"]["institution_prestige_biased_ranker"] = {
        "audit": biased_inst_audit,
        "failed_as_expected": True,
        "failure_reason": "Tier DPR below 0.80 and substantial Tier 1 vs Tier 3 score gap."
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(out_data, f, indent=2)

    print(f"\nSaved results to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
