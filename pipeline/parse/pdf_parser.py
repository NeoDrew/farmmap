"""PDF account parser using pdfplumber."""
import logging
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional

import pdfplumber

from pipeline.parse.schema_mapper import ParsedAccounts, clean_decimal, map_label_to_field

logger = logging.getLogger(__name__)

# Patterns to match monetary values: £123,456 or 123,456 or (123,456) etc.
MONEY_PATTERN = re.compile(
    r"[£$]?\s*\(?\s*([\d,]+(?:\.\d+)?)\s*\)?(?:\s*[kKmMbB])?", re.IGNORECASE
)


def _extract_date_from_text(text: str) -> Optional[date]:
    """Try to extract a financial period end date from PDF text."""
    patterns = [
        r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b",
        r"\b(\d{2})/(\d{2})/(\d{4})\b",
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
                        d = date(int(groups[2]), months[groups[1].lower()], int(groups[0]))
                    elif len(groups[0]) == 4:  # YYYY-MM-DD
                        d = date(int(groups[0]), int(groups[1]), int(groups[2]))
                    else:
                        d = date(int(groups[2]), int(groups[1]), int(groups[0]))
                    if 2000 <= d.year <= 2030:
                        return d
            except Exception:
                pass
    return None


def _parse_money(text: str) -> Optional[Decimal]:
    """Parse a monetary string to Decimal."""
    text = text.strip()
    is_negative = text.startswith("(") or text.startswith("-")
    m = MONEY_PATTERN.search(text)
    if not m:
        return None
    val = clean_decimal(m.group(1))
    if val is None:
        return None
    # Handle k/M/B suffixes
    if text.upper().endswith("K"):
        val *= 1000
    elif text.upper().endswith("M"):
        val *= 1_000_000
    elif text.upper().endswith("B"):
        val *= 1_000_000_000
    return -val if is_negative else val


def _extract_from_tables(pdf: pdfplumber.PDF) -> dict[str, Optional[Decimal]]:
    """Attempt to extract financials from table structures."""
    fields: dict[str, Optional[Decimal]] = {}
    for page in pdf.pages:
        tables = page.extract_tables()
        for table in tables:
            for row in table:
                if not row or len(row) < 2:
                    continue
                label_cell = row[0]
                if not label_cell:
                    continue
                canonical = map_label_to_field(str(label_cell))
                if not canonical:
                    continue
                # Look for the rightmost non-empty numeric cell
                for cell in reversed(row[1:]):
                    if cell and str(cell).strip():
                        val = _parse_money(str(cell))
                        if val is not None and canonical not in fields:
                            fields[canonical] = val
                            break
    return fields


def _extract_from_text(text: str) -> dict[str, Optional[Decimal]]:
    """
    Fallback: search raw text for label + value patterns.
    Looks for lines like:
        Turnover                    123,456
        Net assets             £    98,765
    """
    fields: dict[str, Optional[Decimal]] = {}
    lines = text.splitlines()
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        canonical = map_label_to_field(line_stripped)
        if not canonical:
            # Check if label is embedded in a longer line
            for label, canon in {
                "turnover": "turnover",
                "net assets": "net_assets",
                "total assets": "total_assets",
                "total liabilities": "total_liabilities",
                "shareholders": "net_assets",
            }.items():
                if label in line_stripped.lower():
                    canonical = canon
                    break

        if canonical and canonical not in fields:
            # Try to find the value on the same line
            val = _parse_money(re.sub(r"[a-zA-Z\s:£$]+", " ", line_stripped).strip())
            if val is None and i + 1 < len(lines):
                val = _parse_money(lines[i + 1].strip())
            if val is not None:
                fields[canonical] = val
    return fields


def parse_pdf(file_path: str, company_number: str) -> ParsedAccounts:
    """Parse a PDF accounts document."""
    path = Path(file_path)
    try:
        period_end = date.fromisoformat(path.stem)
    except Exception:
        period_end = date.today()

    try:
        fields: dict[str, Optional[Decimal]] = {}
        doc_date: Optional[date] = None

        with pdfplumber.open(file_path) as pdf:
            # Try table extraction first
            table_fields = _extract_from_tables(pdf)
            fields.update(table_fields)

            # If we got nothing useful from tables, try text
            if len([v for v in fields.values() if v is not None]) < 2:
                full_text = "\n".join(
                    page.extract_text() or "" for page in pdf.pages
                )
                if full_text.strip():
                    text_fields = _extract_from_text(full_text)
                    for k, v in text_fields.items():
                        if k not in fields:
                            fields[k] = v
                    doc_date = _extract_date_from_text(full_text)

        if doc_date:
            period_end = doc_date

        found_count = sum(1 for v in fields.values() if v is not None)
        status = "ok" if found_count >= 2 else ("partial" if found_count == 1 else "failed")

        return ParsedAccounts(
            company_number=company_number,
            period_end=period_end,
            parse_source="pdf",
            parse_status=status,
            turnover=fields.get("turnover"),
            total_assets=fields.get("total_assets"),
            net_assets=fields.get("net_assets"),
            total_liabilities=fields.get("total_liabilities"),
            employees=int(fields["employees"]) if fields.get("employees") is not None else None,
        )

    except Exception as exc:
        logger.warning("PDF parse failed for %s: %s", file_path, exc)
        return ParsedAccounts(
            company_number=company_number,
            period_end=period_end,
            parse_source="pdf",
            parse_status="failed",
        )
