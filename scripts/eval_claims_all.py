"""Evaluate ClaimVerifier across all 10 explanations for Mahi and Deepika (Ollama and Gemini)."""

import glob
import pypdf
import time
import numpy as np
from app.services.parser_agent import parser_agent
from app.services.anonymizer import anonymize_resume
from scripts.job_snapshot import load_snapshot
from app.ranking.llm_reranker import LLMReranker
from app.ranking.claim_verifier import ClaimVerifier

records, meta = load_snapshot('data/snapshots/test_snap_1.json')
sample_jobs = records[:100]
jobs_map = {str(j.get('id') or j.get('external_id') or ''): j for j in sample_jobs}

def prepare_resume(glob_pattern, candidate_name):
    fpath = glob.glob(glob_pattern)[0]
    reader = pypdf.PdfReader(fpath)
    raw = '\n'.join([p.extract_text() or '' for p in reader.pages])
    anon_text = anonymize_resume(raw, candidate_name=candidate_name)
    parsed = parser_agent._parse_with_rules(anon_text)
    return {
        'candidate_name': candidate_name,
        'raw_text': anon_text,
        'summary': parsed.summary or '',
        'skills': parsed.skills,
        'experience': [e.model_dump() for e in parsed.experience],
    }

mahi_res = prepare_resume('uploads/resumes/*Mahima*', 'Mahima')
deepika_res = prepare_resume('uploads/resumes/*Deepika*', 'Deepika')

verifier = ClaimVerifier()

for provider in ["ollama", "gemini"]:
    print(f"\n=======================================================")
    print(f"      EVALUATING PROVIDER: {provider.upper()}")
    print(f"=======================================================")
    reranker = LLMReranker(name=f"hybrid_llm_{provider}", provider_name=provider)
    
    for c_name, resume in [("Mahi", mahi_res), ("Deepika", deepika_res)]:
        print(f"\n--- Candidate: {c_name} (Provider: {provider}) ---")
        t0 = time.time()
        try:
            rank_result = reranker.rank(resume, sample_jobs, k=10)
            elapsed = time.time() - t0
            meta = rank_result.metadata
            print(f"Rerank latency: {elapsed:.2f}s (LLM: {meta.get('latency_ms', 0):.2f}ms)")
            print(f"Repairs: {meta.get('repair_count')}, Hallucinations rejected: {meta.get('hallucinated_ids_rejected')}")
            
            explanations = meta.get('explanations', [])
            print(f"Total explanations received: {len(explanations)}")
            
            scores = []
            for i, exp in enumerate(explanations[:10]):
                job = jobs_map.get(exp.get('job_id'))
                if not job:
                    # Search by fallback
                    job = sample_jobs[0]
                ver = verifier.verify_explanation(exp, resume, job)
                scores.append(ver.faithfulness_score)
                print(f"  Exp #{i+1} [Rank {exp.get('rank')} - Job {exp.get('job_id')[:8]}...]: faithfulness={ver.faithfulness_score:.2f} "
                      f"(claims {ver.supported_claims}/{ver.total_claims}, inv_matched={len(ver.invalid_matched)}, "
                      f"inv_missing={len(ver.invalid_missing)}, unsupp_reason={len(ver.unsupported_reason_skills)})")
            
            if scores:
                mean_s = np.mean(scores)
                std_s = np.std(scores)
                min_s = np.min(scores)
                max_s = np.max(scores)
                median_s = np.median(scores)
                print(f"\nFaithfulness Summary for {c_name} ({provider}):")
                print(f"  Mean +/- Std: {mean_s:.4f} +/- {std_s:.4f}")
                print(f"  Median: {median_s:.4f} | Min: {min_s:.4f} | Max: {max_s:.4f}")
                print(f"  Distribution: {[round(s, 2) for s in scores]}")
        except Exception as e:
            print(f"ERROR running {provider} for {c_name}: {type(e).__name__}: {e}")
