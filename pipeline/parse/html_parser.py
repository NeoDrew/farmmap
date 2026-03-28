"""HTML account parser using BeautifulSoup."""
import logging
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

from pipeline.parse.schema_mapper import ParsedAccounts, clean_decimal, map_label_to_field

logger = logging.getLogger(__name__)

MONEY_PATTERN = re.compile(
    r"[£$]?\s*\(?\s*([\d,]+(?:\.\d+)?)\s*\)?"
)


def _parse_money(text: str) -> Optional[Decimal]:
    text = text.strip()
    if not text:
        return None
    is_negative = text.startswith("(") or text.startswith("-")
    m = MONEY_PATTERN.search(text)
    if not m:
        return None
    val = clean_decimal(m.group(1))
    if val is None:
        return None
    return -val if is_negative else val


def _get_period_end(soup: BeautifulSoup, file_path: str) -> date:
    """Try to extract period end date from HTML or filename."""
    path = Path(file_path)
    try:
        return date.fromisoformat(path.stem)
    except Exception:
        pass

    # Try to find a date in the document
    text = soup.get_text()
    patterns = [
        r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b",
        r"\b(\d{4})-(\d{2})-(\d{2})\b",
    ]
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    }
    for pattern in patterns:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            try:
                groups = m.groups()
                if len(groups) == 3:
                    if groups[1].lower() in months:
                        return date(int(groups[2]), months[groups[1].lower()], int(groups[0]))
                    else:
                        return date(int(groups[0]), int(groups[1]), int(groups[2]))
            except Exception:
                pass
    return date.today()


def _extract_from_inline_ixbrl(soup: BeautifulSoup) -> dict[str, Optional[Decimal]]:
    """Handle inline iXBRL embedded in HTML (ix:nonFraction tags)."""
    from pipeline.parse.ixbrl_parser import CONCEPT_REGISTRY, _strip_namespace, _extract_numeric
    fields: dict[str, Optional[Decimal]] = {}
    employees: Optional[int] = None

    ix_elements = soup.find_all(attrs={"name": True})
    for el in ix_elements:
        name_attr = el.get("name", "")
        if not name_attr:
            continue
        stripped = _strip_namespace(name_attr)
        canonical = CONCEPT_REGISTRY.get(stripped)
        if not canonical:
            continue
        try:
            scale = int(el.get("scale", 0) or 0)
        except Exception:
            scale = 0
        sign = el.get("sign", "")
        raw = el.get_text(strip=True)
        val = _extract_numeric(raw, scale)
        if val is None:
            continue
        if sign == "-":
            val = -val
        if canonical == "employees":
            try:
                employees = int(val)
            except Exception:
                pass
        elif canonical in ("turnover", "total_assets", "net_assets", "total_liabilities"):
            existing = fields.get(canonical)
            if existing is None or abs(val) > abs(existing):
                fields[canonical] = val

    if employees is not None:
        fields["employees"] = Decimal(employees)
    return fields


def _extract_from_tables(soup: BeautifulSoup) -> dict[str, Optional[Decimal]]:
    """Extract financials from HTML tables with label/value patterns."""
    fields: dict[str, Optional[Decimal]] = {}
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            label_text = cells[0].get_text(strip=True)
            canonical = map_label_to_field(label_text)
            if not canonical:
                continue
            # Look at the last non-empty cell for the value
            for cell in reversed(cells[1:]):
                cell_text = cell.get_text(strip=True)
                if cell_text:
                    val = _parse_money(cell_text)
                    if val is not None and canonical not in fields:
                        fields[canonical] = val
                    break
    return fields


def parse_html(file_path: str, company_number: str) -> ParsedAccounts:
    """Parse an HTML accounts document."""
    try:
        with open(file_path, "rb") as f:
            content = f.read()
        soup = BeautifulSoup(content, "lxml")
        period_end = _get_period_end(soup, file_path)

        # First try inline iXBRL extraction
        fields = _extract_from_inline_ixbrl(soup)

        # Fall back to table extraction
        if len([v for v in fields.values() if v is not None]) < 2:
            table_fields = _extract_from_tables(soup)
            for k, v in table_fields.items():
                if k not in fields:
                    fields[k] = v

        found_count = sum(1 for v in fields.values() if v is not None)
        status = "ok" if found_count >= 2 else ("partial" if found_count == 1 else "failed")

        employees = None
        if fields.get("employees") is not None:
            try:
                employees = int(fields["employees"])
            except Exception:
                pass

        return ParsedAccounts(
            company_number=company_number,
            period_end=period_end,
            parse_source="html",
            parse_status=status,
            turnover=fields.get("turnover"),
            total_assets=fields.get("total_assets"),
            net_assets=fields.get("net_assets"),
            total_liabilities=fields.get("total_liabilities"),
            employees=employees,
        )

    except Exception as exc:
        logger.warning("HTML parse failed for %s: %s", file_path, exc)
        path = Path(file_path)
        try:
            period_end = date.fromisoformat(path.stem)
        except Exception:
            period_end = date.today()
        return ParsedAccounts(
            company_number=company_number,
            period_end=period_end,
            parse_source="html",
            parse_status="failed",
        )
