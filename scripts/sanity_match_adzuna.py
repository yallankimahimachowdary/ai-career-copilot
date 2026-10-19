"""scripts/sanity_match_adzuna.py
------------------------------
Sanity test matching a synthetic candidate against the frozen Adzuna snapshot_1.
"""

import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.matcher_service import MatcherAgent
from app.services.embedding_service import embedding_service
import numpy as np

async def main():
    matcher = MatcherAgent()
    with open("data/fairness/synthetic_resumes_v1.jsonl", "r", encoding="utf-8") as f:
        resumes = [json.loads(line) for line in f]
    swe_resume = resumes[0]  # syn_swe_01: Junior Backend Software Engineer
    print(f"Testing Candidate: {swe_resume['id']} ({swe_resume['summary']})")

    with open("data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl", "r", encoding="utf-8") as f:
        jobs = [json.loads(line) for line in f]
    print(f"Total Adzuna snapshot jobs evaluated: {len(jobs)}")

    t0 = time.time()
    scored_jobs = []
    for job in jobs:
        desc = job.get("description", "")
        title = job.get("title", "")
        skills = job.get("skills", [])
        final_score, comp_score, xgb_score, feats, s_breakdown, expls = matcher.score_job(
            parsed_resume=swe_resume,
            job_title=title,
            job_description=desc,
            job_skills=skills,
            semantic_distance=0.30,
        )
        scored_jobs.append({
            "title": title,
            "company": job.get("company_name"),
            "location": job.get("location"),
            "final_score": final_score,
            "comp_score": comp_score,
            "xgb_score": xgb_score,
            "matched_skills": s_breakdown.matched_skills,
        })

    elapsed_ms = (time.time() - t0) * 1000
    scored_jobs.sort(key=lambda x: x["final_score"], reverse=True)

    print(f"\nScoring Latency: {elapsed_ms:.1f}ms total ({elapsed_ms/len(jobs):.2f}ms per job)")
    print("\n--- TOP 5 MATCHED JOBS ---")
    for idx, j in enumerate(scored_jobs[:5], 1):
        print(f"{idx}. [{j['final_score']*100:.1f}%] {j['title']} @ {j['company']} ({j['location']})")
        print(f"   Matched Skills: {j['matched_skills']}")
        print(f"   Subscores: Composite={j['comp_score']*100:.1f}%, XGBoost={j['xgb_score']*100:.1f}%")

if __name__ == "__main__":
    asyncio.run(main())
