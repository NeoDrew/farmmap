"""
iXBRL account parser using direct XML parsing.

We parse inline XBRL documents by looking for ix:nonFraction elements
with numeric financial values, mapping their contextRef and name attributes
to our canonical schema using a taxonomy concept registry.

Note: Arelle is a heavy dependency and tricky to install headlessly.
This implementation uses lxml + BeautifulSoup for a lighter-weight approach
that handles the most common UK GAAP / FRS 105 patterns.
"""
import logging
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

from pipeline.parse.schema_mapper import ParsedAccounts, clean_decimal

logger = logging.getLogger(__name__)

# Concept alias registry: maps taxonomy concept names (lower-case, namespace-stripped)
# to canonical field names. Covers UK-GAAP 2009, FRS 102, FRS 105, IFRS.
CONCEPT_REGISTRY: dict[str, str] = {
    # Turnover / Revenue
    "turnover": "turnover",
    "revenue": "turnover",
    "turnoverorrevenue": "turnover",
    "grossprofit": "turnover",
    "totalrevenue": "turnover",
    "incomestatementturnover": "turnover",
    # Total assets
    "totalassets": "total_assets",
    "fixedassets": "total_assets",
    "totalfixedassets": "total_assets",
    "balancesheetfixedassets": "total_assets",
    # Net assets
    "netassets": "net_assets",
    "netassetsliabilities": "net_assets",
    "shareholdersfunds": "net_assets",
    "equitycapitalandreserves": "net_assets",
    "totalequityandliabilities": "net_assets",
    "netassetsorliabilities": "net_assets",
    # Total liabilities
    "totalliabilities": "total_liabilities",
    "currentliabilities": "total_liabilities",
    "totalcurrentliabilities": "total_liabilities",
    "creditorsfallingduewithinoneyear": "total_liabilities",
    # Employees
    "averagenumberofemployees": "employees",
    "numberofemployees": "employees",
    "employees": "employees",
}


def _strip_namespace(name: str) -> str:
    """Remove XML namespace prefix from a concept name."""
    if ":" in name:
        name = name.split(":")[-1]
    # Remove common prefixes if they leaked through
    for prefix in ["uk-gaap", "ukifrs", "bus", "core", "frs", "ifrs"]:
        if name.lower().startswith(prefix):
            name = name[len(prefix):]
    return name.lower().replace("-", "").replace("_", "")


def _extract_numeric(text: str, scale: int = 0) -> Optional[Decimal]:
    """Extract numeric value from iXBRL text, applying scale."""
    val = clean_decimal(text)
    if val is None:
        return None
    if scale != 0:
        val = val * Decimal(10 ** scale)
    return val


def _get_period_end(soup: BeautifulSoup) -> Optional[date]:
    """Extract the balance sheet / period end date from the document."""
    # Look for xbrli:instant or xbrli:endDate in contexts
    for tag_name in ["xbrli:instant", "instant", "xbrli:enddate", "enddate"]:
        tags = soup.find_all(tag_name)
        dates = []
        for tag in tags:
            try:
                d = date.fromisoformat(tag.get_text(strip=True))
                dates.append(d)
            except Exception:
                pass
        if dates:
            return max(dates)

    # Fallback: look for date patterns in the document text
    text = soup.get_text()
    patterns = [
        r"\b(\d{4}-\d{2}-\d{2})\b",
        r"\b(\d{2}/\d{2}/\d{4})\b",
        r"\b(\d{1,2}\s+\w+\s+\d{4})\b",
    ]
    dates = []
    for pattern in patterns:
        for m in re.finditer(pattern, text):
            try:
                from dateutil import parser as dparser
                d = dparser.parse(m.group(1), dayfirst=True).date()
                if 2000 <= d.year <= 2030:
                    dates.append(d)
            except Exception:
                pass
    return max(dates) if dates else None


def parse_ixbrl(file_path: str, company_number: str) -> ParsedAccounts:
    """
    Parse an iXBRL file and extract canonical financial fields.
    """
    path = Path(file_path)
    filing_date_str = path.stem  # e.g. "2023-06-30"

    try:
        period_end = date.fromisoformat(filing_date_str)
    except Exception:
        period_end = date.today()

    try:
        with open(file_path, "rb") as f:
            content = f.read()
        soup = BeautifulSoup(content, "lxml")

        # Try to get a more accurate period end from document
        doc_period = _get_period_end(soup)
        if doc_period:
            period_end = doc_period

        fields: dict[str, Optional[Decimal]] = {
            "turnover": None,
            "total_assets": None,
            "net_assets": None,
            "total_liabilities": None,
        }
        employees: Optional[int] = None

        # Find all ix:nonFraction elements (numeric XBRL values)
        ix_elements = soup.find_all(
            lambda tag: tag.name and (
                "nonfraction" in tag.name.lower() or
                "nonNumeric" in tag.name or
                tag.name.lower().endswith(":nonfraction")
            )
        )

        # Also try direct attribute search for name= attributes with known concepts
        all_named = soup.find_all(attrs={"name": True})
        ix_elements = list(set(ix_elements + all_named))

        for el in ix_elements:
            name_attr = el.get("name", "") or ""
            if not name_attr:
                continue

            stripped = _strip_namespace(name_attr)
            canonical = CONCEPT_REGISTRY.get(stripped)
            if not canonical:
                continue

            # Extract scale and sign
            try:
                scale_attr = int(el.get("scale", 0) or 0)
            except (ValueError, TypeError):
                scale_attr = 0

            sign = el.get("sign", "")
            raw_text = el.get_text(strip=True)
            if not raw_text:
                continue

            value = _extract_numeric(raw_text, scale_attr)
            if value is None:
                continue

            if sign == "-":
                value = -value

            if canonical == "employees":
                try:
                    employees = int(value)
                except Exception:
                    pass
            elif canonical in fields:
                # Take the largest absolute value if multiple matches (handles subtotals)
                existing = fields[canonical]
                if existing is None or abs(value) > abs(existing):
                    fields[canonical] = value

        # Determine parse status
        found_count = sum(1 for v in fields.values() if v is not None)
        if employees is not None:
            found_count += 1

        if found_count == 0:
            status = "failed"
        elif found_count >= 2:
            status = "ok"
        else:
            status = "partial"

        return ParsedAccounts(
            company_number=company_number,
            period_end=period_end,
            parse_source="ixbrl",
            parse_status=status,
            turnover=fields["turnover"],
            total_assets=fields["total_assets"],
            net_assets=fields["net_assets"],
            total_liabilities=fields["total_liabilities"],
            employees=employees,
        )

    except Exception as exc:
        logger.warning("iXBRL parse failed for %s: %s", file_path, exc)
        return ParsedAccounts(
            company_number=company_number,
            period_end=period_end,
            parse_source="ixbrl",
            parse_status="failed",
        )
