from app.ranking.llm_reranker import LLMReranker
from scripts.job_snapshot import load_snapshot
import glob, pypdf
from app.services.parser_agent import parser_agent
from app.services.anonymizer import anonymize_resume

records, _ = load_snapshot('data/snapshots/test_snap_1.json')
pool = records[:100]

def prepare(pattern, name):
    f = glob.glob(pattern)[0]
    r = pypdf.PdfReader(f)
    text = '\n'.join([p.extract_text() or '' for p in r.pages])
    anon = anonymize_resume(text, candidate_name=name)
    p = parser_agent._parse_with_rules(anon)
    return {'candidate_name': name, 'raw_text': anon, 'summary': p.summary or '', 'skills': p.skills, 'experience': [e.model_dump() for e in p.experience]}

cand_a = prepare('uploads/resumes/*candidate_a*', 'Candidate A')
cand_b = prepare('uploads/resumes/*candidate_b*', 'Candidate B')

reranker = LLMReranker(name='hybrid_llm_gemini', provider_name='gemini')
res_m = reranker.rank(cand_a, pool, k=10)
res_d = reranker.rank(cand_b, pool, k=10)

print("Candidate A Gemini Rerank Top 10:")
for idx, jid in enumerate(res_m.ranked_job_ids, 1):
    job = next(j for j in pool if str(j.get('id') or j.get('external_id')) == jid)
    print(f"  {idx}. {jid[:8]} - {job.get('title')} ({job.get('company')})")

print("\nCandidate B Gemini Rerank Top 10:")
for idx, jid in enumerate(res_d.ranked_job_ids, 1):
    job = next(j for j in pool if str(j.get('id') or j.get('external_id')) == jid)
    print(f"  {idx}. {jid[:8]} - {job.get('title')} ({job.get('company')})")
