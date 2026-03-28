"""
Incremental refresh: fetch new/updated accounts for known companies since last run.

Run with:
    uv run python -m pipeline.flows.incremental
"""
import asyncio
import logging
import os
from datetime import date, timedelta
from typing import Optional

import httpx
from sqlalchemy import text

from pipeline.flows.full_refresh import fetch_and_parse_batch, parse_document
from pipeline.ingest.accounts_fetcher import _get_manifest_conn
from pipeline.ingest.ch_api import get_filing_history
from pipeline.store.loader import get_sync_engine, upsert_accounts

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def get_last_run_date() -> date:
    """Get the date of the last successful incremental run, defaulting to 30 days ago."""
    engine = get_sync_engine()
    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT MAX(started_at) FROM pipeline_runs WHERE status='ok' AND flow_name='incremental'"
            )
        ).scalar()
        if result:
            return result.date() - timedelta(days=1)
    return date.today() - timedelta(days=30)


def get_all_company_numbers() -> list[str]:
    """Fetch all known company numbers from the database."""
    engine = get_sync_engine()
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT company_number FROM companies ORDER BY company_number")).fetchall()
    return [r[0] for r in rows]


async def run_incremental(since_date: Optional[date] = None) -> dict:
    """
    Check CH API for new account filings since last run.
    Only processes companies with upcoming or overdue accounts dates.
    """
    if since_date is None:
        since_date = get_last_run_date()

    logger.info("Running incremental refresh for filings since %s", since_date)

    # Get companies whose accounts were recently filed or are overdue
    engine = get_sync_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT company_number FROM companies
                WHERE last_accounts_date >= :since
                   OR next_accounts_due <= current_date + interval '30 days'
                ORDER BY company_number
                """
            ),
            {"since": since_date},
        ).fetchall()
    company_numbers = [r[0] for r in rows]
    logger.info("Checking %d companies for new filings", len(company_numbers))

    manifest_conn = _get_manifest_conn()
    semaphore = asyncio.Semaphore(10)
    all_parsed = []
    batch_size = 100

    for i in range(0, len(company_numbers), batch_size):
        batch = company_numbers[i : i + batch_size]
        logger.info("Processing companies %d–%d...", i + 1, min(i + batch_size, len(company_numbers)))
        parsed = await fetch_and_parse_batch(batch, semaphore, manifest_conn)
        all_parsed.extend(parsed)

    count = upsert_accounts(all_parsed)
    manifest_conn.close()
    logger.info("Incremental refresh complete. Loaded %d account records.", count)
    return {"accounts_loaded": count, "companies_checked": len(company_numbers)}


if __name__ == "__main__":
    asyncio.run(run_incremental())
