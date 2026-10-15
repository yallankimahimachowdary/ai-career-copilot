import glob, pypdf
from app.services.parser_agent import parser_agent
from app.services.anonymizer import anonymize_resume
from scripts.job_snapshot import load_snapshot
from app.services.matcher_service import matcher_agent

records, meta = load_snapshot('data/snapshots/test_snap_1.json')

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
        'education': [e.model_dump() for e in parsed.education],
        'experience': [e.model_dump() for e in parsed.experience],
    }

mahi_res = prepare_resume('uploads/resumes/*Mahima*', 'Mahima')
deepika_res = prepare_resume('uploads/resumes/*Deepika*', 'Deepika')

def simulate_prod_retrieval(resume, job_pool, limit=10):
    candidate_skills = resume.get('skills', [])
    edu_texts = [f"{e.get('degree', '')} {e.get('field_of_study', '')}".lower() for e in resume.get('education', [])]
    summary_text = (resume.get('summary') or '').lower()
    skills_lower = {s.lower() for s in candidate_skills}

    is_biotech = (
        any(any(k in t for k in ['bio', 'pharma', 'clinical', 'molecular', 'genetic', 'microbio']) for t in edu_texts)
        or any(k in summary_text for k in ['biotech', 'biology', 'pharmaceutical', 'clinical', 'microbiology'])
        or any(k in skills_lower for k in ['pcr', 'molecular biology', 'microbiology', 'cell culture', 'bioinformatics', 'crispr', 'elisa', 'formulation'])
    )

    print(f"Candidate: {resume['candidate_name']} | is_biotech: {is_biotech}")
    
    # In production vector_stmt + keyword retrieval:
    # If is_biotech: title filters match bio, pharma, clinic, medic, scien, chem, lab, research OR direct keywords
    filtered_pool = []
    for j in job_pool:
        title = (j.get('title') or '').lower()
        if is_biotech:
            biotech_kws = ['bio', 'pharma', 'clinic', 'medic', 'scien', 'chem', 'lab', 'research', 'biotechnol', 'bioinform', 'biomedic', 'microbiol']
            if any(k in title for k in biotech_kws):
                filtered_pool.append(j)
        else:
            # Mahi: general
            filtered_pool.append(j)
            
    print(f"Filtered candidate pool count: {len(filtered_pool)} (from {len(job_pool)})")
    
    # Score candidates using matcher_agent.score_job
    scored = []
    for j in filtered_pool:
        skills = j.get('skills', [])
        f_score, comp_score, xgb_score, features, sb, expl = matcher_agent.score_job(
            parsed_resume=resume,
            job_title=j.get('title', ''),
            job_description=j.get('description', ''),
            job_skills=skills,
            semantic_distance=0.40,
        )
        scored.append((f_score, comp_score, j.get('id') or j.get('external_id'), j.get('title'), j.get('company_name'), len(sb.matched_skills), sb.matched_skills))
        
    scored.sort(key=lambda x: (x[0], x[1], str(x[2])), reverse=True)
    return scored[:limit]

for name, res in [('Mahi', mahi_res), ('Deepika', deepika_res)]:
    print(f"\n=== Production Simulation for {name} ===")
    top = simulate_prod_retrieval(res, records, limit=10)
    for rank, (fs, cs, jid, title, comp, n_m, m_skills) in enumerate(top, 1):
        print(f"{rank}. [{fs:.4f}] {title} @ {comp} (ID: {jid}) | Matched ({n_m}): {m_skills}")
