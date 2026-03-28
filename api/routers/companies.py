"""Company endpoints: bbox search and detail view."""
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.deps import get_db
from api.schemas import CompanyDetail, CompanySummary
from pipeline.store.models import Account, Company

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("", response_model=list[CompanySummary])
async def list_companies(
    west: float = Query(..., description="Bounding box west longitude"),
    south: float = Query(..., description="Bounding box south latitude"),
    east: float = Query(..., description="Bounding box east longitude"),
    north: float = Query(..., description="Bounding box north latitude"),
    has_accounts: Optional[bool] = Query(None),
    sic: Optional[str] = Query(None, description="Comma-separated SIC codes to filter"),
    limit: int = Query(500, le=2000),
    db: AsyncSession = Depends(get_db),
):
    """Return companies within a bounding box with latest financial summary."""
    sic_list = [s.strip() for s in sic.split(",")] if sic else None

    # Use raw SQL for PostGIS spatial query + lateral join for latest accounts
    where_clauses = [
        "c.lat IS NOT NULL",
        "c.lat BETWEEN :south AND :north",
        "c.lng BETWEEN :west AND :east",
    ]
    params: dict = {
        "south": south, "north": north, "west": west, "east": east, "limit": limit
    }

    if has_accounts is True:
        where_clauses.append("a.id IS NOT NULL")
    elif has_accounts is False:
        where_clauses.append("a.id IS NULL")

    if sic_list:
        where_clauses.append("c.sic_codes && :sic_codes")
        params["sic_codes"] = sic_list

    where_sql = " AND ".join(where_clauses)

    sql = text(
        f"""
        SELECT
            c.company_number,
            c.company_name,
            c.lat,
            c.lng,
            c.sic_codes,
            c.postcode,
            c.last_accounts_date,
            c.geocode_quality,
            a.net_assets,
            a.total_assets,
            a.turnover,
            a.parse_status
        FROM companies c
        LEFT JOIN LATERAL (
            SELECT net_assets, total_assets, turnover, parse_status, id
            FROM accounts
            WHERE company_number = c.company_number
            ORDER BY period_end DESC
            LIMIT 1
        ) a ON true
        WHERE {where_sql}
        LIMIT :limit
        """
    )

    result = await db.execute(sql, params)
    rows = result.fetchall()
    return [
        CompanySummary(
            company_number=r.company_number,
            company_name=r.company_name,
            lat=r.lat,
            lng=r.lng,
            sic_codes=r.sic_codes,
            postcode=r.postcode,
            last_accounts_date=r.last_accounts_date,
            geocode_quality=r.geocode_quality,
            net_assets=float(r.net_assets) if r.net_assets is not None else None,
            total_assets=float(r.total_assets) if r.total_assets is not None else None,
            turnover=float(r.turnover) if r.turnover is not None else None,
            parse_status=r.parse_status,
        )
        for r in rows
    ]


@router.get("/{company_number}", response_model=CompanyDetail)
async def get_company(
    company_number: str,
    db: AsyncSession = Depends(get_db),
):
    """Return full company detail with all filed accounts."""
    company_number = company_number.upper().strip().zfill(8)
    stmt = (
        select(Company)
        .where(Company.company_number == company_number)
        .options(selectinload(Company.accounts))
    )
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company
