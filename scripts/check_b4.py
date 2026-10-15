"""B4 Checkpoint: Test LLMReranker with Ollama on both Mahi's and Deepika's resumes."""

import glob
import pypdf
import time
from app.services.parser_agent import parser_agent
from app.services.anonymizer import anonymize_resume
from scripts.job_snapshot import load_snapshot
from app.ranking.hybrid import HybridRanker
from app.ranking.llm_reranker import LLMReranker

records, meta = load_snapshot('data/snapshots/test_snap_1.json')
sample_jobs = records[:100]

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

reranker = LLMReranker(name="hybrid_llm_ollama", provider_name="ollama")

for name, res in [('Mahi', mahi_res), ('Deepika', deepika_res)]:
    print(f"\n================ Running B4 Ollama Re-Ranker for {name} ================")
    t0 = time.time()
    result = reranker.rank(res, sample_jobs, k=10)
    elapsed = time.time() - t0
    meta = result.metadata
    print(f"Candidate: {name}")
    print(f"Latency: {elapsed:.2f}s (LLM Latency: {meta.get('latency_ms', 0):.2f}ms)")
    print(f"Attempts: {meta.get('attempts')}, Repairs: {meta.get('repair_count')}, Hallucinations Rejected: {meta.get('hallucinated_ids_rejected')}")
    print("Top 3 Ranked Job IDs:", result.ranked_job_ids[:3])
    explanations = meta.get('explanations', [])
    if explanations:
        first = explanations[0]
        print(f"Top 1 explanation: Job={first.get('job_id')} | Matched={first.get('matched_skills')} | Missing={first.get('missing_skills')} | Reason={first.get('reason')}")

print("\nB4 CHECKPOINT COMPLETED SUCCESSFULLY!")
