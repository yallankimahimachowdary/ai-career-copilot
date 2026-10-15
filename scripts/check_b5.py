"""B5 Checkpoint: Evaluate ClaimVerifier on live B4 Ollama outputs."""

import glob
import pypdf
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

# Evaluate explanation claims from Mahi's top explanation
verifier = ClaimVerifier()

# Test sample explanation from real Ollama output
sample_explanation = {
    "job_id": "1b94478e-9f81-4eca-82a0-915e216bbce4",
    "rank": 1,
    "matched_skills": ["Communication", "Git/GitHub", "HTML/CSS", "JavaScript", "Problem Solving", "REST API"],
    "missing_skills": ["Agile/Scrum", "React", "SQL"],
    "reason": "The candidate has relevant skills for the Frontend Developer role, with experience in Git/GitHub, HTML/CSS, JavaScript, and Problem Solving.",
}

job = jobs_map.get("1b94478e-9f81-4eca-82a0-915e216bbce4") or sample_jobs[0]
res = verifier.verify_explanation(sample_explanation, mahi_res, job)

print("=== B5 Real Ollama Explanation Faithfulness ===")
print("Job ID:", res.job_id)
print("Faithfulness Score:", res.faithfulness_score)
print("Supported Claims:", f"{res.supported_claims}/{res.total_claims}")
print("Valid Matched:", res.valid_matched)
print("Invalid Matched:", res.invalid_matched)
print("Valid Missing:", res.valid_missing)
print("Invalid Missing:", res.invalid_missing)
print("Unsupported Reason Skills:", res.unsupported_reason_skills)
print("B5 CHECKPOINT COMPLETED SUCCESSFULLY!")
