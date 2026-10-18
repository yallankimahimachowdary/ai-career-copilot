"""Load learning resources into PostgreSQL from data/learning/learning_resources_seed.json.

Idempotent upsert on unique constraint (skill_name, title, provider):
- Inserts new rows
- Updates url, resource_type, difficulty, est_hours, url_status, url_checked_at, is_active, updated_at on conflict
- Reports counts inserted/updated and total in database
"""

import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text
from app.db.session import AsyncSessionLocal
from app.models.learning_resource import LearningResource

SEED_PATH = Path("data/learning/learning_resources_seed.json")


async def load_learning_resources():
    print(f"Reading learning resources seed from {SEED_PATH}...")
    with open(SEED_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    resources = data.get("resources", [])
    print(f"Loaded {len(resources)} resources from seed.")

    upsert_sql = text("""
        INSERT INTO learning_resources (
            id, skill_name, title, url, provider, resource_type,
            difficulty, est_hours, source, url_status, url_checked_at,
            is_active, created_at
        ) VALUES (
            :id, :skill_name, :title, :url, :provider, :resource_type,
            :difficulty, :est_hours, :source, :url_status, :url_checked_at,
            :is_active, :created_at
        )
        ON CONFLICT (skill_name, title, provider) DO UPDATE SET
            url = EXCLUDED.url,
            resource_type = EXCLUDED.resource_type,
            difficulty = EXCLUDED.difficulty,
            est_hours = EXCLUDED.est_hours,
            source = EXCLUDED.source,
            url_status = EXCLUDED.url_status,
            url_checked_at = EXCLUDED.url_checked_at,
            is_active = EXCLUDED.is_active
    """)

    now = datetime.now(timezone.utc)
    inserted_or_updated = 0

    async with AsyncSessionLocal() as session:
        for r in resources:
            checked_at_val = None
            if r.get("url_checked_at"):
                try:
                    checked_at_val = datetime.fromisoformat(r["url_checked_at"])
                except Exception:
                    checked_at_val = now

            params = {
                "id": uuid.uuid4(),
                "skill_name": r["skill_name"],
                "title": r["title"],
                "url": r.get("url"),
                "provider": r["provider"],
                "resource_type": r.get("resource_type", "official_docs"),
                "difficulty": r.get("difficulty", "all_levels"),
                "est_hours": float(r.get("est_hours", 10.0)),
                "source": r.get("source", "curated_seed"),
                "url_status": r.get("url_status"),
                "url_checked_at": checked_at_val,
                "is_active": bool(r.get("is_active", True)),
                "created_at": now,
            }
            await session.execute(upsert_sql, params)
            inserted_or_updated += 1

        await session.commit()

        # Check total count
        count_res = await session.execute(text("SELECT count(*) FROM learning_resources"))
        total_count = count_res.scalar()

        active_res = await session.execute(
            text("SELECT count(*) FROM learning_resources WHERE is_active = true")
        )
        active_count = active_res.scalar()

    print("\n--- LEARNING RESOURCES LOAD SUMMARY ---")
    print(f"  Processed from seed: {inserted_or_updated}")
    print(f"  Total in database  : {total_count}")
    print(f"  Active resources   : {active_count}")
    print(f"  Inactive resources : {total_count - active_count}")


if __name__ == "__main__":
    asyncio.run(load_learning_resources())
