"""
Full refresh Prefect flow: monthly bulk data → geocode → accounts → load.

Run with:
    uv run python -m pipeline.flows.full_refresh
"""
import asyncio
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
import pandas as pd
from sqlalchemy import create_engine, text

from pipeline.geocode.postcodes import geocode_postcodes
from pipeline.ingest.accounts_fetcher import fetch_accounts_for_company, _get_manifest_conn
from pipeline.ingest.ch_api import get_most_recent_accounts_filing
from pipeline.ingest.ch_bulk import download_and_filter, load_parquet
from pipeline.parse.html_parser import parse_html
from pipeline.parse.ixbrl_parser import parse_ixbrl
from pipeline.parse.pdf_parser import parse_pdf
from pipeline.parse.schema_mapper import ParsedAccounts
from pipeline.store.loader import get_sync_engine, upsert_accounts, upsert_companies

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

# Limit concurrency to avoid CH API rate limit hammering
FETCH_CONCURRENCY = 10


def parse_document(doc_info: dict) -> Optional[ParsedAccounts]:
    """Route to the right parser based on format."""
    fmt = doc_info.get("format", "unknown")
    file_path = doc_info.get("file_path", "")
    company_number = doc_info.get("company_number", "")
    period_end_str = doc_info.get("period_end", "")

    if not file_path or not Path(file_path).exists():
        return None

    if fmt == "ixbrl":
        result = parse_ixbrl(file_path, company_number)
    elif fmt == "pdf":
        result = parse_pdf(file_path, company_number)
    elif fmt in ("html", "htm"):
        result = parse_html(file_path, company_number)
    elif fmt == "image_pdf":
        from pipeline.parse.schema_mapper import ParsedAccounts
        from datetime import date
        try:
            period_end = date.fromisoformat(Path(file_path).stem)
        except Exception:
            period_end = date.today()
        return ParsedAccounts(
            company_number=company_number,
            period_end=period_end,
            parse_source="image_pdf",
            parse_status="image_pdf",
        )
    else:
        return None

    if result:
        result.raw_filing_url = doc_info.get("raw_filing_url")
    return result


async def fetch_and_parse_batch(
    company_numbers: list[str],
    semaphore: asyncio.Semaphore,
    manifest_conn: sqlite3.Connection,
) -> list[ParsedAccounts]:
    """Fetch and parse accounts for a batch of companies."""
    results = []
    api_key = os.getenv("CH_API_KEY", "")
    auth = httpx.BasicAuth(username=api_key, password="") if api_key else None

    async with httpx.AsyncClient(timeout=60, follow_redirects=True, auth=auth) as client:
        tasks = [
            _fetch_one(client, cn, semaphore, manifest_conn)
            for cn in company_numbers
        ]
        doc_infos = await asyncio.gather(*tasks, return_exceptions=True)

    for item in doc_infos:
        if isinstance(item, Exception):
            logger.warning("Fetch error: %s", item)
            continue
        if item is None:
            continue
        parsed = parse_document(item)
        if parsed:
            results.append(parsed)
    return results


async def _fetch_one(
    client: httpx.AsyncClient,
    company_number: str,
    semaphore: asyncio.Semaphore,
    manifest_conn: sqlite3.Connection,
) -> Optional[dict]:
    async with semaphore:
        filing = await get_most_recent_accounts_filing(client, company_number)
        if not filing:
            return None
        return await fetch_accounts_for_company(client, company_number, filing, manifest_conn)


async def run_full_refresh(
    skip_download: bool = False,
    max_companies: Optional[int] = None,
) -> dict:
    """
    Main full refresh pipeline:
    1. Download + filter CH bulk data
    2. Geocode postcodes
    3. Load companies into DB
    4. Fetch + parse accounts
    5. Load accounts into DB
    """
    start = datetime.utcnow()
    stats = {
        "companies_found": 0,
        "companies_geocoded": 0,
        "accounts_fetched": 0,
        "accounts_ok": 0,
        "accounts_partial": 0,
        "accounts_failed": 0,
    }

    # Step 1: Get farm companies
    if skip_download and Path("data/parquet/companies_farm.parquet").exists():
        logger.info("Loading existing parquet...")
        df = load_parquet()
    else:
        logger.info("Downloading CH bulk data...")
        df = await download_and_filter()

    if df.empty:
        logger.error("No farm companies found!")
        return stats

    if max_companies:
        df = df.head(max_companies)

    stats["companies_found"] = len(df)
    logger.info("Found %d farm companies", len(df))

    # Step 2: Geocode postcodes
    postcodes = df["RegAddress.PostCode"].dropna().unique().tolist()
    logger.info("Geocoding %d unique postcodes...", len(postcodes))
    geo_data = await geocode_postcodes(postcodes)
    stats["companies_geocoded"] = sum(1 for g in geo_data.values() if g.get("lat") is not None)
    logger.info("Geocoded %d postcodes successfully", stats["companies_geocoded"])

    # Step 3: Load companies
    logger.info("Upserting companies into database...")
    upsert_companies(df, geo_data)

    # Step 4 & 5: Fetch, parse and load accounts
    company_numbers = df["CompanyNumber"].apply(lambda x: str(x).strip().zfill(8)).tolist()
    manifest_conn = _get_manifest_conn()
    semaphore = asyncio.Semaphore(FETCH_CONCURRENCY)

    api_key = os.getenv("CH_API_KEY", "")
    if not api_key:
        logger.warning("CH_API_KEY not set — skipping accounts fetching step")
        manifest_conn.close()
        duration = (datetime.utcnow() - start).total_seconds()
        logger.info("Partial refresh complete in %.0fs (no accounts). Stats: %s", duration, stats)
        return stats

    all_parsed: list[ParsedAccounts] = []
    batch_size = 100

    for i in range(0, len(company_numbers), batch_size):
        batch = company_numbers[i : i + batch_size]
        logger.info(
            "Processing companies %d–%d of %d...",
            i + 1, min(i + batch_size, len(company_numbers)), len(company_numbers),
        )
        parsed = await fetch_and_parse_batch(batch, semaphore, manifest_conn)
        all_parsed.extend(parsed)

        # Flush to DB every 500 records
        if len(all_parsed) >= 500:
            upsert_accounts(all_parsed)
            stats["accounts_fetched"] += len(all_parsed)
            stats["accounts_ok"] += sum(1 for p in all_parsed if p.parse_status == "ok")
            stats["accounts_partial"] += sum(1 for p in all_parsed if p.parse_status == "partial")
            stats["accounts_failed"] += sum(1 for p in all_parsed if p.parse_status in ("failed", "image_pdf"))
            all_parsed = []

    # Flush remainder
    if all_parsed:
        upsert_accounts(all_parsed)
        stats["accounts_fetched"] += len(all_parsed)
        stats["accounts_ok"] += sum(1 for p in all_parsed if p.parse_status == "ok")
        stats["accounts_partial"] += sum(1 for p in all_parsed if p.parse_status == "partial")
        stats["accounts_failed"] += sum(1 for p in all_parsed if p.parse_status in ("failed", "image_pdf"))

    duration = (datetime.utcnow() - start).total_seconds()
    logger.info("Full refresh complete in %.0fs. Stats: %s", duration, stats)
    manifest_conn.close()
    return stats


if __name__ == "__main__":
    import sys
    skip_dl = "--skip-download" in sys.argv
    numeric_args = [a for a in sys.argv[1:] if a.isdigit()]
    max_co = int(numeric_args[0]) if numeric_args else None
    asyncio.run(run_full_refresh(skip_download=skip_dl, max_companies=max_co))
