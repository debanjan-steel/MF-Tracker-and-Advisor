"""
mfapi_client.py — PRIMARY data source: MFAPI.in
Fetches mutual fund scheme master list and full historical daily NAVs.
Falls back to AMFI if this source fails (handled by data_manager.py).
"""

import logging
import time
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_URL = settings.mfapi_base_url          # https://api.mfapi.in/mf
SCHEME_SEARCH_URL = "https://api.mfapi.in/mf/search"
REQUEST_TIMEOUT = 15                         # seconds
RATE_LIMIT_DELAY = 0.3                       # seconds between bulk requests


# ---------------------------------------------------------------------------
# Retry decorator — retries up to 4 times with exponential backoff
# ---------------------------------------------------------------------------
@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError)),
    reraise=True,
)
def _get(url: str, params: Optional[dict] = None) -> dict | list:
    """Internal GET with retry logic. Raises on HTTP errors."""
    response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search_schemes(query: str) -> list[dict]:
    """
    Search mutual fund schemes by name or AMC using MFAPI search endpoint.

    Returns a list of dicts with keys:
        schemeCode (int), schemeName (str)

    Example:
        search_schemes("parag parikh") →
        [{"schemeCode": 122639, "schemeName": "Parag Parikh Flexi Cap Fund - Direct Plan - Growth"}]
    """
    try:
        results = _get(SCHEME_SEARCH_URL, params={"q": query})
        logger.info(f"[MFAPI] Search '{query}' returned {len(results)} results.")
        return results
    except Exception as e:
        logger.error(f"[MFAPI] search_schemes failed: {e}")
        raise


def fetch_scheme_metadata(scheme_code: int) -> dict:
    """
    Fetch scheme metadata and latest NAV for a single scheme.

    Returns top-level dict with keys:
        meta (dict): fund_house, scheme_type, scheme_category, scheme_name
        data (list): [{date, nav}] — most recent NAVs first

    Note: Returns ONLY the most recent NAV for quick lookups.
          Use fetch_full_nav_history() for complete historical data.
    """
    try:
        url = f"{BASE_URL}/{scheme_code}/latest"
        result = _get(url)
        logger.info(f"[MFAPI] Fetched latest NAV for scheme {scheme_code}: "
                    f"{result.get('data', [{}])[0].get('nav', 'N/A')}")
        return result
    except Exception as e:
        logger.error(f"[MFAPI] fetch_scheme_metadata({scheme_code}) failed: {e}")
        raise


def fetch_full_nav_history(scheme_code: int) -> dict:
    """
    Fetch complete historical daily NAV series for a scheme from inception to today.

    Returns dict with keys:
        meta: {fund_house, scheme_type, scheme_category, scheme_name, scheme_code}
        data: [{date: "DD-MM-YYYY", nav: "142.8500"}, ...] — newest first

    The data list can span 10–25 years for older funds (~2500–6000 rows).
    """
    try:
        url = f"{BASE_URL}/{scheme_code}"
        result = _get(url)
        nav_count = len(result.get("data", []))
        meta = result.get("meta", {})
        logger.info(
            f"[MFAPI] Fetched {nav_count} NAV records for "
            f"'{meta.get('scheme_name', scheme_code)}' (code: {scheme_code})."
        )
        return result
    except Exception as e:
        logger.error(f"[MFAPI] fetch_full_nav_history({scheme_code}) failed: {e}")
        raise


def fetch_multiple_schemes(scheme_codes: list[int], delay: float = RATE_LIMIT_DELAY) -> dict[int, dict]:
    """
    Batch fetch full NAV history for multiple scheme codes.
    Applies a small delay between requests to avoid rate-limiting.

    Returns:
        {scheme_code: nav_history_dict} — failed codes are omitted and logged.
    """
    results = {}
    total = len(scheme_codes)
    for idx, code in enumerate(scheme_codes, 1):
        try:
            results[code] = fetch_full_nav_history(code)
            logger.info(f"[MFAPI] Batch progress: {idx}/{total} schemes fetched.")
        except Exception as e:
            logger.warning(f"[MFAPI] Skipping scheme {code} in batch due to error: {e}")
        if idx < total:
            time.sleep(delay)
    return results


def get_all_scheme_codes() -> list[dict]:
    """
    Retrieve the master list of ALL active Indian mutual fund scheme codes from MFAPI.

    Returns a flat list of dicts:
        [{"schemeCode": 122639, "schemeName": "..."}, ...]

    This is the definitive scheme master — use this to seed the local DB.
    """
    try:
        # MFAPI returns the full scheme master when no search query is provided
        result = _get(BASE_URL)
        logger.info(f"[MFAPI] Scheme master fetched: {len(result)} total schemes.")
        return result
    except Exception as e:
        logger.error(f"[MFAPI] get_all_scheme_codes() failed: {e}")
        raise

