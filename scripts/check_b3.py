"""B3 Checkpoint Evaluation Script."""

import glob
import pypdf
def format_table(headers, rows):
    col_widths = [max(len(str(h)), max(len(str(r[i])) for r in rows)) for i, h in enumerate(headers)]
    header_line = "| " + " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers)) + " |"
    separator_line = "| " + " | ".join("-" * col_widths[i] for i in range(len(headers))) + " |"
    data_lines = ["| " + " | ".join(str(r[i]).ljust(col_widths[i]) for i in range(len(headers))) + " |" for r in rows]
    return "\n".join([header_line, separator_line] + data_lines)
from app.services.parser_agent import parser_agent
from app.services.anonymizer import anonymize_resume
from scripts.job_snapshot import load_snapshot
from app.ranking.baselines import BM25Ranker, SbertRanker, SkillOverlapRanker
from app.ranking.hybrid import HybridRanker, CompositeXGBRanker

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

job_map = {str(j.get('id') or j.get('external_id')): (j.get('title') or 'Unknown')[:28] for j in sample_jobs}

bm25 = BM25Ranker()
sbert = SbertRanker()
overlap = SkillOverlapRanker()
hybrid = HybridRanker(bm25_ranker=bm25, sbert_ranker=sbert, overlap_ranker=overlap)
composite_xgb = CompositeXGBRanker()

for name, res in [('Mahi', mahi_res), ('Deepika', deepika_res)]:
    print(f"\n================ Top 5 Comparison for {name} ================")
    r_bm25 = bm25.rank(res, sample_jobs, k=5)
    r_sbert = sbert.rank(res, sample_jobs, k=5)
    r_ov = overlap.rank(res, sample_jobs, k=5)
    r_hy = hybrid.rank(res, sample_jobs, k=5)
    r_xgb = composite_xgb.rank(res, sample_jobs, k=5)

    rows = []
    for rank in range(5):
        id_bm = r_bm25.ranked_job_ids[rank]
        id_sb = r_sbert.ranked_job_ids[rank]
        id_ov = r_ov.ranked_job_ids[rank]
        id_hy = r_hy.ranked_job_ids[rank]
        id_xg = r_xgb.ranked_job_ids[rank]

        rows.append([
            f"#{rank+1}",
            f"{job_map.get(id_bm, 'Unknown')} ({r_bm25.scores.get(id_bm, 0):.2f})",
            f"{job_map.get(id_sb, 'Unknown')} ({r_sbert.scores.get(id_sb, 0):.2f})",
            f"{job_map.get(id_ov, 'Unknown')} ({r_ov.scores.get(id_ov, 0):.2f})",
            f"{job_map.get(id_hy, 'Unknown')} ({r_hy.scores.get(id_hy, 0):.2f})",
            f"{job_map.get(id_xg, 'Unknown')} ({r_xgb.scores.get(id_xg, 0):.2f})",
        ])
    
    headers = ['Rank', 'BM25', 'SBERT', 'Skill Overlap', 'Hybrid (Fixed)', 'Composite XGB']
    print(format_table(headers, rows))

print('\nB3 CHECKPOINT COMPLETED SUCCESSFULLY!')
