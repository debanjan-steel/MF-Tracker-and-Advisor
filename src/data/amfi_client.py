"""
amfi_client.py — SECONDARY & VERIFICATION data source: AMFI India Official Portal
Provides fallback NAV data and cross-verification against MFAPI.

AMFI (Association of Mutual Funds in India) is the statutory body under SEBI.
All commercial platforms (Groww, Zerodha, MFAPI) derive their data from AMFI.
This client reads the official daily NAVAll.txt feed directly.
"""

import logging
import io
from datetime import datetime
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
NAV_ALL_URL = settings.amfi_nav_url          # https://portal.amfiindia.com/spages/NAVAll.txt
REQUEST_TIMEOUT = 30                          # NAVAll.txt is ~3MB so allow more time
NAV_DISCREPANCY_THRESHOLD = 0.01             # Flag if difference > 0.01%

# AMFI NAVAll.txt line format:
# SchemeCode;ISINDivPayoutISINGrowth;ISINDivReinvestment;SchemeName;NetAssetValue;Date
# Example:
# 100006;INF846K01EW2;INF846K01EX0;Aditya Birla Sun Life Banking & PSU Debt Fund;567.1234;31-Oct-2026
FIELD_SCHEME_CODE = 0
FIELD_SCHEME_NAME = 3
FIELD_NAV = 4
FIELD_DATE = 5


# ---------------------------------------------------------------------------
# Retry decorator
# ---------------------------------------------------------------------------
@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=3, max=60),
    retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError)),
    reraise=True,
)
def _fetch_nav_all_raw() -> str:
    """Download the raw AMFI NAVAll.txt content."""
    response = requests.get(NAV_ALL_URL, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.text


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def fetch_and_parse_nav_all() -> dict[int, dict]:
    """
    Download and parse the AMFI NAVAll.txt daily feed.
    Returns a lookup dict of {scheme_code: {name, nav, date}} for ALL schemes.

    This is the official SEBI-mandated data and serves as ground truth.
    Updated by AMFI every business day between 9 PM – 11 PM IST.

    Returns:
        {
            122639: {
                "scheme_code": 122639,
                "scheme_name": "Parag Parikh Flexi Cap Fund...",
                "nav": 78.4200,
                "date": "2026-10-31",
            },
            ...
        }
    """
    try:
        raw_text = _fetch_nav_all_raw()
        return _parse_nav_all(raw_text)
    except Exception as e:
        logger.error(f"[AMFI] fetch_and_parse_nav_all() failed: {e}")
        raise


def _parse_nav_all(raw_text: str) -> dict[int, dict]:
    """
    Parse the semicolon-delimited NAVAll.txt content into a structured dict.
    Skips header lines and invalid rows silently.
    """
    nav_lookup: dict[int, dict] = {}
    lines = raw_text.splitlines()
    parsed_count = 0
    skipped_count = 0

    for line in lines:
        line = line.strip()
        # Skip blank lines, category headers (no semicolons), and column headers
        if not line or ";" not in line or line.startswith("Scheme Code"):
            continue

        parts = line.split(";")
        if len(parts) < 6:
            skipped_count += 1
            continue

        try:
            scheme_code = int(parts[FIELD_SCHEME_CODE].strip())
            nav_str = parts[FIELD_NAV].strip()
            date_str = parts[FIELD_DATE].strip()

            # Skip N.A. NAVs (closed / suspended schemes)
            if nav_str.upper() in ("N.A.", "NA", "-", ""):
                skipped_count += 1
                continue

            nav_value = float(nav_str)
            # Normalise date to ISO format YYYY-MM-DD
            nav_date = _normalise_date(date_str)

            nav_lookup[scheme_code] = {
                "scheme_code": scheme_code,
                "scheme_name": parts[FIELD_SCHEME_NAME].strip(),
                "nav": nav_value,
                "date": nav_date,
            }
            parsed_count += 1

        except (ValueError, IndexError):
            skipped_count += 1
            continue

    logger.info(
        f"[AMFI] NAVAll.txt parsed: {parsed_count} valid schemes, "
        f"{skipped_count} rows skipped."
    )
    return nav_lookup


def _normalise_date(date_str: str) -> str:
    """
    Convert AMFI date formats to ISO 8601 (YYYY-MM-DD).
    AMFI uses: '31-Oct-2026' or '31/10/2026'
    """
    for fmt in ("%d-%b-%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    logger.warning(f"[AMFI] Unrecognised date format: '{date_str}' — returning raw.")
    return date_str


def get_latest_nav(scheme_code: int, nav_lookup: Optional[dict] = None) -> Optional[dict]:
    """
    Get latest NAV for a single scheme from AMFI.
    Optionally accepts a pre-fetched nav_lookup to avoid re-downloading NAVAll.txt.

    Returns:
        {"scheme_code": int, "scheme_name": str, "nav": float, "date": str} or None
    """
    if nav_lookup is None:
        nav_lookup = fetch_and_parse_nav_all()
    result = nav_lookup.get(scheme_code)
    if result is None:
        logger.warning(f"[AMFI] Scheme code {scheme_code} not found in NAVAll.txt.")
    return result


# ---------------------------------------------------------------------------
# Cross-Verification
# ---------------------------------------------------------------------------

def verify_nav(
    scheme_code: int,
    mfapi_nav: float,
    mfapi_date: str,
    amfi_nav_lookup: Optional[dict] = None,
) -> dict:
    """
    Cross-verify the NAV reported by MFAPI against the official AMFI value.

    Returns a verification result dict:
        {
            "scheme_code": int,
            "mfapi_nav": float,
            "amfi_nav": float,
            "discrepancy_pct": float,
            "flag": bool,          # True if discrepancy > threshold
            "authoritative_nav": float,  # AMFI value takes precedence if flagged
            "verified_date": str,
        }
    """
    if amfi_nav_lookup is None:
        amfi_nav_lookup = fetch_and_parse_nav_all()

    amfi_record = amfi_nav_lookup.get(scheme_code)
    if amfi_record is None:
        logger.warning(f"[AMFI] Cannot verify scheme {scheme_code}: not in AMFI feed.")
        return {
            "scheme_code": scheme_code,
            "mfapi_nav": mfapi_nav,
            "amfi_nav": None,
            "discrepancy_pct": None,
            "flag": False,
            "authoritative_nav": mfapi_nav,
            "verified_date": mfapi_date,
            "status": "AMFI_NOT_FOUND",
        }

    amfi_nav = amfi_record["nav"]
    discrepancy_pct = abs(mfapi_nav - amfi_nav) / amfi_nav * 100 if amfi_nav else 0
    flagged = discrepancy_pct > NAV_DISCREPANCY_THRESHOLD

    if flagged:
        logger.warning(
            f"[AMFI] ⚠️ NAV discrepancy for scheme {scheme_code}: "
            f"MFAPI={mfapi_nav}, AMFI={amfi_nav} "
            f"(diff={discrepancy_pct:.4f}%). Using AMFI value."
        )

    return {
        "scheme_code": scheme_code,
        "mfapi_nav": mfapi_nav,
        "amfi_nav": amfi_nav,
        "discrepancy_pct": round(discrepancy_pct, 6),
        "flag": flagged,
        "authoritative_nav": amfi_nav if flagged else mfapi_nav,
        "verified_date": amfi_record["date"],
        "status": "DISCREPANCY_FLAGGED" if flagged else "VERIFIED_OK",
    }

