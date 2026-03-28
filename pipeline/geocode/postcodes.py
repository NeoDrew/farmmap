"""Batch postcode geocoding via postcodes.io API."""
import logging
from pathlib import Path
from typing import Optional

import httpx
import pandas as pd

logger = logging.getLogger(__name__)

POSTCODES_IO_BULK = "https://api.postcodes.io/postcodes"
POSTCODES_IO_SINGLE = "https://api.postcodes.io/postcodes/{}"
POSTCODES_IO_TERMINATED = "https://api.postcodes.io/terminated_postcodes/{}"
CACHE_FILE = Path("data/cache/postcode_cache.parquet")
BATCH_SIZE = 100


def _load_cache() -> dict[str, dict]:
    if CACHE_FILE.exists():
        df = pd.read_parquet(CACHE_FILE)
        return df.set_index("postcode").to_dict("index")
    return {}


def _save_cache(cache: dict[str, dict]) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame.from_dict(cache, orient="index").reset_index()
    df.rename(columns={"index": "postcode"}, inplace=True)
    df.to_parquet(CACHE_FILE, index=False)


def _normalise_postcode(pc: str) -> str:
    return pc.strip().upper().replace(" ", "")


async def geocode_postcodes(postcodes: list[str]) -> dict[str, dict]:
    """
    Geocode a list of postcodes. Returns dict mapping postcode → geo info.
    Uses a local parquet cache to avoid re-fetching.
    """
    cache = _load_cache()
    normalised = {_normalise_postcode(p): p for p in postcodes}
    to_fetch = [n for n in normalised if n not in cache]

    results: dict[str, dict] = {}

    async with httpx.AsyncClient(timeout=30) as client:
        # Primary batch lookups
        for i in range(0, len(to_fetch), BATCH_SIZE):
            batch = to_fetch[i : i + BATCH_SIZE]
            try:
                resp = await client.post(
                    POSTCODES_IO_BULK, json={"postcodes": batch}
                )
                resp.raise_for_status()
                for item in resp.json().get("result", []):
                    if item is None:
                        continue
                    query = _normalise_postcode(item.get("query", ""))
                    result = item.get("result")
                    if result:
                        cache[query] = {
                            "lat": result["latitude"],
                            "lng": result["longitude"],
                            "admin_district": result.get("admin_district"),
                            "admin_county": result.get("admin_county"),
                            "region": result.get("region"),
                            "geocode_quality": "exact",
                        }
                    else:
                        # Try terminated postcode fallback
                        fallback = await _try_terminated(client, query)
                        cache[query] = fallback
            except Exception as exc:
                logger.warning("Batch geocode failed for batch starting %s: %s", batch[0], exc)

        # District-level fallback for anything still missing
        for norm in to_fetch:
            if norm not in cache:
                district = norm[:4].strip()
                cache[norm] = {
                    "lat": None,
                    "lng": None,
                    "admin_district": None,
                    "admin_county": None,
                    "region": None,
                    "geocode_quality": "failed",
                }
                logger.warning("Could not geocode postcode: %s", norm)

    # Merge cache hits
    for norm, orig in normalised.items():
        if norm in cache:
            results[orig] = cache[norm]

    _save_cache(cache)
    return results


async def _try_terminated(client: httpx.AsyncClient, postcode: str) -> dict:
    """Try the terminated postcodes endpoint."""
    try:
        resp = await client.get(POSTCODES_IO_TERMINATED.format(postcode))
        if resp.status_code == 200:
            data = resp.json().get("result", {})
            if data:
                return {
                    "lat": data.get("latitude"),
                    "lng": data.get("longitude"),
                    "admin_district": None,
                    "admin_county": None,
                    "region": None,
                    "geocode_quality": "terminated",
                }
    except Exception:
        pass
    return {
        "lat": None,
        "lng": None,
        "admin_district": None,
        "admin_county": None,
        "region": None,
        "geocode_quality": "failed",
    }
