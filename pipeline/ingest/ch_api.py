"""Companies House REST API client with rate limiting and retry."""
import asyncio
import os
import time
from typing import Any, Optional

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

CH_API_BASE = "https://api.company-information.service.gov.uk"
DOCUMENT_API_BASE = "https://document-api.company-information.service.gov.uk"

# 600 requests per 5 minutes = 2 per second
_RATE_LIMIT_CALLS = 600
_RATE_LIMIT_PERIOD = 300  # seconds
_MIN_INTERVAL = _RATE_LIMIT_PERIOD / _RATE_LIMIT_CALLS  # ~0.5s per request

_last_call_time: float = 0.0
_lock = asyncio.Lock()


async def _rate_limited_sleep() -> None:
    global _last_call_time
    async with _lock:
        now = time.monotonic()
        elapsed = now - _last_call_time
        if elapsed < _MIN_INTERVAL:
            await asyncio.sleep(_MIN_INTERVAL - elapsed)
        _last_call_time = time.monotonic()


def _get_auth() -> Optional[httpx.BasicAuth]:
    api_key = os.getenv("CH_API_KEY", "")
    if api_key:
        return httpx.BasicAuth(username=api_key, password="")
    return None


@retry(
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(5),
)
async def get_filing_history(
    client: httpx.AsyncClient,
    company_number: str,
    category: str = "accounts",
) -> list[dict[str, Any]]:
    """Return list of filings for a company, most recent first."""
    await _rate_limited_sleep()
    url = f"{CH_API_BASE}/company/{company_number}/filing-history"
    params = {"category": category, "count": 5}
    resp = await client.get(url, params=params, auth=_get_auth())
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    data = resp.json()
    return data.get("items", [])


@retry(
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(5),
)
async def get_document_metadata(
    client: httpx.AsyncClient, document_url: str
) -> Optional[dict[str, Any]]:
    """Fetch document metadata to get the download URL and content type."""
    await _rate_limited_sleep()
    resp = await client.get(document_url, auth=_get_auth())
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


async def get_most_recent_accounts_filing(
    client: httpx.AsyncClient, company_number: str
) -> Optional[dict[str, Any]]:
    """Return the most recent accounts filing metadata for a company."""
    filings = await get_filing_history(client, company_number)
    if not filings:
        return None
    return filings[0]


def determine_format(filing: dict[str, Any]) -> str:
    """Determine document format from filing metadata."""
    links = filing.get("links", {})
    doc_url = links.get("document_metadata", "")
    if "xhtml" in doc_url.lower() or filing.get("description", "").lower().startswith(
        "accounts"
    ):
        return "ixbrl"
    return "unknown"
