"""
scripts/refresh_jobs.py
-----------------------
Standalone scheduled job market refresh command (Phase 6).
Suitable for execution via Windows Task Scheduler or cron.

Usage:
    python scripts/refresh_jobs.py [--sources adzuna] [--queries "Software Engineer" "Data Scientist"] [--evaluate-only]
"""

import argparse
import asyncio
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.logging import logger
from app.db.session import AsyncSessionLocal
from app.services.job_ingestion_service import job_ingestion_service
from app.services.job_refresh_coordinator import job_refresh_coordinator


async def main_async(args: argparse.Namespace) -> int:
    logger.info("Starting scheduled job market refresh cycle...")

    if args.evaluate_only:
        logger.info("Running freshness evaluation only (no ingestion)...")
        async with AsyncSessionLocal() as session:
            summary = await job_ingestion_service.evaluate_listing_freshness(
                db=session,
                stale_days=args.stale_days,
                expired_days=args.expired_days,
            )
        logger.info(f"Freshness evaluation completed: {summary}")
        return 0

    sources = args.sources.split(",") if args.sources else None
    queries = args.queries if args.queries else None

    run_record = await job_refresh_coordinator.run_refresh(
        queries=queries,
        sources=sources,
        max_retries=args.max_retries,
        evaluate_freshness=not args.skip_evaluation,
    )

    logger.info(
        f"Refresh cycle finished with status='{run_record.status}' in {run_record.duration_seconds}s. "
        f"Sources: {list(run_record.sources.keys())}. Freshness summary: {run_record.freshness_summary}"
    )

    if run_record.status in ("completed", "partial_success", "skipped"):
        return 0
    else:
        logger.error(f"Refresh cycle failed: {run_record.error_message} (category={run_record.error_category})")
        return 1


def main():
    parser = argparse.ArgumentParser(description="AI Career Copilot Job Market Refresh Command")
    parser.add_argument("--sources", type=str, default=None, help="Comma-separated sources to refresh (e.g. adzuna)")
    parser.add_argument("--queries", nargs="+", default=None, help="List of job search queries")
    parser.add_argument("--max-retries", type=int, default=3, help="Max retries for transient failures")
    parser.add_argument("--evaluate-only", action="store_true", help="Only evaluate freshness without fetching new jobs")
    parser.add_argument("--skip-evaluation", action="store_true", help="Skip freshness evaluation step")
    parser.add_argument("--stale-days", type=int, default=None, help="Threshold in days to consider a listing stale (default: 14)")
    parser.add_argument("--expired-days", type=int, default=None, help="Threshold in days to consider a listing expired (default: 30)")

    args = parser.parse_args()
    exit_code = asyncio.run(main_async(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
