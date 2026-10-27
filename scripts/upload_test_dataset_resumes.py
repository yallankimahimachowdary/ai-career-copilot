import asyncio
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
        res = await session.execute(select(User).where(User.email == "r15d_upload_user@example.com"))
        user = res.scalar_one_or_none()
        if not user:
            user = User(
                id="r15d-test-upload-user-id",
                email="r15d_upload_user@example.com",
                full_name="R15d Upload Test User",
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

    target_resumes = [
        "data/resumes_dryrun/SYN_001_Tanvi_Naidu.pdf",
        "data/resumes_dryrun/SYN_040_Divya_Gowda.pdf",
        "data/resumes_dryrun/SYN_080_Arjun_Bose.pdf",
    ]

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=60.0) as client:
        print("=== UPLOAD API TEST ON 3 DATASET RESUMES (DEFAULT MODE) ===")
        print(f"PARSER_MODE in config: {settings.PARSER_MODE}")
        print("-" * 75)

        for rel_path in target_resumes:
            pdf_path = Path(rel_path)
            if not pdf_path.exists():
                print(f"[ERROR] File not found: {rel_path}")
                continue

            raw_bytes = pdf_path.read_bytes()
            files = {
                "file": (pdf_path.name, raw_bytes, "application/pdf")
            }

            t0 = time.perf_counter()
            resp = await client.post("/api/v1/resumes/upload", files=files)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            status = resp.status_code
            data = resp.json() if status == 201 else {}
            parsed_data = data.get("parsed_data", {})
            name_token = parsed_data.get("candidate_name") or "n/a"
            skills = parsed_data.get("skills", [])
            parse_meta = parsed_data.get("parse_metadata", {})
            stored_mode = parse_meta.get("parser_mode", "unknown")
            stored_engine = parse_meta.get("parser_engine", "unknown")

            print(f"Resume: {pdf_path.name}")
            print(f"  HTTP Status:         {status}")
            print(f"  Wall-Clock:          {elapsed_ms:,.2f} ms")
            print(f"  Extracted Name:      {name_token}")
            print(f"  Skills Count:        {len(skills)}")
            print(f"  Stored Parser Mode:  {stored_mode} (engine: {stored_engine})")
            print(f"  Extracted Skills:    {skills}")
            print("-" * 75)

    app.dependency_overrides.clear()

if __name__ == "__main__":
    asyncio.run(main())
