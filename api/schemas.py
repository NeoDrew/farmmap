"""Pydantic response schemas."""
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel


class AccountSchema(BaseModel):
    id: int
    period_end: date
    parse_source: Optional[str]
    parse_status: Optional[str]
    turnover: Optional[float]
    total_assets: Optional[float]
    net_assets: Optional[float]
    total_liabilities: Optional[float]
    employees: Optional[int]
    raw_filing_url: Optional[str]

    model_config = {"from_attributes": True}


class CompanySummary(BaseModel):
    company_number: str
    company_name: str
    lat: Optional[float]
    lng: Optional[float]
    sic_codes: Optional[list[str]]
    postcode: Optional[str]
    last_accounts_date: Optional[date]
    geocode_quality: Optional[str]
    net_assets: Optional[float]
    total_assets: Optional[float]
    turnover: Optional[float]
    parse_status: Optional[str]


class CompanyDetail(BaseModel):
    company_number: str
    company_name: str
    status: Optional[str]
    sic_codes: Optional[list[str]]
    postcode: Optional[str]
    registered_address: Optional[dict]
    lat: Optional[float]
    lng: Optional[float]
    geocode_quality: Optional[str]
    last_accounts_date: Optional[date]
    next_accounts_due: Optional[date]
    accounts: list[AccountSchema]

    model_config = {"from_attributes": True}


class ViewportStats(BaseModel):
    total_companies: int
    companies_with_accounts: int
    accounts_ok: int
    accounts_partial: int
    accounts_failed: int
    median_net_assets: Optional[float]
    median_turnover: Optional[float]
    median_total_assets: Optional[float]


class PipelineStatus(BaseModel):
    last_run_at: Optional[datetime]
    last_run_status: Optional[str]
    total_companies: int
    companies_with_accounts: int
    parse_ok: int
    parse_partial: int
    parse_failed: int
    coverage_pct: float
