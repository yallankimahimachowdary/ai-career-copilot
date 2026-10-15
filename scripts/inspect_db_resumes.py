import asyncio
from app.db.session import AsyncSessionLocal
from app.models.resume import Resume
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Resume))
        resumes = res.scalars().all()
        for r in resumes:
            print("ID:", r.id, "| Name:", r.candidate_name)
            pd = r.parsed_data or {}
            print("  Skills count:", len(pd.get("skills", [])))
            print("  Skills:", pd.get("skills", []))
            print("  Education:", pd.get("education", []))
            print("  Summary:", (pd.get("summary") or "")[:120])

if __name__ == "__main__":
    asyncio.run(check())
