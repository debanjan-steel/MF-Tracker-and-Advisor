"""
data_manager.py — Resilient Ingestion Controller
Implements: Primary (MFAPI) → Fallback (AMFI) + Cross-Verification logic.
All data access in the application should go through this manager.
"""

import logging
from typing import Optional

from src.data.mfapi_client import (
    fetch_full_nav_history,
    fetch_scheme_metadata,
    search_schemes,
    get_all_scheme_codes,
)
from src.data.amfi_client import (
    fetch_and_parse_nav_all,
    get_latest_nav,
    verify_nav,
)

logger = logging.getLogger(__name__)


class DataManager:
    """
    Central data access gateway for all mutual fund NAV data.

    Strategy:
        1. Try Primary (MFAPI) — fast, structured JSON.
        2. On failure → Fall back to Secondary (AMFI official feed).
        3. On success → Cross-verify latest NAV between MFAPI and AMFI.
           If discrepancy > 0.01%, AMFI value is authoritative.
    """

    def __init__(self):
        self._amfi_cache: Optional[dict] = None  # In-memory cache for today's AMFI feed
        self._scheme_master_cache: Optional[list[dict]] = None

    # ------------------------------------------------------------------
    # AMFI feed — cached for the session to avoid repeated 3 MB downloads
    # ------------------------------------------------------------------

    def _get_amfi_feed(self, force_refresh: bool = False) -> dict:
        """Return cached AMFI NAVAll.txt or fetch fresh if needed."""
        if self._amfi_cache is None or force_refresh:
            logger.info("[DataManager] Fetching fresh AMFI NAVAll.txt feed.")
            self._amfi_cache = fetch_and_parse_nav_all()
        return self._amfi_cache

    # ------------------------------------------------------------------
    # Scheme Search — Smart token-based fuzzy matching
    # ------------------------------------------------------------------

    def _normalize_search_text(self, text: str) -> str:
        import re
        t = text.lower()
        t = re.sub(r'mid\s+cap', 'midcap', t)
        t = re.sub(r'small\s+cap', 'smallcap', t)
        t = re.sub(r'large\s+cap', 'largecap', t)
        t = re.sub(r'flexi\s+cap', 'flexicap', t)
        t = re.sub(r'multi\s+cap', 'multicap', t)
        return t

    def search(self, query: str) -> list[dict]:
        """
        Fuzzy, relaxed, token-based mutual fund search.
        Handles variations like 'mid cap' vs 'midcap', filler words ('fund'),
        and word order flexibility across all Indian mutual fund schemes.
        """
        if not query or len(query.strip()) < 2:
            return []

        import re
        logger.info(f"[DataManager] Smart searching for: '{query}'")

        # Load master list if not cached
        if self._scheme_master_cache is None:
            try:
                self._scheme_master_cache = get_all_scheme_codes()
            except Exception as e:
                logger.warning(f"[DataManager] Failed to load full scheme master: {e}")
                return search_schemes(query)

        norm_q = self._normalize_search_text(query.strip())
        raw_tokens = [tok for tok in re.split(r'[^a-z0-9]+', norm_q) if tok]
        significant_tokens = [tok for tok in raw_tokens if tok not in {'fund', 'mf', 'scheme', 'mutual'}]
        tokens = significant_tokens if significant_tokens else raw_tokens

        results = []
        for item in self._scheme_master_cache:
            name = item.get("schemeName") or item.get("scheme_name") or ""
            norm_name = self._normalize_search_text(name)

            if all(tok in norm_name for tok in tokens):
                score = 0
                if "direct" in norm_name:
                    score += 20
                if "growth" in norm_name:
                    score += 10
                if norm_q in norm_name:
                    score += 30
                score -= len(norm_name) * 0.05
                results.append((score, item))

        # Fallback if no exact match: allow one missing token for long queries
        if not results and len(tokens) > 2:
            for item in self._scheme_master_cache:
                name = item.get("schemeName") or item.get("scheme_name") or ""
                norm_name = self._normalize_search_text(name)
                matched_count = sum(1 for tok in tokens if tok in norm_name)
                if matched_count >= len(tokens) - 1:
                    score = matched_count * 5
                    if "direct" in norm_name:
                        score += 20
                    if "growth" in norm_name:
                        score += 10
                    results.append((score, item))

        results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in results[:30]]

    def get_scheme_master(self) -> list[dict]:
        """Return the complete master list of all AMFI-registered mutual fund schemes."""
        logger.info("[DataManager] Fetching full scheme master from MFAPI.")
        return get_all_scheme_codes()

    def get_scheme_metadata(self, scheme_code: int) -> dict:
        """Fetch metadata for a scheme."""
        from src.data.storage import get_scheme
        cached = get_scheme(scheme_code)
        if cached:
            return cached
        res = fetch_scheme_metadata(scheme_code)
        return res.get("meta", {})

    # ------------------------------------------------------------------
    # NAV History — Primary with Fallback
    # ------------------------------------------------------------------

    def get_nav_history(self, scheme_code: int) -> dict:
        """
        Fetch full historical NAV series for a scheme.
        Primary: MFAPI. Fallback: AMFI (only provides current day NAV;
        full historical from AMFI is not directly available, so fallback
        returns the latest NAV in a normalised format).

        Returns:
            {
                "meta": {...},
                "data": [{"date": "YYYY-MM-DD", "nav": float}, ...],
                "source": "MFAPI" | "AMFI_FALLBACK",
            }
        """
        # --- Primary attempt ---
        try:
            result = fetch_full_nav_history(scheme_code)
            normalised = self._normalise_mfapi_history(result, scheme_code)
            # Cross-verify latest NAV
            if normalised["data"]:
                latest = normalised["data"][0]
                verification = verify_nav(
                    scheme_code=scheme_code,
                    mfapi_nav=latest["nav"],
                    mfapi_date=latest["date"],
                    amfi_nav_lookup=self._get_amfi_feed(),
                )
                if verification["flag"]:
                    logger.warning(
                        f"[DataManager] NAV discrepancy detected for {scheme_code}. "
                        f"Correcting latest NAV from {latest['nav']} to {verification['authoritative_nav']}."
                    )
                    normalised["data"][0]["nav"] = verification["authoritative_nav"]
                    normalised["data"][0]["nav_verified"] = True
            normalised["source"] = "MFAPI"
            return normalised

        except Exception as primary_error:
            logger.warning(
                f"[DataManager] Primary (MFAPI) failed for scheme {scheme_code}: "
                f"{primary_error}. Attempting AMFI fallback."
            )

        # --- AMFI Fallback (current day NAV only) ---
        try:
            amfi_feed = self._get_amfi_feed()
            amfi_record = get_latest_nav(scheme_code, amfi_feed)
            if amfi_record is None:
                raise ValueError(f"Scheme {scheme_code} not found in AMFI feed.")
            return {
                "meta": {
                    "scheme_code": scheme_code,
                    "scheme_name": amfi_record["scheme_name"],
                    "fund_house": "N/A (AMFI fallback)",
                    "scheme_type": "N/A",
                    "scheme_category": "N/A",
                },
                "data": [{"date": amfi_record["date"], "nav": amfi_record["nav"], "nav_verified": True}],
                "source": "AMFI_FALLBACK",
                "warning": "Only latest NAV available via AMFI fallback. MFAPI was unreachable.",
            }
        except Exception as fallback_error:
            logger.error(
                f"[DataManager] Both primary and fallback failed for scheme {scheme_code}. "
                f"AMFI error: {fallback_error}"
            )
            raise RuntimeError(
                f"Unable to fetch NAV data for scheme {scheme_code}. "
                f"Both MFAPI and AMFI sources are unavailable."
            ) from fallback_error

    # ------------------------------------------------------------------
    # Latest NAV Only
    # ------------------------------------------------------------------

    def get_latest_nav(self, scheme_code: int) -> dict:
        """
        Get only the latest NAV for a scheme (fast, single record).
        Always cross-verifies against AMFI.
        """
        try:
            result = fetch_scheme_metadata(scheme_code)
            if not result.get("data"):
                raise ValueError("Empty data from MFAPI latest endpoint.")
            latest = result["data"][0]
            mfapi_nav = float(latest["nav"])
            mfapi_date = self._convert_date(latest["date"])
            verification = verify_nav(
                scheme_code=scheme_code,
                mfapi_nav=mfapi_nav,
                mfapi_date=mfapi_date,
                amfi_nav_lookup=self._get_amfi_feed(),
            )
            return {
                "scheme_code": scheme_code,
                "scheme_name": result.get("meta", {}).get("scheme_name", ""),
                "nav": verification["authoritative_nav"],
                "date": verification["verified_date"],
                "source": "MFAPI+AMFI_VERIFIED",
                "verification": verification,
            }
        except Exception as e:
            logger.warning(f"[DataManager] get_latest_nav MFAPI failed ({e}). Falling back to AMFI.")
            amfi_feed = self._get_amfi_feed()
            record = get_latest_nav(scheme_code, amfi_feed)
            if not record:
                raise RuntimeError(f"Cannot get latest NAV for scheme {scheme_code}.")
            return {**record, "source": "AMFI_FALLBACK"}

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_mfapi_history(raw: dict, scheme_code: int) -> dict:
        """
        Normalise MFAPI response: convert dates to ISO format and nav to float.
        Returns the same structure with clean types.
        """
        from src.data.amfi_client import _normalise_date
        normalised_data = []
        for record in raw.get("data", []):
            try:
                normalised_data.append({
                    "date": _normalise_date(record["date"]),
                    "nav": float(record["nav"]),
                    "nav_verified": False,
                })
            except (KeyError, ValueError):
                continue
        return {
            "meta": raw.get("meta", {}),
            "data": normalised_data,
        }

    @staticmethod
    def _convert_date(date_str: str) -> str:
        """Convert DD-MM-YYYY (MFAPI format) to YYYY-MM-DD."""
        from src.data.amfi_client import _normalise_date
        return _normalise_date(date_str)


# Module-level singleton — import and use directly
data_manager = DataManager()

