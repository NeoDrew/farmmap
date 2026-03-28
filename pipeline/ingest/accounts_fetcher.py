"""Download Companies House account documents with SQLite manifest tracking."""
import logging
import os
import sqlite3
from pathlib import Path
from typing import Any, Optional

import httpx
import pdfplumber

logger = logging.getLogger(__name__)

ACCOUNTS_DIR = Path("data/accounts")
MANIFEST_DB = Path("data/cache/download_manifest.db")
DOCUMENT_API = "https://document-api.company-information.service.gov.uk"
CH_API_BASE = "https://api.company-information.service.gov.uk"


def _get_manifest_conn() -> sqlite3.Connection:
    MANIFEST_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(MANIFEST_DB))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS downloads (
            company_number TEXT,
            filing_date TEXT,
            file_path TEXT,
            content_type TEXT,
            status TEXT,
            PRIMARY KEY (company_number, filing_date)
        )
        """
    )
    conn.commit()
    return conn


def _is_already_downloaded(conn: sqlite3.Connection, company_number: str, filing_date: str) -> Optional[str]:
    row = conn.execute(
        "SELECT file_path FROM downloads WHERE company_number=? AND filing_date=? AND status='ok'",
        (company_number, filing_date),
    ).fetchone()
    return row[0] if row else None


def _record_download(
    conn: sqlite3.Connection,
    company_number: str,
    filing_date: str,
    file_path: str,
    content_type: str,
    status: str,
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO downloads (company_number, filing_date, file_path, content_type, status)
        VALUES (?, ?, ?, ?, ?)
        """,
        (company_number, filing_date, file_path, content_type, status),
    )
    conn.commit()


def _detect_format(content_type: str, file_path: str) -> str:
    """Determine format from content-type header."""
    ct = content_type.lower()
    if "xhtml" in ct or "xml" in ct:
        return "ixbrl"
    if "pdf" in ct:
        return "pdf"
    if "html" in ct or "text" in ct:
        return "html"
    # Fallback: check file extension
    ext = Path(file_path).suffix.lower()
    if ext in (".xhtml", ".xml"):
        return "ixbrl"
    if ext == ".pdf":
        return "pdf"
    return "html"


def _is_image_only_pdf(file_path: str) -> bool:
    """Return True if PDF is image-only (no extractable text)."""
    try:
        with pdfplumber.open(file_path) as pdf:
            text = ""
            for page in pdf.pages[:3]:
                text += page.extract_text() or ""
            return len(text.strip()) < 50
    except Exception:
        return True


async def fetch_accounts_for_company(
    client: httpx.AsyncClient,
    company_number: str,
    filing: dict[str, Any],
    manifest_conn: sqlite3.Connection,
) -> Optional[dict[str, Any]]:
    """
    Download the account document for a single filing.
    Returns metadata dict with file_path, format, status.
    """
    filing_date = filing.get("date", "unknown")
    cached = _is_already_downloaded(manifest_conn, company_number, filing_date)
    if cached and Path(cached).exists():
        logger.debug("Using cached %s/%s", company_number, filing_date)
        content_type = manifest_conn.execute(
            "SELECT content_type FROM downloads WHERE company_number=? AND filing_date=?",
            (company_number, filing_date),
        ).fetchone()
        ct = content_type[0] if content_type else "application/pdf"
        fmt = _detect_format(ct, cached)
        return {"file_path": cached, "format": fmt, "company_number": company_number, "period_end": filing_date}

    links = filing.get("links", {})
    doc_meta_url = links.get("document_metadata")
    if not doc_meta_url:
        logger.warning("No document_metadata link for %s/%s", company_number, filing_date)
        return None

    try:
        # Get document metadata to find download URL
        api_key = os.getenv("CH_API_KEY", "")
        auth = httpx.BasicAuth(username=api_key, password="") if api_key else None
        meta_resp = await client.get(doc_meta_url, auth=auth)
        if meta_resp.status_code == 404:
            return None
        meta_resp.raise_for_status()
        meta = meta_resp.json()

        # Find the best resource to download
        resources = meta.get("resources", {})
        download_url = None
        content_type = "application/pdf"
        for res_type, res_info in resources.items():
            if "xhtml" in res_type or "xml" in res_type:
                download_url = res_info.get("href") or res_info
                content_type = res_type
                break
            if "pdf" in res_type and not download_url:
                download_url = res_info.get("href") or res_info
                content_type = res_type
            if "html" in res_type and not download_url:
                download_url = res_info.get("href") or res_info
                content_type = res_type

        if not download_url:
            # Try direct links
            download_url = links.get("self", "")
            if not download_url:
                return None

        # Download the document
        ext = ".xhtml" if "xhtml" in content_type else (".pdf" if "pdf" in content_type else ".html")
        company_dir = ACCOUNTS_DIR / company_number
        company_dir.mkdir(parents=True, exist_ok=True)
        file_path = str(company_dir / f"{filing_date}{ext}")

        doc_resp = await client.get(download_url, auth=auth)
        doc_resp.raise_for_status()
        with open(file_path, "wb") as f:
            f.write(doc_resp.content)

        fmt = _detect_format(content_type, file_path)

        # Check for image-only PDFs
        if fmt == "pdf" and _is_image_only_pdf(file_path):
            _record_download(manifest_conn, company_number, filing_date, file_path, content_type, "image_pdf")
            return {"file_path": file_path, "format": "image_pdf", "company_number": company_number, "period_end": filing_date}

        _record_download(manifest_conn, company_number, filing_date, file_path, content_type, "ok")
        return {"file_path": file_path, "format": fmt, "company_number": company_number, "period_end": filing_date}

    except httpx.HTTPStatusError as exc:
        logger.warning("HTTP error fetching %s/%s: %s", company_number, filing_date, exc)
        _record_download(manifest_conn, company_number, filing_date, "", "", "http_error")
        return None
    except Exception as exc:
        logger.warning("Error fetching %s/%s: %s", company_number, filing_date, exc)
        return None
