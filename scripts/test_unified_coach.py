import asyncio
import httpx
import time
import json
import sys
sys.path.insert(0, ".")

from app.db.session import AsyncSessionLocal
from app.models.resume import Resume
from app.models.job_posting import JobPosting
from app.services.coach_service import _extract_resume_skills, _extract_job_requirements

async def test_unified():
    async with AsyncSessionLocal() as db:
        resume = await db.get(Resume, "3386e2b7-fced-4fdd-8276-19baddeeef2c")
        job = await db.get(JobPosting, "1fbc3edb-cc18-4d55-a89a-f7ab137f8963")
    
    r_skills = _extract_resume_skills(resume)
    j_reqs = _extract_job_requirements(job)
    
    prompt = (
        "You are an expert career coach. Analyze the candidate against the job requirements and generate a complete JSON coaching session.\n"
        f"CANDIDATE: Name: {resume.candidate_name}, Skills: {', '.join(r_skills[:15])}\n"
        f"JOB: Title: {job.title} @ {job.company_name}, Requirements: {', '.join(j_reqs['must_have'][:10])}\n\n"
        "Return ONLY valid JSON matching this structure:\n"
        "{\n"
        '  "overall_readiness_score": 65.0,\n'
        '  "confirmed_strengths": ["PCR", "Microbiology"],\n'
        '  "critical_gaps": [{"skill": "Fermentation", "category": "Technical", "importance": "high", "candidate_has": false, "recommendation": "Study fermentation"}],\n'
        '  "growth_gaps": [],\n'
        '  "executive_summary": "2-sentence summary.",\n'
        '  "learning_roadmap": ["Step 1", "Step 2"],\n'
        '  "technical_questions": [{"id": "TQ-001", "category": "technical", "difficulty": "junior", "target_skill": "PCR", "question": "Question text", "why_asked": "Reason", "sample_answer": "Sample", "evaluation_criteria": ["Correct"]}],\n'
        '  "behavioral_questions": [{"id": "BQ-001", "category": "behavioral", "difficulty": "junior", "target_skill": "Teamwork", "question": "Question text", "why_asked": "Reason", "sample_answer": "STAR sample", "evaluation_criteria": ["STAR"]}],\n'
        '  "gap_questions": [{"id": "GQ-001", "category": "gap_probing", "difficulty": "junior", "target_skill": "Fermentation", "question": "Question text", "why_asked": "Reason", "sample_answer": "Sample", "evaluation_criteria": ["Plan"]}],\n'
        '  "preparation_tips": ["Tip 1", "Tip 2"]\n'
        "}"
    )

    start = time.time()
    payload = {
        "model": "llama3.2:3b",
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.0, "num_predict": 550}
    }
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post("http://localhost:11434/api/generate", json=payload)
        resp.raise_for_status()
        data = resp.json()
        elapsed = time.time() - start
        parsed = json.loads(data["response"])
        print(f"COMPLETED IN {elapsed:.2f}s!")
        print("Score:", parsed.get("overall_readiness_score"))
        print("Strengths:", parsed.get("confirmed_strengths"))
        t_q = len(parsed.get("technical_questions", []))
        b_q = len(parsed.get("behavioral_questions", []))
        g_q = len(parsed.get("gap_questions", []))
        print(f"Questions: {t_q} technical, {b_q} behavioral, {g_q} gap")

if __name__ == "__main__":
    asyncio.run(test_unified())
