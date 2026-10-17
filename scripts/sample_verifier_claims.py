import glob, pypdf, json, random
from app.services.parser_agent import parser_agent
from app.services.anonymizer import anonymize_resume
from scripts.job_snapshot import load_snapshot
from app.ranking.claim_verifier import ClaimVerifier
from app.core.taxonomy import extract_canonical_skills

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

cand_a_res = prepare_resume('uploads/resumes/*candidate_a*', 'Candidate A')
cand_b_res = prepare_resume('uploads/resumes/*candidate_b*', 'Candidate B')

verifier = ClaimVerifier()

# Real explanations collected from Ollama and Gemini runs:
sample_exps = [
    # Candidate A - Job 1 (Ollama)
    ("Candidate A", "54d2b933-a4f8-4142-9a68-929dba9d89d5", {
        "job_id": "54d2b933-a4f8-4142-9a68-929dba9d89d5", "rank": 1,
        "matched_skills": ["Data Science", "Machine Learning", "Python"],
        "missing_skills": ["Agile/Scrum", "Git/GitHub", "Leadership"],
        "reason": "The candidate has relevant skills in Data Science, Machine Learning, and Python, making them a strong fit for this role."
    }),
    # Candidate A - Job 2 (Ollama)
    ("Candidate A", "09db5aa5-b74a-4c37-9f7f-b64a207eb2bc", {
        "job_id": "09db5aa5-b74a-4c37-9f7f-b64a207eb2bc", "rank": 2,
        "matched_skills": ["Java", "SQL"],
        "missing_skills": ["Spring Boot", "Microservices"],
        "reason": "Strong core skills in Java and SQL for backend engineering."
    }),
    # Candidate A - Job 3 (Gemini)
    ("Candidate A", "f4dbdcdc-c272-4149-8002-95c9fb03b0fd", {
        "job_id": "f4dbdcdc-c272-4149-8002-95c9fb03b0fd", "rank": 1,
        "matched_skills": ["Communication", "Java", "JavaScript", "Problem Solving", "Python"],
        "missing_skills": ["HTML/CSS"],
        "reason": "Excellent alignment with candidate's core programming languages (Java, Python, JavaScript) and soft skills for a fullstack role."
    }),
    # Candidate B - Job 1 (Ollama)
    ("Candidate B", "4b7cb06f-2f90-4297-a25e-3ab507327897", {
        "job_id": "4b7cb06f-2f90-4297-a25e-3ab507327897", "rank": 1,
        "matched_skills": ["Microbiology", "Molecular Biology"],
        "missing_skills": ["Communication", "Drug Discovery", "Leadership"],
        "reason": "The candidate has relevant skills in Microbiology and Molecular Biology, but lacks skills in Communication, Drug Discovery, and Leadership, which are required for the Senior Scientist - Biologist role."
    }),
    # Candidate B - Job 2 (Gemini)
    ("Candidate B", "4b7cb06f-2f90-4297-a25e-3ab507327897", {
        "job_id": "4b7cb06f-2f90-4297-a25e-3ab507327897", "rank": 1,
        "matched_skills": ["Microbiology"],
        "missing_skills": [],
        "reason": "This Chennai-based R&D trainee role perfectly aligns with the candidate's microbiology background, location, and seeking of research hands-on experience."
    }),
    # Candidate B - Job 3 (Ollama)
    ("Candidate B", "54d2b933-a4f8-4142-9a68-929dba9d89d5", {
        "job_id": "54d2b933-a4f8-4142-9a68-929dba9d89d5", "rank": 2,
        "matched_skills": ["Python"],
        "missing_skills": ["Machine Learning", "Data Science"],
        "reason": "Candidate has basic Python programming but lacks required advanced machine learning frameworks."
    }),
    # Candidate B - Job 4 (Gemini)
    ("Candidate B", "b039b9cf-1ea4-4168-b1be-e0ba370b87d1", {
        "job_id": "b039b9cf-1ea4-4168-b1be-e0ba370b87d1", "rank": 2,
        "matched_skills": ["Molecular Biology", "Cell Culture"],
        "missing_skills": ["Next-Generation Sequencing", "CRISPR"],
        "reason": "Candidate demonstrates foundational wet-lab competency in Molecular Biology and Cell Culture."
    }),
]

individual_claims = []

for cand_name, jid, exp in sample_exps:
    resume = cand_a_res if cand_name == "Candidate A" else cand_b_res
    job = jobs_map.get(jid, sample_jobs[0])
    res_skills = verifier._get_resume_skills(resume)
    job_skills = verifier._get_job_skills(job)
    ver = verifier.verify_explanation(exp, resume, job)

    # 1. Matched skill claims
    for s in exp.get("matched_skills", []):
        is_valid = s in ver.valid_matched
        individual_claims.append({
            "candidate": cand_name,
            "type": "matched_skill",
            "claim": f"Candidate has matched skill: '{s}'",
            "verdict": "SUPPORTED" if is_valid else "UNSUPPORTED",
            "evidence": f"Resume skills extracted: {list(res_skills)[:8]}... (found: {is_valid})",
            "job_title": job.get("title"),
        })

    # 2. Missing skill claims
    for s in exp.get("missing_skills", []):
        is_valid = s in ver.valid_missing
        in_job = s.lower() in job_skills or any(cs in job_skills for cs in [s.lower()])
        in_res = s.lower() in res_skills or any(cs in res_skills for cs in [s.lower()])
        individual_claims.append({
            "candidate": cand_name,
            "type": "missing_skill",
            "claim": f"Job requires and candidate lacks: '{s}'",
            "verdict": "SUPPORTED" if is_valid else "UNSUPPORTED",
            "evidence": f"Required in job: {in_job} | Absent in resume: {not in_res}",
            "job_title": job.get("title"),
        })

    # 3. Reason skill claims
    reason_skills = extract_canonical_skills(exp.get("reason", ""))
    for rs in reason_skills:
        is_valid = rs not in ver.unsupported_reason_skills
        individual_claims.append({
            "candidate": cand_name,
            "type": "reason_claim",
            "claim": f"Reason cites skill: '{rs}'",
            "verdict": "SUPPORTED" if is_valid else "UNSUPPORTED",
            "evidence": f"Skill '{rs}' valid in candidate profile or matched/missing pool: {is_valid}",
            "job_title": job.get("title"),
        })

random.seed(42)
sampled_20 = random.sample(individual_claims, min(20, len(individual_claims)))

print("\n" + "=" * 90)
print("       20 RANDOMLY SAMPLED VERIFIER CLAIMS WITH VERDICT & EVIDENCE")
print("=" * 90)

for idx, c in enumerate(sampled_20, 1):
    print(f"\nClaim #{idx:02d} [{c['type'].upper()}] - {c['candidate']} for job: {c['job_title']}")
    print(f"  Claim  : {c['claim']}")
    print(f"  Verdict: {c['verdict']}")
    print(f"  Evidence: {c['evidence']}")

print("\n" + "=" * 90)
