import json
from pathlib import Path
from app.ranking.baselines import BM25Ranker, SbertRanker, SkillOverlapRanker
from app.ranking.hybrid import HybridRanker, CompositeXGBRanker
from scripts.job_snapshot import load_snapshot
from scripts.run_ranking_experiment import load_and_anonymize_resumes

def audit_b3():
    print("=== B3: Hybrid vs Composite XGB Side-by-Side Verification ===")
    snapshot_records, snapshot_meta = load_snapshot("data/snapshots/test_snap_1.json")
    pool = snapshot_records[:150]
    resumes = load_and_anonymize_resumes("uploads/resumes")

    bm25 = BM25Ranker()
    sbert = SbertRanker()
    overlap = SkillOverlapRanker()
    hybrid = HybridRanker(bm25_ranker=bm25, sbert_ranker=sbert, overlap_ranker=overlap)
    composite = CompositeXGBRanker()

    results = {}

    for r in resumes:
        cand_name = r["candidate_name"]
        print(f"\n--- Candidate: {cand_name} ---")

        res_hybrid = hybrid.rank(r, pool, k=5)
        res_comp = composite.rank(r, pool, k=5)

        table_rows = []
        for rank in range(1, 6):
            # Hybrid
            h_jid = res_hybrid.ranked_job_ids[rank - 1]
            h_score = res_hybrid.scores[h_jid]
            h_rec = next((x for x in pool if str(x.get("id") or x.get("external_id")) == h_jid), {})
            h_title = h_rec.get("title", "N/A")

            # Composite XGB
            c_jid = res_comp.ranked_job_ids[rank - 1]
            c_score = res_comp.scores[c_jid]
            c_rec = next((x for x in pool if str(x.get("id") or x.get("external_id")) == c_jid), {})
            c_title = c_rec.get("title", "N/A")

            table_rows.append({
                "rank": rank,
                "hybrid": {"job_id": h_jid, "title": h_title, "score": h_score},
                "composite_xgb": {"job_id": c_jid, "title": c_title, "score": c_score},
            })

            print(f"Rank {rank}:")
            print(f"  Hybrid:        [{h_jid[:8]}] {h_score:.4f} | {h_title[:40]}")
            print(f"  Composite XGB: [{c_jid[:8]}] {c_score:.4f} | {c_title[:40]}")

        results[cand_name] = table_rows

    out_file = Path("artifacts/audit/b3_side_by_side_comparison.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved side-by-side comparison to {out_file}")

if __name__ == "__main__":
    audit_b3()
