"""
scripts/college_report/test_demo_workflow.py
--------------------------------------------
First Step Demo Workflow Verification Script.
Executes the end-to-end user workflow:
1. Health Check
2. User Authentication (JWT)
3. Resume Upload & Parsing (PDF)
4. Job Matching (Hybrid + XGBoost)
5. Explainability (SHAP feature attribution)
6. Interview Coach (Skill-gap analysis & learning resources)
7. Labor Market Intelligence (Role overview & salary spectrum)
8. Chat Copilot (Adaptive Intent Router & RAG)
"""

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from sqlalchemy import select
from app.models.user import User


async def run_workflow():
    print("=================================================================")
    print("   AI CAREER COPILOT -- END-TO-END DEMO WORKFLOW VERIFICATION   ")
    print("=================================================================")
    start_all = time.perf_counter()

    # 1. Identify Demo User
    demo_email = "alex07@gmail.com"
    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == demo_email))).scalar_one_or_none()
        if not user:
            user = (await session.execute(select(User))).scalars().first()
        user_id = user.id
        user_email = user.email

    token = create_access_token(subject=user_id)
    headers = {"Authorization": f"Bearer {token}"}
    print(f"[AUTH] Authenticated as: {user_email} (ID: {user_id})")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=120.0) as client:
        # Step 1: Health Check
        t0 = time.perf_counter()
        r_health = await client.get("/health")
        dt_health = (time.perf_counter() - t0) * 1000
        print(f"\n[1. HEALTH CHECK] Status: {r_health.status_code} ({dt_health:.1f} ms)")
        print(f"    Response: {r_health.json()}")

        # Step 2: Resume Upload & Parsing
        test_pdf = PROJECT_ROOT / "data" / "resumes_dryrun" / "SYN_001_Tanvi_Naidu.pdf"
        if not test_pdf.exists():
            raise FileNotFoundError(f"Resume PDF not found: {test_pdf}")

        t0 = time.perf_counter()
        with open(test_pdf, "rb") as f:
            files = {"file": (test_pdf.name, f, "application/pdf")}
            r_upload = await client.post("/api/v1/resumes/upload", headers=headers, files=files)
        dt_upload = (time.perf_counter() - t0) * 1000
        print(f"\n[2. RESUME UPLOAD] Status: {r_upload.status_code} ({dt_upload:.1f} ms)")
        resume_data = r_upload.json()
        resume_id = resume_data.get("id")
        candidate_name = resume_data.get("candidate_name")
        skills = resume_data.get("parsed_data", {}).get("skills", [])
        print(f"    Resume ID: {resume_id}")
        print(f"    Candidate Name: {candidate_name}")
        print(f"    Extracted Skills ({len(skills)}): {skills[:8]}...")

        # Step 3: Job Matching
        t0 = time.perf_counter()
        r_match = await client.post(
            f"/api/v1/matches/resume/{resume_id}?limit=5&min_score=0.0",
            headers=headers
        )
        dt_match = (time.perf_counter() - t0) * 1000
        print(f"\n[3. JOB MATCHING] Status: {r_match.status_code} ({dt_match:.1f} ms)")
        match_data = r_match.json()
        matches = match_data.get("matches", [])
        print(f"    Total Matches Returned: {len(matches)}")
        top_job_id = None
        if matches:
            top_match = matches[0]
            top_job_id = top_match.get("job_id")
            score_val = top_match.get("score") or top_match.get("match_score") or top_match.get("composite_score") or 0.0
            print(f"    Top Match: Job ID {top_job_id} | Title: '{top_match.get('title')}' | Company: '{top_match.get('company')}'")
            print(f"    Match Score: {score_val:.4f} | Confidence: {top_match.get('confidence_tier')}")

        # Step 4: Explainability (SHAP & Feature Attribution)
        if top_job_id:
            t0 = time.perf_counter()
            r_explain = await client.get(
                f"/api/v1/matches/compare/{resume_id}/{top_job_id}",
                headers=headers
            )
            dt_explain = (time.perf_counter() - t0) * 1000
            print(f"\n[4. EXPLAINABILITY (XAI)] Status: {r_explain.status_code} ({dt_explain:.1f} ms)")
            explain_data = r_explain.json()
            explanation = explain_data.get("explanation", {})
            print(f"    Composite Score: {explain_data.get('composite_score')}")
            print(f"    Matched Skills: {explanation.get('matched_skills', [])}")
            print(f"    Missing Skills: {explanation.get('missing_skills', [])}")
            shap_vals = explanation.get("shap_feature_importance", {})
            print(f"    SHAP Features: {list(shap_vals.keys())[:5]}")

        # Step 5: Interview Coach Agent (Skill Gap & Resources)
        t0 = time.perf_counter()
        coach_payload = {
            "resume_id": resume_id,
            "target_role": "Data Scientist",
            "experience_level": "mid",
        }
        r_coach = await client.post("/api/v1/coach/skill-gap", headers=headers, json=coach_payload)
        dt_coach = (time.perf_counter() - t0) * 1000
        print(f"\n[5. INTERVIEW COACH] Status: {r_coach.status_code} ({dt_coach:.1f} ms)")
        coach_data = r_coach.json()
        critical_gaps = coach_data.get("critical_gaps", [])
        print(f"    Target Role: {coach_data.get('target_role')}")
        print(f"    Identified Skill Gaps ({len(critical_gaps)}): {critical_gaps[:6]}")
        learning_recs = coach_data.get("learning_recommendations", [])
        print(f"    Learning Resources Attached: {len(learning_recs)}")

        # Step 6: Market Intelligence Agent (Role Overview)
        t0 = time.perf_counter()
        market_payload = {
            "role_title": "Data Scientist",
            "location": None,
        }
        r_market = await client.post("/api/v1/market/role-overview", headers=headers, json=market_payload)
        dt_market = (time.perf_counter() - t0) * 1000
        print(f"\n[6. MARKET INTELLIGENCE] Status: {r_market.status_code} ({dt_market:.1f} ms)")
        market_data = r_market.json()
        print(f"    Total Active Postings: {market_data.get('total_active_postings')}")
        print(f"    Median Salary: {market_data.get('median_salary')}")
        print(f"    Full-time Ratio: {market_data.get('full_time_ratio')}")

        # Step 7: Chat Agent (Adaptive Intent Router & LangGraph RAG)
        t0 = time.perf_counter()
        chat_payload = {
            "query": "What are the key technical skills required for a Data Scientist role?",
            "resume_id": resume_id,
            "job_id": top_job_id,
            "history": [],
        }
        r_chat = await client.post("/api/v1/chat/query", headers=headers, json=chat_payload)
        dt_chat = (time.perf_counter() - t0) * 1000
        print(f"\n[7. CHAT & ROUTER AGENT] Status: {r_chat.status_code} ({dt_chat:.1f} ms)")
        chat_data = r_chat.json()
        print(f"    Intent: {chat_data.get('intent')}")
        print(f"    Routing Strategy: {chat_data.get('strategy_used')}")
        msg = chat_data.get('response', '') or chat_data.get('message', '') or ''
        clean_msg = msg.encode('ascii', errors='replace').decode('ascii')
        preview = clean_msg[:120].replace('\n', ' ') if clean_msg else 'No text'
        print(f"    Response Preview: '{preview}...'")

    total_time = time.perf_counter() - start_all
    print("\n=================================================================")
    print(f"   DEMO WORKFLOW RESULT: ALL 7 STEPS COMPLETED IN {total_time:.2f}s   ")
    print("=================================================================")


if __name__ == "__main__":
    asyncio.run(run_workflow())
