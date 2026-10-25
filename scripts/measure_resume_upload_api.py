import asyncio
import io
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import httpx
from httpx import ASGITransport
from app.main import app
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.api.deps import get_current_user

async def get_or_create_test_user():
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        res = await session.execute(select(User).where(User.email == "fast_upload_test@example.com"))
        user = res.scalar_one_or_none()
        if not user:
            user = User(
                id="fast-upload-test-user-id",
                email="fast_upload_test@example.com",
                full_name="Fast Upload Test User",
                hashed_password="mockhashedpassword123",
                is_active=True,
                is_superuser=False,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        return user

async def main():
    test_user = await get_or_create_test_user()
    app.dependency_overrides[get_current_user] = lambda: test_user

    # Load 3 synthetic resumes from results/dryrun/intake_candidates.json
    intake_path = Path("results/dryrun/intake_candidates.json")
    if intake_path.exists():
        with open(intake_path, "r", encoding="utf-8") as f:
            candidates = json.load(f)[:3]
    else:
        candidates = [
            {"candidate_id": "SYN_001", "anonymized_text": "Alex Smith\nSoftware Engineer with Python, Docker, SQL, FastAPI expertise."},
            {"candidate_id": "SYN_002", "anonymized_text": "Jordan Lee\nMachine Learning Engineer with PyTorch, TensorFlow, Python, Pandas."},
            {"candidate_id": "SYN_003", "anonymized_text": "Taylor Kim\nCloud Architect with AWS, Kubernetes, Terraform, Linux skills."},
        ]

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=60.0) as client:
        print("=== MEASURING RESUME UPLOAD API (DEFAULT: RULE-BASED PARSER) ===")
        print(f"Active PARSER_MODE setting: {settings.PARSER_MODE}")
        
        for cand in candidates:
            cid = cand.get("candidate_id", "SYN_TEST")
            text = cand.get("anonymized_text", "Experienced developer with Python and Docker.")
            files = {
                "file": (f"{cid}_resume.txt", text.encode("utf-8"), "text/plain")
            }
            
            t0 = time.perf_counter()
            resp = await client.post("/api/v1/resumes/upload", files=files)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            
            status = resp.status_code
            data = resp.json() if status == 201 else {}
            skills = data.get("parsed_data", {}).get("skills", [])
            p_mode = data.get("parsed_data", {}).get("parse_metadata", {}).get("parser_mode", "unknown")
            p_engine = data.get("parsed_data", {}).get("parse_metadata", {}).get("parser_engine", "unknown")
            
            print(f"[{cid}] HTTP {status} | Latency: {elapsed_ms:,.2f} ms | Skills: {len(skills)} | Parser Mode: {p_mode} ({p_engine})")
            if skills:
                print(f"       Extracted skills: {', '.join(skills[:8])}{'...' if len(skills)>8 else ''}")

        # Check Ollama status
        ollama_available = False
        try:
            async with httpx.AsyncClient(timeout=2.0) as o_client:
                o_resp = await o_client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
                if o_resp.status_code == 200:
                    ollama_available = True
        except Exception:
            ollama_available = False

        print(f"\nOllama Local Daemon Status: {'AVAILABLE / IDLE' if ollama_available else 'UNAVAILABLE'}")
        if ollama_available:
            print("=== MEASURING OPT-IN LLM PARSER MODE (PARSER_MODE=llm) ===")
            orig_mode = settings.PARSER_MODE
            settings.PARSER_MODE = "llm"
            try:
                cid = candidates[0].get("candidate_id", "SYN_001")
                text = candidates[0].get("anonymized_text")[:500]
                files = {"file": (f"{cid}_llm_optin.txt", text.encode("utf-8"), "text/plain")}
                
                t0 = time.perf_counter()
                resp = await client.post("/api/v1/resumes/upload", files=files)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                
                status = resp.status_code
                data = resp.json() if status == 201 else {}
                skills = data.get("parsed_data", {}).get("skills", [])
                p_mode = data.get("parsed_data", {}).get("parse_metadata", {}).get("parser_mode", "unknown")
                p_engine = data.get("parsed_data", {}).get("parse_metadata", {}).get("parser_engine", "unknown")
                print(f"[{cid}] HTTP {status} | Latency: {elapsed_ms:,.2f} ms | Skills: {len(skills)} | Parser Mode: {p_mode} ({p_engine})")
            finally:
                settings.PARSER_MODE = orig_mode

    app.dependency_overrides.clear()

if __name__ == "__main__":
    asyncio.run(main())
