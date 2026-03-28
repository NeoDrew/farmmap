"""Map endpoints: GeoJSON points, choropleth data."""
import json
from typing import Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, get_redis

router = APIRouter(prefix="/api/map", tags=["map"])

CACHE_TTL = 3600  # 1 hour


def _bbox_cache_key(prefix: str, west: float, south: float, east: float, north: float, **kwargs) -> str:
    extras = "_".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
    return f"{prefix}:{west:.3f},{south:.3f},{east:.3f},{north:.3f}:{extras}"


@router.get("/points")
async def map_points(
    west: float = Query(...),
    south: float = Query(...),
    east: float = Query(...),
    north: float = Query(...),
    has_accounts: Optional[bool] = Query(None),
    sic: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Return GeoJSON FeatureCollection of company points within bbox.
    Cached in Redis for 1 hour.
    """
    sic_list = [s.strip() for s in sic.split(",")] if sic else None
    cache_key = _bbox_cache_key(
        "points", west, south, east, north,
        has_accounts=has_accounts, sic=sic or ""
    )

    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    where = [
        "c.lat BETWEEN :south AND :north",
        "c.lng BETWEEN :west AND :east",
    ]
    params: dict = {"south": south, "north": north, "west": west, "east": east}

    if has_accounts is True:
        where.append("a.id IS NOT NULL")
    elif has_accounts is False:
        where.append("a.id IS NULL")

    if sic_list:
        where.append("c.sic_codes && :sic_codes")
        params["sic_codes"] = sic_list

    where_sql = " AND ".join(where)

    sql = text(
        f"""
        SELECT
            c.company_number,
            c.company_name,
            c.lat,
            c.lng,
            c.sic_codes,
            c.postcode,
            a.net_assets,
            a.total_assets,
            a.turnover,
            a.parse_status,
            a.period_end
        FROM companies c
        LEFT JOIN LATERAL (
            SELECT net_assets, total_assets, turnover, parse_status, period_end, id
            FROM accounts
            WHERE company_number = c.company_number
            ORDER BY period_end DESC
            LIMIT 1
        ) a ON true
        WHERE {where_sql}
        LIMIT 2000
        """
    )

    result = await db.execute(sql, params)
    rows = result.fetchall()

    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [r.lng, r.lat]},
            "properties": {
                "company_number": r.company_number,
                "company_name": r.company_name,
                "sic_codes": r.sic_codes,
                "postcode": r.postcode,
                "net_assets": float(r.net_assets) if r.net_assets is not None else None,
                "total_assets": float(r.total_assets) if r.total_assets is not None else None,
                "turnover": float(r.turnover) if r.turnover is not None else None,
                "parse_status": r.parse_status,
                "period_end": str(r.period_end) if r.period_end else None,
            },
        }
        for r in rows
    ]

    geojson = {"type": "FeatureCollection", "features": features}
    await redis.setex(cache_key, CACHE_TTL, json.dumps(geojson))
    return geojson


@router.get("/choropleth")
async def map_choropleth(
    metric: str = Query("net_assets", enum=["net_assets", "turnover", "total_assets", "company_count", "coverage_pct"]),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Return district-level (postcode district: 'EX14', 'TA1' etc.) aggregated stats
    as a JSON object keyed by district code. Cached for 1 hour.

    Returns a dict of { "district": { metric_value, company_count, accounts_count } }
    suitable for choropleth colouring in the frontend.
    """
    cache_key = f"choropleth:{metric}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    metric_sql = {
        "net_assets": "PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY a.net_assets)",
        "turnover": "PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY a.turnover)",
        "total_assets": "PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY a.total_assets)",
        "company_count": "COUNT(c.company_number)",
        "coverage_pct": "ROUND(100.0 * COUNT(a.net_assets) / NULLIF(COUNT(c.company_number), 0), 1)",
    }[metric]

    sql = text(
        f"""
        SELECT
            UPPER(REGEXP_REPLACE(c.postcode, '\\s.*$', '')) AS district,
            {metric_sql} AS metric_value,
            COUNT(c.company_number) AS company_count,
            COUNT(a.id) AS accounts_count,
            ROUND(100.0 * COUNT(a.id) / NULLIF(COUNT(c.company_number), 0), 1) AS coverage_pct
        FROM companies c
        LEFT JOIN LATERAL (
            SELECT net_assets, total_assets, turnover, id
            FROM accounts
            WHERE company_number = c.company_number
              AND parse_status IN ('ok', 'partial')
            ORDER BY period_end DESC
            LIMIT 1
        ) a ON true
        WHERE c.postcode IS NOT NULL
        GROUP BY district
        HAVING COUNT(c.company_number) >= 1
        ORDER BY district
        """
    )

    result = await db.execute(sql)
    rows = result.fetchall()

    data = {
        r.district: {
            "metric_value": float(r.metric_value) if r.metric_value is not None else None,
            "company_count": r.company_count,
            "accounts_count": r.accounts_count,
            "coverage_pct": float(r.coverage_pct) if r.coverage_pct else 0.0,
        }
        for r in rows
        if r.district
    }

    await redis.setex(cache_key, CACHE_TTL, json.dumps(data))
    return data
