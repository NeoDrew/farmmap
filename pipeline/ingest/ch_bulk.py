"""Download and filter Companies House bulk data for farm SIC codes."""
import io
import logging
import zipfile
from pathlib import Path
from typing import Optional

import httpx
import pandas as pd

logger = logging.getLogger(__name__)

CH_BULK_BASE = "https://download.companieshouse.gov.uk"
OUTPUT_FILE = Path("data/parquet/companies_farm.parquet")
RAW_DIR = Path("data/raw")

# Farm SIC codes: arable, horticulture, livestock, mixed, support activities
FARM_SIC_CODES = {
    "01110", "01120", "01130", "01140", "01150", "01160", "01190",
    "01210", "01220", "01230", "01240", "01250", "01260", "01270", "01280", "01290",
    "01300",
    "01410", "01420", "01430", "01440", "01450", "01460", "01470", "01490",
    "01500",
    "01610", "01620", "01630", "01640",
}

KEEP_COLUMNS = [
    "CompanyNumber",
    "CompanyName",
    "CompanyStatus",
    "RegAddress.CareOf",
    "RegAddress.POBox",
    "RegAddress.AddressLine1",
    "RegAddress.AddressLine2",
    "RegAddress.PostTown",
    "RegAddress.County",
    "RegAddress.Country",
    "RegAddress.PostCode",
    "SICCode.SicText_1",
    "SICCode.SicText_2",
    "SICCode.SicText_3",
    "SICCode.SicText_4",
    "Accounts.AccountRefDay",
    "Accounts.AccountRefMonth",
    "Accounts.NextDueDate",
    "Accounts.LastMadeUpDate",
    "Accounts.AccountCategory",
]


def _extract_sic_code(sic_text: Optional[str]) -> Optional[str]:
    """Extract 5-digit SIC code from text like '01110 - Growing of cereals'."""
    if not sic_text or not isinstance(sic_text, str):
        return None
    code = sic_text.strip()[:5]
    return code if code.isdigit() else None


def _is_farm_company(row: pd.Series) -> bool:
    for col in ["SICCode.SicText_1", "SICCode.SicText_2", "SICCode.SicText_3", "SICCode.SicText_4"]:
        code = _extract_sic_code(row.get(col))
        if code and code in FARM_SIC_CODES:
            return True
    return False


def _build_address_json(row: pd.Series) -> dict:
    return {
        "care_of": row.get("RegAddress.CareOf"),
        "po_box": row.get("RegAddress.POBox"),
        "line1": row.get("RegAddress.AddressLine1"),
        "line2": row.get("RegAddress.AddressLine2"),
        "town": row.get("RegAddress.PostTown"),
        "county": row.get("RegAddress.County"),
        "country": row.get("RegAddress.Country"),
        "postcode": row.get("RegAddress.PostCode"),
    }


def _get_sic_codes(row: pd.Series) -> list[str]:
    codes = []
    for col in ["SICCode.SicText_1", "SICCode.SicText_2", "SICCode.SicText_3", "SICCode.SicText_4"]:
        code = _extract_sic_code(row.get(col))
        if code:
            codes.append(code)
    return codes


async def download_and_filter(
    part_urls: Optional[list[str]] = None,
) -> pd.DataFrame:
    """
    Download CH bulk CSV snapshot(s), filter to active farm companies,
    and save to parquet. Returns the filtered DataFrame.
    """
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if part_urls is None:
        part_urls = await _discover_bulk_urls()

    all_chunks: list[pd.DataFrame] = []

    async with httpx.AsyncClient(timeout=600, follow_redirects=True) as client:
        for url in part_urls:
            filename = url.split("/")[-1]
            local_path = RAW_DIR / filename
            if not local_path.exists():
                logger.info("Downloading %s ...", url)
                async with client.stream("GET", url) as resp:
                    resp.raise_for_status()
                    with open(local_path, "wb") as f:
                        async for chunk in resp.aiter_bytes(chunk_size=65536):
                            f.write(chunk)
                logger.info("Saved %s", local_path)
            else:
                logger.info("Using cached %s", local_path)

            logger.info("Filtering %s for farm SIC codes...", filename)
            farm_rows = _filter_csv_zip(local_path)
            all_chunks.append(farm_rows)
            logger.info("Found %d farm companies in %s", len(farm_rows), filename)

    combined = pd.concat(all_chunks, ignore_index=True) if all_chunks else pd.DataFrame()
    if combined.empty:
        logger.warning("No farm companies found in bulk data!")
        return combined

    # Deduplicate by CompanyNumber
    combined = combined.drop_duplicates(subset="CompanyNumber")
    logger.info("Total unique farm companies: %d", len(combined))
    combined.to_parquet(OUTPUT_FILE, index=False)
    return combined


def _filter_csv_zip(zip_path: Path) -> pd.DataFrame:
    """Read a CH bulk zip file and return only active farm company rows."""
    farm_rows = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
        if not csv_names:
            logger.warning("No CSV found in %s", zip_path)
            return pd.DataFrame()
        csv_name = csv_names[0]
        with zf.open(csv_name) as f:
            for chunk in pd.read_csv(
                f,
                chunksize=50_000,
                low_memory=False,
                dtype=str,
                on_bad_lines="skip",
            ):
                chunk.columns = chunk.columns.str.strip()
                # Filter active companies only
                if "CompanyStatus" in chunk.columns:
                    chunk = chunk[chunk["CompanyStatus"].str.strip().str.lower() == "active"]
                # Filter farm SIC codes
                farm_mask = chunk.apply(_is_farm_company, axis=1)
                farm_rows.append(chunk[farm_mask])
    if not farm_rows:
        return pd.DataFrame()
    return pd.concat(farm_rows, ignore_index=True)


async def _discover_bulk_urls() -> list[str]:
    """
    Discover the current bulk data download URLs from Companies House.
    Falls back to constructing likely URLs if scraping fails.
    """
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{CH_BULK_BASE}/en_output.aspx")
            resp.raise_for_status()
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "lxml")
            links = [
                a["href"]
                for a in soup.find_all("a", href=True)
                if "BasicCompanyData" in a["href"] and a["href"].endswith(".zip")
            ]
            if links:
                urls = [
                    lnk if lnk.startswith("http") else f"{CH_BULK_BASE}/{lnk.lstrip('/')}"
                    for lnk in links
                ]
                logger.info("Discovered %d bulk URLs: %s", len(urls), urls)
                return urls
    except Exception as exc:
        logger.warning("Failed to discover bulk URLs from CH website: %s", exc)

    # Fallback: CH bulk data is published monthly, typically named with the 1st of the month.
    # Try the current month, then the previous month.
    from datetime import date
    from dateutil.relativedelta import relativedelta
    today = date.today()
    candidates = []
    for months_back in range(0, 3):
        d = today - relativedelta(months=months_back)
        # CH uses first day of month
        for day in [1]:
            date_str = d.replace(day=day).strftime("%Y-%m-%d")
            candidates.append(f"{CH_BULK_BASE}/BasicCompanyDataAsOneFile-{date_str}.zip")
        # Also try part files (CH splits into parts when large)
        for part in range(1, 7):
            date_str = d.replace(day=1).strftime("%Y-%m-%d")
            candidates.append(f"{CH_BULK_BASE}/BasicCompanyData-{date_str}-part{part}_{part}.zip")
    # Verify which URL actually exists
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for url in candidates:
            try:
                resp = await client.head(url)
                if resp.status_code == 200:
                    logger.info("Found bulk data at: %s", url)
                    return [url]
            except Exception:
                continue
    logger.warning("Could not find bulk data URL, trying first candidate: %s", candidates[0])
    return [candidates[0]]


def load_parquet() -> pd.DataFrame:
    """Load the cached farm companies parquet."""
    if OUTPUT_FILE.exists():
        return pd.read_parquet(OUTPUT_FILE)
    raise FileNotFoundError(f"Parquet not found at {OUTPUT_FILE}. Run download_and_filter() first.")
