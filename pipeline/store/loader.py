"""Upsert companies and accounts into PostgreSQL."""
import logging
import os
from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert

from pipeline.parse.schema_mapper import ParsedAccounts
from pipeline.store.models import Account, Company

logger = logging.getLogger(__name__)


def get_sync_engine():
    url = os.getenv(
        "DATABASE_URL_SYNC",
        "postgresql+psycopg://farmmap:farmmap@localhost:5433/farmmap",
    )
    return create_engine(url, pool_pre_ping=True)


def upsert_companies(df: pd.DataFrame, geo_data: dict[str, dict]) -> int:
    """
    Upsert farm companies from the filtered bulk DataFrame.
    geo_data: dict mapping original postcode → geocode result dict.
    Returns count of rows upserted.
    """
    engine = get_sync_engine()
    rows = []

    for _, row in df.iterrows():
        company_num = str(row.get("CompanyNumber", "")).strip().zfill(8)
        if not company_num:
            continue

        postcode = str(row.get("RegAddress.PostCode", "") or "").strip()
        geo = geo_data.get(postcode, {})
        lat = geo.get("lat")
        lng = geo.get("lng")

        sic_codes = []
        for col in ["SICCode.SicText_1", "SICCode.SicText_2", "SICCode.SicText_3", "SICCode.SicText_4"]:
            val = str(row.get(col, "") or "").strip()
            if val and val != "nan":
                code = val[:5]
                if code.isdigit() and code not in sic_codes:
                    sic_codes.append(code)

        address = {
            "line1": _clean(row.get("RegAddress.AddressLine1")),
            "line2": _clean(row.get("RegAddress.AddressLine2")),
            "town": _clean(row.get("RegAddress.PostTown")),
            "county": _clean(row.get("RegAddress.County")),
            "country": _clean(row.get("RegAddress.Country")),
            "postcode": postcode,
        }

        last_accounts = _parse_date(row.get("Accounts.LastMadeUpDate"))
        next_accounts = _parse_date(row.get("Accounts.NextDueDate"))

        record: dict[str, Any] = {
            "company_number": company_num,
            "company_name": str(row.get("CompanyName", "")).strip(),
            "status": str(row.get("CompanyStatus", "")).strip().lower() or None,
            "sic_codes": sic_codes or None,
            "postcode": postcode or None,
            "registered_address": address,
            "lat": lat,
            "lng": lng,
            "geocode_quality": geo.get("geocode_quality"),
            "last_accounts_date": last_accounts or None,
            "next_accounts_due": next_accounts or None,
        }
        rows.append(record)

    if not rows:
        return 0

    with engine.begin() as conn:
        stmt = insert(Company).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["company_number"],
            set_={
                "company_name": stmt.excluded.company_name,
                "status": stmt.excluded.status,
                "sic_codes": stmt.excluded.sic_codes,
                "postcode": stmt.excluded.postcode,
                "registered_address": stmt.excluded.registered_address,
                "lat": stmt.excluded.lat,
                "lng": stmt.excluded.lng,
                "geocode_quality": stmt.excluded.geocode_quality,
                "last_accounts_date": stmt.excluded.last_accounts_date,
                "next_accounts_due": stmt.excluded.next_accounts_due,
                "updated_at": text("now()"),
            },
        )
        conn.execute(stmt)

        # Update PostGIS geometry column from lat/lng (only if PostGIS is available)
        try:
            conn.execute(
                text(
                    """
                    UPDATE companies
                    SET geom = ST_SetSRID(ST_MakePoint(lng, lat), 4326)
                    WHERE lat IS NOT NULL AND lng IS NOT NULL AND geom IS NULL
                    """
                )
            )
        except Exception:
            pass  # PostGIS not available on this database

    logger.info("Upserted %d companies", len(rows))
    return len(rows)


def upsert_accounts(parsed: list[ParsedAccounts]) -> int:
    """Insert parsed account records. Skips duplicates on (company_number, period_end)."""
    if not parsed:
        return 0
    engine = get_sync_engine()
    rows = [p.to_dict() for p in parsed]

    with engine.begin() as conn:
        stmt = insert(Account).values(rows)
        stmt = stmt.on_conflict_do_nothing()
        result = conn.execute(stmt)

    count = len(rows)
    logger.info("Inserted %d account records", count)
    return count


def _clean(val: Any) -> Any:
    """Convert NaN / 'nan' strings to None."""
    if val is None:
        return None
    s = str(val).strip()
    if s.lower() in ("nan", "none", ""):
        return None
    return s


def _parse_date(val: Any) -> date | None:
    """Parse CH date strings (DD/MM/YYYY or YYYY-MM-DD) into date objects."""
    s = _clean(val)
    if s is None:
        return None
    # CH bulk CSV uses DD/MM/YYYY
    if "/" in s:
        try:
            return date(int(s[6:10]), int(s[3:5]), int(s[0:2]))
        except (ValueError, IndexError):
            return None
    # ISO format
    try:
        return date.fromisoformat(s[:10])
    except (ValueError, IndexError):
        return None
