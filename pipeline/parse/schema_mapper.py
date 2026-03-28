"""Canonical schema for parsed accounts and normalisation helpers."""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal, Optional


@dataclass
class ParsedAccounts:
    company_number: str
    period_end: date
    parse_source: Literal["ixbrl", "pdf", "html", "image_pdf", "unknown"]
    parse_status: Literal["ok", "partial", "failed", "image_pdf"]
    turnover: Optional[Decimal] = None
    total_assets: Optional[Decimal] = None
    net_assets: Optional[Decimal] = None
    total_liabilities: Optional[Decimal] = None
    employees: Optional[int] = None
    currency: str = "GBP"
    raw_filing_url: Optional[str] = None

    def has_any_financial_data(self) -> bool:
        return any(
            v is not None
            for v in [self.turnover, self.total_assets, self.net_assets, self.total_liabilities]
        )

    def to_dict(self) -> dict:
        return {
            "company_number": self.company_number,
            "period_end": self.period_end,
            "parse_source": self.parse_source,
            "parse_status": self.parse_status,
            "turnover": float(self.turnover) if self.turnover is not None else None,
            "total_assets": float(self.total_assets) if self.total_assets is not None else None,
            "net_assets": float(self.net_assets) if self.net_assets is not None else None,
            "total_liabilities": float(self.total_liabilities) if self.total_liabilities is not None else None,
            "employees": self.employees,
            "currency": self.currency,
            "raw_filing_url": self.raw_filing_url,
        }


def clean_decimal(value: str | int | float | None) -> Optional[Decimal]:
    """Safely convert a value to Decimal, stripping currency symbols."""
    if value is None:
        return None
    try:
        s = str(value).strip().replace(",", "").replace("£", "").replace("$", "")
        if s in ("", "-", "N/A", "n/a"):
            return None
        # Handle parenthetical negatives: (123) → -123
        if s.startswith("(") and s.endswith(")"):
            s = "-" + s[1:-1]
        return Decimal(s)
    except Exception:
        return None


# Maps from various label strings (lower-case) to canonical field names
LABEL_TO_FIELD: dict[str, str] = {
    # Turnover / revenue
    "turnover": "turnover",
    "revenue": "turnover",
    "sales": "turnover",
    "income": "turnover",
    "total income": "turnover",
    "gross income": "turnover",
    # Total assets
    "total assets": "total_assets",
    "fixed assets": "total_assets",
    "total fixed assets": "total_assets",
    "net assets": "net_assets",
    "net assets or liabilities": "net_assets",
    "shareholders funds": "net_assets",
    "shareholders' funds": "net_assets",
    "members' funds": "net_assets",
    "capital and reserves": "net_assets",
    "net worth": "net_assets",
    # Total liabilities
    "total liabilities": "total_liabilities",
    "creditors: amounts falling due": "total_liabilities",
    "creditors": "total_liabilities",
    # Employees
    "average number of employees": "employees",
    "number of employees": "employees",
    "employees": "employees",
}


def map_label_to_field(label: str) -> Optional[str]:
    """Return canonical field name for a label string, or None."""
    normalised = label.lower().strip().rstrip(":")
    return LABEL_TO_FIELD.get(normalised)
