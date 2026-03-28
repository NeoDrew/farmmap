"""Stats and pipeline status endpoints."""
import json
from typing import Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, get_redis
from api.schemas import PipelineStatus, ViewportStats

router = APIRouter(prefix="/api", tags=["stats"])

CACHE_TTL = 300  # 5 minutes for stats


@router.get("/stats/summary", response_model=ViewportStats)
async def viewport_summary(
    west: float = Query(...),
    south: float = Query(...),
    east: float = Query(...),
    north: float = Query(...),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Aggregate stats for the current map viewport."""
    cache_key = f"stats:{west:.2f},{south:.2f},{east:.2f},{north:.2f}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    sql = text(
        """
        SELECT
            COUNT(c.company_number) AS total_companies,
            COUNT(a.id) AS companies_with_accounts,
            COUNT(CASE WHEN a.parse_status = 'ok' THEN 1 END) AS accounts_ok,
            COUNT(CASE WHEN a.parse_status = 'partial' THEN 1 END) AS accounts_partial,
            COUNT(CASE WHEN a.parse_status IN ('failed', 'image_pdf') THEN 1 END) AS accounts_failed,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY a.net_assets) AS median_net_assets,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY a.turnover) AS median_turnover,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY a.total_assets) AS median_total_assets
        FROM companies c
        LEFT JOIN LATERAL (
            SELECT id, parse_status, net_assets, turnover, total_assets
            FROM accounts
            WHERE company_number = c.company_number
            ORDER BY period_end DESC
            LIMIT 1
        ) a ON true
        WHERE c.lat BETWEEN :south AND :north
          AND c.lng BETWEEN :west AND :east
        """
    )
    result = await db.execute(
        sql,
        {"south": south, "north": north, "west": west, "east": east},
    )
    r = result.fetchone()
    stats = ViewportStats(
        total_companies=r.total_companies or 0,
        companies_with_accounts=r.companies_with_accounts or 0,
        accounts_ok=r.accounts_ok or 0,
        accounts_partial=r.accounts_partial or 0,
        accounts_failed=r.accounts_failed or 0,
        median_net_assets=float(r.median_net_assets) if r.median_net_assets is not None else None,
        median_turnover=float(r.median_turnover) if r.median_turnover is not None else None,
        median_total_assets=float(r.median_total_assets) if r.median_total_assets is not None else None,
    )
    await redis.setex(cache_key, CACHE_TTL, stats.model_dump_json())
    return stats


@router.get("/pipeline/status", response_model=PipelineStatus)
async def pipeline_status(
    db: AsyncSession = Depends(get_db),
):
    """Return pipeline run status and database coverage stats."""
    sql = text(
        """
        WITH coverage AS (
            SELECT
                COUNT(DISTINCT c.company_number) AS total_companies,
                COUNT(DISTINCT a.company_number) AS companies_with_accounts,
                COUNT(CASE WHEN a.parse_status = 'ok' THEN 1 END) AS parse_ok,
                COUNT(CASE WHEN a.parse_status = 'partial' THEN 1 END) AS parse_partial,
                COUNT(CASE WHEN a.parse_status IN ('failed', 'image_pdf') THEN 1 END) AS parse_failed
            FROM companies c
            LEFT JOIN accounts a ON a.company_number = c.company_number
        )
        SELECT
            (SELECT started_at FROM pipeline_runs ORDER BY started_at DESC LIMIT 1) AS last_run_at,
            (SELECT status FROM pipeline_runs ORDER BY started_at DESC LIMIT 1) AS last_run_status,
            cov.total_companies,
            cov.companies_with_accounts,
            cov.parse_ok,
            cov.parse_partial,
            cov.parse_failed
        FROM coverage cov
        """
    )
    result = await db.execute(sql)
    r = result.fetchone()
    if not r:
        return PipelineStatus(
            last_run_at=None,
            last_run_status=None,
            total_companies=0,
            companies_with_accounts=0,
            parse_ok=0,
            parse_partial=0,
            parse_failed=0,
            coverage_pct=0.0,
        )
    total = r.total_companies or 0
    with_accts = r.companies_with_accounts or 0
    coverage_pct = round(100.0 * with_accts / total, 1) if total > 0 else 0.0
    return PipelineStatus(
        last_run_at=r.last_run_at,
        last_run_status=r.last_run_status,
        total_companies=total,
        companies_with_accounts=with_accts,
        parse_ok=r.parse_ok or 0,
        parse_partial=r.parse_partial or 0,
        parse_failed=r.parse_failed or 0,
        coverage_pct=coverage_pct,
    )
