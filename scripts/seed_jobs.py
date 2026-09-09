import asyncio
import argparse
import os
import zipfile
import pandas as pd
from tqdm.asyncio import tqdm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
import urllib.request
import json

from app.core.config import settings
from app.core.logging import logger
from app.db.session import AsyncSessionLocal
from app.models.job_posting import JobPosting
from app.services.embedding_service import embedding_service

DATA_DIR = os.path.join("data", "kaggle")
POSTINGS_CSV = os.path.join(DATA_DIR, "postings.csv")
SKILLS_CSV = os.path.join(DATA_DIR, "jobs", "job_skills.csv")


async def process_batch(session: AsyncSession, batch: list[dict], skip_embeddings: bool):
    """Process and insert a batch of job postings."""
    records = []
    
    for row in batch:
        # Construct raw job posting without embedding first
        title = str(row.get('title', '')).strip()
        description = str(row.get('description', '')).strip()
        if not title or not description or title == 'nan' or description == 'nan':
            continue

        skills = row.get('skills', [])
        company_name = str(row.get('company_name', '')).strip() if pd.notna(row.get('company_name')) else None
        location = str(row.get('location', '')).strip() if pd.notna(row.get('location')) else None
        
        embed_vector = None
        if not skip_embeddings:
            embed_text = embedding_service.construct_job_embed_text(
                title=title,
                description=description,
                skills=skills,
                company=company_name,
                location=location
            )
            embed_vector = await embedding_service.get_embedding(embed_text)

        # Convert to DB dict
        record = {
            "external_id": str(row['job_id']),
            "title": title,
            "company_name": company_name,
            "description": description,
            "location": location,
            "work_type": str(row.get('formatted_work_type', '')) if pd.notna(row.get('formatted_work_type')) else None,
            "remote_allowed": bool(row.get('remote_allowed', False) == 1.0),
            "skills": skills,
            "min_salary": float(row['min_salary']) if pd.notna(row.get('min_salary')) else None,
            "max_salary": float(row['max_salary']) if pd.notna(row.get('max_salary')) else None,
            "med_salary": float(row['med_salary']) if pd.notna(row.get('med_salary')) else None,
            "pay_period": str(row.get('pay_period', '')) if pd.notna(row.get('pay_period')) else None,
            "source": "kaggle_linkedin",
            "embedding": embed_vector
        }
        records.append(record)

    if not records:
        return

    # Upsert to prevent duplicate issues on re-runs
    stmt = insert(JobPosting).values(records)
    stmt = stmt.on_conflict_do_nothing(index_elements=['external_id'])
    
    try:
        await session.execute(stmt)
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(f"Batch insert failed: {e}")


async def seed_jobs(limit: int = 1000, batch_size: int = 100, skip_embeddings: bool = False):
    """Seed job postings from Kaggle CSVs."""
    if not os.path.exists(POSTINGS_CSV):
        logger.error(f"Dataset not found at {POSTINGS_CSV}.")
        logger.error("Please download the LinkedIn Job Postings (2023-2024) dataset from Kaggle,")
        logger.error("extract it, and ensure 'postings.csv' and 'jobs/job_skills.csv' are in the 'data/kaggle' directory.")
        return

    logger.info("Loading job postings...")
    # Load postings
    df_postings = pd.read_csv(POSTINGS_CSV, nrows=limit if limit > 0 else None)
    
    logger.info(f"Loaded {len(df_postings)} postings.")

    # Load and map skills if available
    skills_map = {}
    if os.path.exists(SKILLS_CSV):
        logger.info("Loading job skills...")
        # Since skills can be huge, we only load skills for the job_ids we have
        job_ids = df_postings['job_id'].unique()
        # Read in chunks to avoid memory issues with huge skill file
        chunksize = 100000
        for chunk in pd.read_csv(SKILLS_CSV, chunksize=chunksize):
            # Filter chunk
            chunk = chunk[chunk['job_link'].isin(job_ids)] if 'job_link' in chunk.columns else chunk[chunk['job_id'].isin(job_ids)]
            job_col = 'job_link' if 'job_link' in chunk.columns else 'job_id'
            skill_col = 'job_skills' if 'job_skills' in chunk.columns else 'skill_abr'
            
            for _, row in chunk.iterrows():
                jid = row[job_col]
                if jid not in skills_map:
                    skills_map[jid] = []
                # Handle comma separated strings or direct values
                skill_val = str(row[skill_col])
                if ',' in skill_val:
                    skills_map[jid].extend([s.strip() for s in skill_val.split(',')])
                else:
                    skills_map[jid].append(skill_val.strip())
                    
    # Map skills back to postings
    df_postings['skills'] = df_postings['job_id'].map(lambda x: list(set(skills_map.get(x, []))))

    # Prepare for batch insertion
    records = df_postings.to_dict('records')
    batches = [records[i:i + batch_size] for i in range(0, len(records), batch_size)]

    logger.info(f"Starting insertion of {len(records)} jobs in {len(batches)} batches...")
    
    async with AsyncSessionLocal() as session:
        for batch in tqdm(batches, desc="Inserting jobs"):
            await process_batch(session, batch, skip_embeddings)
            
    logger.info("Seeding complete.")

def main():
    parser = argparse.ArgumentParser(description="Seed Job Postings from Kaggle Dataset")
    parser.add_argument("--limit", type=int, default=1000, help="Number of rows to load (0 for all)")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for inserts")
    parser.add_argument("--skip-embeddings", action="store_true", help="Skip generating vector embeddings")
    args = parser.parse_args()

    asyncio.run(seed_jobs(limit=args.limit, batch_size=args.batch_size, skip_embeddings=args.skip_embeddings))

if __name__ == "__main__":
    main()
