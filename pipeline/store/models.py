"""SQLAlchemy models for FarmMap."""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Float,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "companies"

    company_number: Mapped[str] = mapped_column(String(8), primary_key=True)
    company_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[Optional[str]] = mapped_column(String(50))
    sic_codes: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String(10)))
    postcode: Mapped[Optional[str]] = mapped_column(String(10))
    registered_address: Mapped[Optional[dict]] = mapped_column(JSONB)
    lat: Mapped[Optional[float]] = mapped_column(Float)
    lng: Mapped[Optional[float]] = mapped_column(Float)
    geocode_quality: Mapped[Optional[str]] = mapped_column(String(20))
    last_accounts_date: Mapped[Optional[date]] = mapped_column(Date)
    next_accounts_due: Mapped[Optional[date]] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    accounts: Mapped[list["Account"]] = relationship(
        back_populates="company", order_by="Account.period_end.desc()"
    )


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_number: Mapped[str] = mapped_column(
        String(8), nullable=False, index=True
    )
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    parse_source: Mapped[Optional[str]] = mapped_column(String(10))
    parse_status: Mapped[Optional[str]] = mapped_column(String(20))
    turnover: Mapped[Optional[float]] = mapped_column(Numeric(18, 2))
    total_assets: Mapped[Optional[float]] = mapped_column(Numeric(18, 2))
    net_assets: Mapped[Optional[float]] = mapped_column(Numeric(18, 2))
    total_liabilities: Mapped[Optional[float]] = mapped_column(Numeric(18, 2))
    employees: Mapped[Optional[int]] = mapped_column(Integer)
    raw_filing_url: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    company: Mapped["Company"] = relationship(back_populates="accounts")


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    flow_name: Mapped[str] = mapped_column(String(100), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="running")
    companies_processed: Mapped[Optional[int]] = mapped_column(Integer)
    accounts_parsed: Mapped[Optional[int]] = mapped_column(Integer)
    parse_ok: Mapped[Optional[int]] = mapped_column(Integer)
    parse_partial: Mapped[Optional[int]] = mapped_column(Integer)
    parse_failed: Mapped[Optional[int]] = mapped_column(Integer)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
