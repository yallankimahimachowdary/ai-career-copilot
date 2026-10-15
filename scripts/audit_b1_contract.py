import json
import os
from pathlib import Path
from app.ranking.base import BaseRanker, RankingResult
from app.ranking.baselines import BM25Ranker, SbertRanker, SkillOverlapRanker
from app.ranking.hybrid import HybridRanker, CompositeXGBRanker
from app.ranking.llm_reranker import LLMReranker
from scripts.job_snapshot import load_snapshot
from scripts.run_ranking_experiment import load_and_anonymize_resumes

def audit_b1():
    print("=== B1: Common Ranking Interface Contract Audit ===")
    snapshot_records, snapshot_meta = load_snapshot("data/snapshots/test_snap_1.json")
    print(f"Loaded snapshot: {len(snapshot_records)} records, sha256: {snapshot_meta.get('sha256_hash')[:12]}...")

    resumes = load_and_anonymize_resumes("uploads/resumes")
    print(f"Loaded {len(resumes)} anonymized resumes: {[r['candidate_name'] for r in resumes]}")

    bm25 = BM25Ranker()
    sbert = SbertRanker()
    overlap = SkillOverlapRanker()
    hybrid = HybridRanker(bm25_ranker=bm25, sbert_ranker=sbert, overlap_ranker=overlap)
    composite = CompositeXGBRanker()
    reranker_mock = LLMReranker(name="hybrid_llm_mock", provider_name="gemini-mock", hybrid_ranker=hybrid)

    rankers = [bm25, sbert, overlap, hybrid, composite, reranker_mock]
    pool_100 = snapshot_records[:100]

    all_passed = True
    test_results = []

    for ranker in rankers:
        print(f"\nChecking ranker: {ranker.name} (class: {ranker.__class__.__name__})")
        assert isinstance(ranker, BaseRanker), f"{ranker.name} is not a BaseRanker"

        for resume in resumes:
            cand_name = resume["candidate_name"]
            res: RankingResult = ranker.rank(resume, pool_100, k=10)

            # Contract checks:
            # 1. Output type
            type_ok = isinstance(res, RankingResult)
            # 2. Length of ranked_job_ids
            len_ok = len(res.ranked_job_ids) == 10
            # 3. All job IDs exist in pool
            pool_ids = {str(r.get("id") or r.get("external_id")) for r in pool_100}
            valid_ids = all(jid in pool_ids for jid in res.ranked_job_ids)
            # 4. Scores dict mapping and types
            scores_ok = isinstance(res.scores, dict) and all(isinstance(res.scores[jid], (int, float)) for jid in res.ranked_job_ids)
            # 5. Method name
            method_ok = res.method_name == ranker.name
            # 6. Metadata dict
            meta_ok = isinstance(res.metadata, dict) and "latency_ms" in res.metadata

            passed = type_ok and len_ok and valid_ids and scores_ok and method_ok and meta_ok
            if not passed:
                all_passed = False

            test_results.append({
                "ranker": ranker.name,
                "candidate": cand_name,
                "type_ok": type_ok,
                "len_k_ok": len_ok,
                "valid_job_ids": valid_ids,
                "scores_dict_and_types_ok": scores_ok,
                "method_name_ok": method_ok,
                "metadata_ok": meta_ok,
                "latency_ms": res.metadata.get("latency_ms"),
                "passed": passed,
            })
            print(f"  [{cand_name}] k=10 -> {res.ranked_job_ids[:3]}... | Scores: {scores_ok} | IDs valid: {valid_ids} | Latency: {res.metadata.get('latency_ms')}ms -> {'PASS' if passed else 'FAIL'}")

    print("\n--- B1 Audit Summary ---")
    print(f"Total contract checks: {len(test_results)}")
    print(f"All checks passed: {all_passed}")
    return all_passed

if __name__ == "__main__":
    audit_b1()
