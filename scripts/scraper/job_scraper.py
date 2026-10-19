"""
scripts/scraper/job_scraper.py
------------------------------
Real-time Job Scraper & Daily Batch Scheduler for AI Career Copilot.

Scrapes live job postings from LinkedIn, Indeed, and Glassdoor, normalizes fields
to match the JobPosting PostgreSQL schema, extracts canonical skills using the domain taxonomy,
generates dense vector embeddings, deduplicates records, and stores them in PostgreSQL.

Includes an automated daily batch scheduler powered by APScheduler.
"""

import argparse
import asyncio
import hashlib
import logging
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.core.config import settings
from app.core.logging import logger
from app.core.taxonomy import extract_canonical_skills, filter_category_codes
from app.db.session import AsyncSessionLocal
from app.models.job_posting import JobPosting
from app.services.embedding_service import embedding_service

try:
    from jobspy import scrape_jobs
except ImportError:
    logger.error("python-jobspy is not installed. Run 'pip install python-jobspy'.")
    scrape_jobs = None

try:
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
except ImportError:
    BlockingScheduler = None

# ---------------------------------------------------------------------------
# Default Query Configuration
# ---------------------------------------------------------------------------
# Default Query Configuration (Localized to India)
# ---------------------------------------------------------------------------

DEFAULT_SEARCH_TERMS = [
    # Tech & Software
    "Software Engineer",
    "Python Developer",
    "Full Stack Engineer",
    "Backend Engineer",
    "Frontend Developer",
    "Data Scientist",
    "Data Analyst",
    "Machine Learning Engineer",
    "DevOps Engineer",
    "Cloud Engineer",
    # Life Sciences & Healthcare
    "Biotechnology",
    "Bioinformatics",
    "Biomedical Engineer",
    "Clinical Research",
    "Pharmaceutical",
    # Core Engineering
    "Mechanical Engineer",
    "Civil Engineer",
    "Electronics Engineer",
]

DEFAULT_LOCATIONS = [
    "Chennai",
    "Bengaluru",
    "Hyderabad",
    "Pune",
    "Mumbai",
    "Delhi NCR",
    "Remote",
]

DEFAULT_SITES = ["linkedin", "indeed", "glassdoor"]


# ---------------------------------------------------------------------------
# Salary & Text Extraction Helpers (INR & Indian formats)
# ---------------------------------------------------------------------------

# Patterns like "₹8-12 LPA", "8 - 12 LPA", "₹8,00,000 - ₹12,00,000 a year", "50,000/month"
_LPA_REGEX = re.compile(
    r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:-|to)\s*(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?|lac(?:s)?)\b",
    re.IGNORECASE,
)
_SINGLE_LPA_REGEX = re.compile(
    r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?|lac(?:s)?)\b",
    re.IGNORECASE,
)
_INR_MONTHLY_REGEX = re.compile(
    r"(?:₹|rs\.?|inr)\s*([0-9]{1,2}(?:,[0-9]{2,3})+|\d{4,6})\s*(?:-|to)?\s*(?:(?:₹|rs\.?|inr)\s*([0-9]{1,2}(?:,[0-9]{2,3})+|\d{4,6}))?\s*(?:/|\s*per\s*)month",
    re.IGNORECASE,
)
_INR_ANNUAL_REGEX = re.compile(
    r"(?:₹|rs\.?|inr)\s*([0-9]{1,2}(?:,[0-9]{2,3})+|\d{5,8})\s*(?:-|to)\s*(?:₹|rs\.?|inr)\s*([0-9]{1,2}(?:,[0-9]{2,3})+|\d{5,8})",
    re.IGNORECASE,
)


def _clean_str(val: Any) -> Optional[str]:
    """Clean string value or return None if empty/NaN."""
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    return s if s and s.lower() not in ("nan", "none", "null") else None


def _normalize_location_str(loc: Optional[str]) -> Optional[str]:
    """Normalize Indian city variations to standard city representations."""
    if not loc:
        return None
    l_lower = loc.lower().strip()
    if any(k in l_lower for k in ("bengaluru", "bangalore")):
        return "Bengaluru, Karnataka"
    if any(k in l_lower for k in ("chennai", "madras")):
        return "Chennai, Tamil Nadu"
    if any(k in l_lower for k in ("hyderabad", "secunderabad")):
        return "Hyderabad, Telangana"
    if "pune" in l_lower:
        return "Pune, Maharashtra"
    if any(k in l_lower for k in ("mumbai", "bombay", "navi mumbai", "thane")):
        return "Mumbai, Maharashtra"
    if any(k in l_lower for k in ("delhi", "new delhi", "noida", "gurgaon", "gurugram", "ghaziabad", "faridabad")):
        return "Delhi NCR"
    if "remote" in l_lower:
        return "Remote (India)"
    if l_lower in ("mh", "maharashtra"):
        return "Mumbai, Maharashtra"
    if l_lower in ("ka", "karnataka"):
        return "Bengaluru, Karnataka"
    if l_lower in ("ts", "tg", "telangana"):
        return "Hyderabad, Telangana"
    if l_lower in ("tn", "tamil nadu"):
        return "Chennai, Tamil Nadu"
    if l_lower in ("dl", "delhi"):
        return "Delhi NCR"
    # Strip country suffix if redundant
    cleaned = re.sub(r",\s*(?:india|in)$", "", loc, flags=re.IGNORECASE).strip()
    return cleaned or loc


def _parse_salary(row: Dict[str, Any], description: str) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[str]]:
    """
    Extract min, max, median salary and pay period from structured fields or description text.
    All Indian compensation normalized to annual INR.
    """
    min_sal = None
    max_sal = None
    pay_period = None

    raw_min = row.get("min_amount")
    raw_max = row.get("max_amount")
    interval = _clean_str(row.get("interval"))

    if raw_min is not None and not pd.isna(raw_min):
        try:
            min_sal = float(raw_min)
        except (ValueError, TypeError):
            pass

    if raw_max is not None and not pd.isna(raw_max):
        try:
            max_sal = float(raw_max)
        except (ValueError, TypeError):
            pass

    if interval:
        interval_upper = interval.upper()
        if interval_upper in ("YEAR", "ANNUALLY", "YEARLY"):
            pay_period = "YEARLY"
        elif interval_upper in ("MONTH", "MONTHLY"):
            pay_period = "MONTHLY"
            # Annualize monthly INR
            if min_sal is not None:
                min_sal = min_sal * 12.0
            if max_sal is not None:
                max_sal = max_sal * 12.0
            pay_period = "YEARLY"
        elif interval_upper in ("HOUR", "HOURLY"):
            pay_period = "HOURLY"
            if min_sal is not None:
                min_sal = min_sal * 2000.0
            if max_sal is not None:
                max_sal = max_sal * 2000.0
            pay_period = "YEARLY"

    # Fallback 1: LPA Regex in description (e.g. "8-12 LPA", "₹10 LPA")
    if min_sal is None and max_sal is None and description:
        lpa_match = _LPA_REGEX.search(description)
        if lpa_match:
            try:
                min_sal = float(lpa_match.group(1)) * 100_000.0
                max_sal = float(lpa_match.group(2)) * 100_000.0
                pay_period = "YEARLY"
            except Exception:
                pass
        else:
            single_lpa = _SINGLE_LPA_REGEX.search(description)
            if single_lpa:
                try:
                    val = float(single_lpa.group(1)) * 100_000.0
                    min_sal = val
                    max_sal = val
                    pay_period = "YEARLY"
                except Exception:
                    pass

    # Fallback 2: Monthly regex (e.g. "₹40,000 - ₹60,000 / month")
    if min_sal is None and max_sal is None and description:
        m_match = _INR_MONTHLY_REGEX.search(description)
        if m_match:
            try:
                def _parse_num(s: str) -> float:
                    return float(s.replace(",", "").strip())
                m_min = _parse_num(m_match.group(1)) * 12.0
                min_sal = m_min
                if m_match.group(2):
                    max_sal = _parse_num(m_match.group(2)) * 12.0
                else:
                    max_sal = m_min
                pay_period = "YEARLY"
            except Exception:
                pass

    # Fallback 3: Annual INR regex (e.g. "₹6,00,000 - ₹12,00,000")
    if min_sal is None and max_sal is None and description:
        a_match = _INR_ANNUAL_REGEX.search(description)
        if a_match:
            try:
                min_sal = float(a_match.group(1).replace(",", "").strip())
                max_sal = float(a_match.group(2).replace(",", "").strip())
                pay_period = "YEARLY"
            except Exception:
                pass

    # Sanity checks on salary values
    if min_sal and max_sal and min_sal > max_sal:
        min_sal, max_sal = max_sal, min_sal

    med_sal = None
    if min_sal is not None and max_sal is not None:
        med_sal = round((min_sal + max_sal) / 2.0, 2)
    elif min_sal is not None:
        med_sal = round(min_sal, 2)
    elif max_sal is not None:
        med_sal = round(max_sal, 2)

    return min_sal, max_sal, med_sal, pay_period


def _normalize_work_type(raw_type: Optional[str]) -> Optional[str]:
    """Standardize employment type string."""
    if not raw_type:
        return None
    t = raw_type.lower()
    if "full" in t:
        return "Full-time"
    if "part" in t:
        return "Part-time"
    if "contract" in t or "temp" in t:
        return "Contract"
    if "intern" in t:
        return "Internship"
    return raw_type.strip().title()


def _is_remote(row: Dict[str, Any], title: str, location: Optional[str], description: str) -> bool:
    """Determine whether the job allows remote work."""
    if bool(row.get("is_remote")):
        return True
    combined = f"{title} {location or ''} {description[:500]}".lower()
    if any(k in combined for k in ("remote", "work from home", "wfh", "telecommute", "virtual")):
        return True
    return False


def _build_external_id(site: str, row_id: Any, job_url: Optional[str], title: str, company: Optional[str]) -> str:
    """Construct a persistent unique identifier for deduplication."""
    clean_id = _clean_str(row_id)
    if clean_id:
        return f"{site}_{clean_id}"
    if job_url:
        clean_url = job_url.split("?")[0].strip()
        h = hashlib.sha256(clean_url.encode("utf-8")).hexdigest()[:16]
        return f"{site}_{h}"
    composite = f"{site}_{title}_{company or ''}".lower()
    h = hashlib.sha256(composite.encode("utf-8")).hexdigest()[:16]
    return f"{site}_{h}"


# ---------------------------------------------------------------------------
# JobScraper Pipeline Class
# ---------------------------------------------------------------------------

class JobScraperPipeline:
    """Orchestrates scraping, normalization, deduplication, and database persistence."""

    def __init__(
        self,
        search_terms: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        sites: Optional[List[str]] = None,
        results_per_query: int = 10,
        skip_embeddings: bool = False,
    ):
        self.search_terms = search_terms or DEFAULT_SEARCH_TERMS
        self.locations = locations or DEFAULT_LOCATIONS
        self.sites = sites or DEFAULT_SITES
        self.results_per_query = results_per_query
        self.skip_embeddings = skip_embeddings

    def scrape_platform(
        self,
        site: str,
        search_term: str,
        location: str,
    ) -> List[Dict[str, Any]]:
        """Scrape jobs for a single site and keyword with robust error isolation."""
        if not scrape_jobs:
            logger.error("JobSpy is not available.")
            return []

        try:
            logger.info(
                "Scraping %s for '%s' in '%s' (wanted: %d)...",
                site.upper(), search_term, location, self.results_per_query
            )
            df = scrape_jobs(
                site_name=[site],
                search_term=search_term,
                location=location,
                results_wanted=self.results_per_query,
                country_indeed="india",
                fetch_description=True,
                verbose=0,
            )
            if df is not None and not df.empty:
                logger.info("-> Fetched %d raw listings from %s.", len(df), site)
                return df.to_dict("records")
            logger.info("-> No listings returned from %s.", site)
        except Exception as exc:
            logger.warning(
                "Scraping failed for %s (term: '%s', loc: '%s'): %s. Skipping without crash.",
                site, search_term, location, exc
            )
        return []

    async def normalize_and_filter(
        self,
        raw_jobs: List[Dict[str, Any]],
        existing_keys: Set[str],
        query_loc: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Normalize raw scraped records and deduplicate against existing keys."""
        normalized_records = []

        for row in raw_jobs:
            try:
                title = _clean_str(row.get("title"))
                if not title:
                    continue

                site = _clean_str(row.get("site")) or "scraped"
                company = _clean_str(row.get("company"))
                raw_loc = _clean_str(row.get("location"))
                if not raw_loc or len(raw_loc.strip()) <= 3:
                    raw_loc = query_loc or raw_loc
                location = _normalize_location_str(raw_loc)
                job_url = _clean_str(row.get("job_url"))
                row_id = row.get("id")

                description = _clean_str(row.get("description")) or f"Position for {title} at {company or 'Undisclosed'}."

                # Composite key check (in-memory deduplication)
                comp_key = f"{title.lower()}||{(company or '').lower()}||{(location or '').lower()}"
                external_id = _build_external_id(site, row_id, job_url, title, company)

                if external_id in existing_keys or comp_key in existing_keys:
                    continue

                existing_keys.add(external_id)
                existing_keys.add(comp_key)

                # Remote & Work Type
                remote_allowed = _is_remote(row, title, location, description)
                work_type = _normalize_work_type(_clean_str(row.get("job_type")))

                # Skills Extraction via Domain Taxonomy
                skills_text = f"{title} {description}"
                canonical_skills = extract_canonical_skills(skills_text)
                if row.get("skills") and isinstance(row["skills"], list):
                    extra = filter_category_codes([str(s) for s in row["skills"]])
                    for s in extra:
                        if s not in canonical_skills:
                            canonical_skills.append(s)

                # Salary Normalization
                min_sal, max_sal, med_sal, pay_period = _parse_salary(row, description)

                # Semantic Embedding
                embed_vector = None
                if not self.skip_embeddings:
                    try:
                        embed_text = embedding_service.construct_job_embed_text(
                            title=title,
                            description=description,
                            skills=canonical_skills,
                            company=company or "",
                            location=location or "",
                        )
                        embed_vector = await embedding_service.get_embedding(embed_text)
                    except Exception as emb_exc:
                        logger.warning("Embedding generation error for '%s': %s", title, emb_exc)

                record = {
                    "external_id": external_id,
                    "title": title[:500],
                    "company_name": company[:500] if company else None,
                    "description": description,
                    "location": location[:500] if location else ("Remote (India)" if remote_allowed else "India"),
                    "work_type": work_type,
                    "remote_allowed": remote_allowed,
                    "skills": canonical_skills,
                    "min_salary": min_sal,
                    "max_salary": max_sal,
                    "med_salary": med_sal,
                    "pay_period": pay_period,
                    "country": "India",
                    "currency": "INR",
                    "source": site.lower(),
                    "embedding": embed_vector,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
                normalized_records.append(record)
            except Exception as item_exc:
                logger.warning("Skipping malformed job record: %s", item_exc)

        return normalized_records

    async def save_records(self, session: AsyncSession, records: List[Dict[str, Any]]) -> int:
        """Batch upsert records into job_postings table."""
        if not records:
            return 0

        stmt = insert(JobPosting).values(records)
        stmt = stmt.on_conflict_do_update(
            index_elements=["external_id"],
            set_={
                "title": stmt.excluded.title,
                "company_name": stmt.excluded.company_name,
                "description": stmt.excluded.description,
                "location": stmt.excluded.location,
                "work_type": stmt.excluded.work_type,
                "remote_allowed": stmt.excluded.remote_allowed,
                "skills": stmt.excluded.skills,
                "min_salary": stmt.excluded.min_salary,
                "max_salary": stmt.excluded.max_salary,
                "med_salary": stmt.excluded.med_salary,
                "pay_period": stmt.excluded.pay_period,
                "country": stmt.excluded.country,
                "currency": stmt.excluded.currency,
                "source": stmt.excluded.source,
                "updated_at": stmt.excluded.updated_at,
            },
        )

        await session.execute(stmt)
        await session.commit()

        # Keep ChromaDB in sync with PostgreSQL
        try:
            from app.db.chroma import chroma_service
            chroma_ids = [r["external_id"] for r in records if r.get("embedding")]
            chroma_embs = [r["embedding"] for r in records if r.get("embedding")]
            chroma_docs = [(r.get("title") or "") + " " + (r.get("description") or "")[:500] for r in records if r.get("embedding")]
            chroma_meta = [
                {
                    "title": r.get("title") or "",
                    "company_name": r.get("company_name") or "",
                    "location": r.get("location") or "",
                    "country": r.get("country") or "India",
                    "currency": r.get("currency") or "INR",
                    "source": r.get("source") or "",
                }
                for r in records if r.get("embedding")
            ]
            if chroma_ids:
                chroma_service.upsert_job_postings(
                    ids=chroma_ids,
                    embeddings=chroma_embs,
                    documents=chroma_docs,
                    metadatas=chroma_meta,
                )
        except Exception as chroma_err:
            logger.warning("Failed to sync records to ChromaDB: %s", chroma_err)

        return len(records)


    async def run_batch(self, purge_kaggle: bool = False, purge_all: bool = False) -> Dict[str, int]:
        """Execute complete scraping run across all configured search terms and platforms."""
        if not getattr(settings, "SCRAPER_ENABLED", False):
            logger.warning(
                "Job scraping pipeline invoked but SCRAPER_ENABLED is False in config. "
                "Scraper execution is gated off by default for reproducibility and stability. "
                "Set SCRAPER_ENABLED=true in .env to enable."
            )
            print(
                "\n[GATED] Scraper is disabled by default (SCRAPER_ENABLED=false). "
                "No live scraping requests will be sent.\n"
            )
            return {"total_scraped": 0, "new_inserted": 0, "purged_legacy": 0, "gated": 1}

        logger.info("Starting Real-time Job Scraper Batch Run...")
        stats = {
            "total_scraped": 0,
            "new_inserted": 0,
            "purged_legacy": 0,
        }

        async with AsyncSessionLocal() as session:
            # 1. Optionally purge previous postings
            if purge_all:
                del_result = await session.execute(delete(JobPosting))
                await session.commit()
                purged_count = del_result.rowcount or 0
                stats["purged_legacy"] = purged_count
                logger.info("Purged ALL %d job postings (including US records).", purged_count)
            elif purge_kaggle:
                del_result = await session.execute(
                    delete(JobPosting).where(JobPosting.source == "kaggle_linkedin")
                )
                await session.commit()
                purged_count = del_result.rowcount or 0
                stats["purged_legacy"] = purged_count
                logger.info("Purged %d legacy frozen Kaggle job postings.", purged_count)

            # 2. Fetch existing external IDs and signatures to avoid duplicate insertions
            existing_result = await session.execute(
                select(JobPosting.external_id, JobPosting.title, JobPosting.company_name, JobPosting.location)
            )
            existing_keys: Set[str] = set()
            for r in existing_result.all():
                if r[0]:
                    existing_keys.add(r[0])
                t = (r[1] or "").lower()
                c = (r[2] or "").lower()
                l = (r[3] or "").lower()
                existing_keys.add(f"{t}||{c}||{l}")

            logger.info("Loaded %d existing database signatures for deduplication.", len(existing_keys))

            # 3. Iterate over search terms, locations, and platforms
            for term in self.search_terms:
                for loc in self.locations:
                    for site in self.sites:
                        raw_jobs = self.scrape_platform(site, term, loc)
                        if raw_jobs:
                            stats["total_scraped"] += len(raw_jobs)
                            normalized = await self.normalize_and_filter(raw_jobs, existing_keys, query_loc=loc)
                            if normalized:
                                inserted = await self.save_records(session, normalized)
                                stats["new_inserted"] += inserted
                                logger.info("-> Saved %d new records (Total in DB so far: %d)", inserted, stats["new_inserted"])

                        # Friendly rate-limiting delay between requests
                        delay = random.uniform(1.5, 2.5)
                        time.sleep(delay)

            logger.info("Batch run complete! Final Stats: %s", stats)

        return stats


# ---------------------------------------------------------------------------
# CLI & Scheduler Runner
# ---------------------------------------------------------------------------

def run_once(args: argparse.Namespace):
    """Run a single scraper batch synchronously."""
    terms = [t.strip() for t in args.terms.split(",") if t.strip()] if args.terms else None
    locs = [l.strip() for l in args.locations.split(",") if l.strip()] if args.locations else None
    sites = [s.strip().lower() for s in args.sites.split(",") if s.strip()] if args.sites else None

    pipeline = JobScraperPipeline(
        search_terms=terms,
        locations=locs,
        sites=sites,
        results_per_query=args.limit,
        skip_embeddings=args.skip_embeddings,
    )
    asyncio.run(pipeline.run_batch(purge_kaggle=args.purge_kaggle, purge_all=args.purge_all))


def schedule_daily(args: argparse.Namespace):
    """Launch APScheduler to run the scraper once per day."""
    if not BlockingScheduler:
        logger.error("APScheduler is not installed. Run 'pip install apscheduler'.")
        return

    scheduler = BlockingScheduler()
    logger.info(
        "Initializing APScheduler daily batch job at hour %02d:00 UTC...",
        args.daily_at_hour
    )

    def scheduled_job():
        logger.info("APScheduler triggered daily job scraper batch at %s", datetime.now(timezone.utc))
        run_once(args)

    # Daily trigger at designated hour
    trigger = CronTrigger(hour=args.daily_at_hour, minute=0, timezone="UTC")
    scheduler.add_job(scheduled_job, trigger, id="daily_job_scraper", replace_existing=True)

    # Run immediately on startup if requested
    if args.run_on_start:
        logger.info("Executing initial batch on startup before entering schedule loop...")
        scheduled_job()

    try:
        logger.info("Daily scheduler started. Press Ctrl+C to exit.")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


def main():
    parser = argparse.ArgumentParser(
        description="Real-Time Job Scraper & Daily Batch Scheduler for AI Career Copilot"
    )
    parser.add_argument("--run-once", action="store_true", help="Execute a single scraping batch and exit")
    parser.add_argument("--schedule", action="store_true", help="Start the daily batch scheduler loop")
    parser.add_argument("--run-on-start", action="store_true", help="Run an immediate batch when starting scheduler")
    parser.add_argument("--daily-at-hour", type=int, default=2, help="Hour of day (UTC) for daily cron (default: 2)")
    parser.add_argument("--limit", type=int, default=5, help="Number of jobs requested per site per query")
    parser.add_argument("--terms", type=str, default="", help="Comma-separated search keywords")
    parser.add_argument("--locations", type=str, default="", help="Comma-separated location queries")
    parser.add_argument("--sites", type=str, default="linkedin,indeed,glassdoor", help="Comma-separated sites")
    parser.add_argument("--purge-kaggle", action="store_true", help="Purge frozen legacy Kaggle dataset records")
    parser.add_argument("--purge-all", action="store_true", help="Purge all existing job postings before scraping")
    parser.add_argument("--skip-embeddings", action="store_true", help="Skip vector embedding generation")

    args = parser.parse_args()

    if args.schedule:
        schedule_daily(args)
    else:
        # Default to single run
        run_once(args)


if __name__ == "__main__":
    main()
