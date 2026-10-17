import glob, pypdf, time
from app.services.parser_agent import parser_agent
from app.services.anonymizer import anonymize_resume
from scripts.job_snapshot import load_snapshot
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

cand_a_res = prepare_resume('uploads/resumes/*candidate_a*', 'Candidate A')
cand_b_res = prepare_resume('uploads/resumes/*candidate_b*', 'Candidate B')

reranker = LLMReranker(name='hybrid_llm_gemini', provider_name='gemini')

for name, res in [('Candidate A', cand_a_res), ('Candidate B', cand_b_res)]:
    print(f"\n=== Testing Gemini Re-Ranker for {name} ===")
    t0 = time.time()
    try:
        res_rank = reranker.rank(res, sample_jobs, k=10)
        elapsed = time.time() - t0
        meta = res_rank.metadata
        print("RESULT: SUCCESS")
        print("Status: success")
        print(f"Latency: {elapsed:.2f}s (LLM Latency: {meta.get('latency_ms')}ms)")
        print(f"Attempts: {meta.get('attempts')}")
        print(f"Repairs: {meta.get('repair_count')}")
        print(f"Model: {meta.get('model')} (Requested: {meta.get('requested_model')})")
        print("Top 3 ranked job IDs:", res_rank.ranked_job_ids[:3])
        exps = meta.get('explanations', [])
        if exps:
            print("Top 1 Explanation:", exps[0])
    except Exception as e:
        print("RESULT: FAILED RUN RECORDED")
        print("Status: failed")
        print(f"Error type: {type(e).__name__}")
        print(f"Error: {str(e)}")
