import json
import os
from pathlib import Path
from app.ranking.baselines import BM25Ranker, SbertRanker, SkillOverlapRanker
from scripts.job_snapshot import load_snapshot
from scripts.run_ranking_experiment import load_and_anonymize_resumes

def audit_b2():
    print("=== B2: Baseline Ranking Methods & Determinism Audit ===")
    snapshot_records, snapshot_meta = load_snapshot("data/snapshots/test_snap_1.json")
    pool = snapshot_records[:150]
    resumes = load_and_anonymize_resumes("uploads/resumes")

    out_dir = Path("artifacts/audit")
    out_dir.mkdir(parents=True, exist_ok=True)

    bm25 = BM25Ranker()
    sbert = SbertRanker()
    overlap = SkillOverlapRanker()

    methods = [("bm25", bm25), ("sbert", sbert), ("overlap", overlap)]

    audit_data = {}

    for name, ranker in methods:
        print(f"\nEvaluating baseline: {name}")
        audit_data[name] = {}

        for r in resumes:
            cand_name = r["candidate_name"]
            print(f"  Running {name} twice for {cand_name}...")

            # Run 1
            run1 = ranker.rank(r, pool, k=10)
            # Run 2
            run2 = ranker.rank(r, pool, k=10)

            ids1 = run1.ranked_job_ids
            ids2 = run2.ranked_job_ids
            scores1 = [run1.scores[jid] for jid in ids1]
            scores2 = [run2.scores[jid] for jid in ids2]

            is_identical = (ids1 == ids2) and (scores1 == scores2)
            print(f"    Ordered Job IDs match: {ids1 == ids2}")
            print(f"    Scores match: {scores1 == scores2}")
            print(f"    Determinism PASS: {is_identical}")

            # Top 10 items
            top10_details = []
            for rank, jid in enumerate(ids1, 1):
                rec = next((x for x in pool if str(x.get("id") or x.get("external_id")) == jid), {})
                top10_details.append({
                    "rank": rank,
                    "job_id": jid,
                    "score": round(run1.scores[jid], 4),
                    "title": rec.get("title"),
                    "company": rec.get("company") or rec.get("company_name"),
                })

            audit_data[name][cand_name] = {
                "run1_ids": ids1,
                "run2_ids": ids2,
                "deterministic": is_identical,
                "top10": top10_details,
            }

    out_file = out_dir / "b2_baseline_verification.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(audit_data, f, indent=2)

    print(f"\nSaved fresh B2 verification results to {out_file}")

if __name__ == "__main__":
    audit_b2()
