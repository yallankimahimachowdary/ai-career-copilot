import asyncio
import json
import time
from pathlib import Path
from app.ranking.baselines import BM25Ranker, SbertRanker, SkillOverlapRanker
from app.ranking.hybrid import HybridRanker
from app.ranking.llm_reranker import LLMReranker
from scripts.job_snapshot import load_snapshot
from scripts.run_ranking_experiment import load_and_anonymize_resumes

def audit_b4():
    print("=== B4: LLM Re-Ranker Fresh Verification ===")
    snapshot_records, snapshot_meta = load_snapshot("data/snapshots/test_snap_1.json")
    pool = snapshot_records[:150]
    resumes = load_and_anonymize_resumes("uploads/resumes")

    bm25 = BM25Ranker()
    sbert = SbertRanker()
    overlap = SkillOverlapRanker()
    hybrid = HybridRanker(bm25_ranker=bm25, sbert_ranker=sbert, overlap_ranker=overlap)

    out_dir = Path("artifacts/audit")
    out_dir.mkdir(parents=True, exist_ok=True)

    results = {"ollama": {}, "gemini": {}}

    # 1. Ollama sequential evaluation (strict sequential: one resume at a time)
    print("\n--- 1. Ollama Re-Ranking (Sequential) ---")
    ollama_ranker = LLMReranker(name="hybrid_llm_ollama", provider_name="ollama", hybrid_ranker=hybrid)

    for r in resumes:
        cand_name = r["candidate_name"]
        print(f"\n[Ollama] Running re-ranking for {cand_name}...")
        t0 = time.time()
        res = ollama_ranker.rank(r, pool, k=10)
        elapsed = round(time.time() - t0, 2)

        meta = res.metadata
        repairs = meta.get("repair_attempts", 0)
        hallucinated = meta.get("hallucinated_rejected", 0)
        valid = len(res.ranked_job_ids) == 10

        print(f"  [Ollama - {cand_name}] Done in {elapsed}s | Latency ms: {meta.get('latency_ms')} | Repairs: {repairs} | Rejected: {hallucinated} | Valid k=10: {valid}")
        print(f"  Top 3 jobs: {res.ranked_job_ids[:3]}")

        results["ollama"][cand_name] = {
            "candidate": cand_name,
            "latency_s": elapsed,
            "latency_ms": meta.get("latency_ms"),
            "repair_attempts": repairs,
            "hallucinated_rejected": hallucinated,
            "valid": valid,
            "ranked_jobs": res.ranked_job_ids,
            "scores": res.scores,
            "explanations": meta.get("explanations", []),
        }

    # 2. Gemini live evaluation
    print("\n--- 2. Gemini Live Re-Ranking ---")
    gemini_ranker = LLMReranker(name="hybrid_llm_gemini", provider_name="gemini", hybrid_ranker=hybrid)

    for r in resumes:
        cand_name = r["candidate_name"]
        print(f"\n[Gemini] Running re-ranking for {cand_name}...")
        t0 = time.time()
        res = gemini_ranker.rank(r, pool, k=10)
        elapsed = round(time.time() - t0, 2)

        meta = res.metadata
        repairs = meta.get("repair_attempts", 0)
        hallucinated = meta.get("hallucinated_rejected", 0)
        valid = len(res.ranked_job_ids) == 10

        print(f"  [Gemini - {cand_name}] Done in {elapsed}s | Latency ms: {meta.get('latency_ms')} | Repairs: {repairs} | Rejected: {hallucinated} | Valid k=10: {valid}")
        print(f"  Top 3 jobs: {res.ranked_job_ids[:3]}")

        results["gemini"][cand_name] = {
            "candidate": cand_name,
            "latency_s": elapsed,
            "latency_ms": meta.get("latency_ms"),
            "repair_attempts": repairs,
            "hallucinated_rejected": hallucinated,
            "valid": valid,
            "ranked_jobs": res.ranked_job_ids,
            "scores": res.scores,
            "explanations": meta.get("explanations", []),
        }

    out_file = out_dir / "b4_reranker_verification.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved fresh B4 verification results to {out_file}")

if __name__ == "__main__":
    audit_b4()
