"""
src/data/migration_transformer.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Universal Schema Evolution & Backward-Compatibility Normalizer.

Ensures that whenever data formats change or updates are released:
  1. Old saved items (holdings, plans, goals, watchlists, settings) are
     automatically detected, migrated, and upgraded to the current format.
  2. Legacy field aliases (e.g. `invested` vs `invested_amount`, `target_amount` vs `target_corpus`)
     are seamlessly reconciled with zero data loss.
  3. Corrupted or missing fields are safely backfilled with smart defaults.
"""

from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

CURRENT_SCHEMA_VERSION = 3


# ─────────────────────────────────────────────────────────────────────────────
# 1. Mutual Fund Holdings Migration & Normalization
# ─────────────────────────────────────────────────────────────────────────────

def normalize_holding(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transforms any raw holding from any previous app version into the current canonical format.
    - Resolves field renames: `invested` <-> `invested_amount`, `nav` <-> `avg_nav`
    - Computes missing units or avg_nav
    - Infers missing asset category from scheme name
    - Ensures valid numeric types and standard ISO dates
    """
    if not isinstance(raw, dict):
        return {}

    # 1. Scheme code & name
    try:
        scheme_code = int(raw.get("scheme_code") or raw.get("amfi_code") or raw.get("code") or 0)
    except (ValueError, TypeError):
        scheme_code = 0

    scheme_name = str(raw.get("scheme_name") or raw.get("name") or "Mutual Fund Scheme").strip()

    # 2. Invested amount & units
    invested = 0.0
    for key in ("invested_amount", "invested", "investment", "cost"):
        if raw.get(key) is not None:
            try:
                invested = float(raw[key])
                break
            except (ValueError, TypeError):
                pass

    units = 0.0
    for key in ("units", "close_units", "quantity", "shares"):
        if raw.get(key) is not None:
            try:
                units = float(raw[key])
                break
            except (ValueError, TypeError):
                pass

    avg_nav = 0.0
    for key in ("avg_nav", "buy_nav", "purchase_nav", "nav"):
        if raw.get(key) is not None:
            try:
                avg_nav = float(raw[key])
                break
            except (ValueError, TypeError):
                pass

    # Reconcile units & avg_nav if either is zero
    if units > 0 and avg_nav > 0 and invested <= 0:
        invested = units * avg_nav
    elif invested > 0 and avg_nav > 0 and units <= 0:
        units = invested / avg_nav
    elif invested > 0 and units > 0 and avg_nav <= 0:
        avg_nav = invested / units
    elif avg_nav <= 0:
        avg_nav = 10.0
        if units <= 0 and invested > 0:
            units = invested / 10.0

    # 3. Category inference if missing or generic
    category = str(raw.get("category") or raw.get("scheme_category") or "").strip()
    if not category or category.lower() in ("unknown", "other", "generic", "none"):
        name_lower = scheme_name.lower()
        if "small" in name_lower:
            category = "Small Cap"
        elif "mid" in name_lower:
            category = "Mid Cap"
        elif "large" in name_lower:
            category = "Large Cap"
        elif "flexi" in name_lower:
            category = "Flexi Cap"
        elif "liquid" in name_lower or "overnight" in name_lower:
            category = "Liquid / Debt"
        elif "debt" in name_lower or "bond" in name_lower or "gilt" in name_lower:
            category = "Debt"
        elif "hybrid" in name_lower or "balanced" in name_lower:
            category = "Hybrid"
        elif "arbitrage" in name_lower:
            category = "Arbitrage"
        else:
            category = "Equity"

    # 4. Investment type & dates
    inv_type = str(raw.get("investment_type") or "LUMPSUM").upper().strip()
    if inv_type not in ("SIP", "LUMPSUM"):
        inv_type = "LUMPSUM"

    inv_date = raw.get("investment_date")
    if inv_date is not None:
        inv_date = str(inv_date).strip()[:10]  # Ensure YYYY-MM-DD
    else:
        inv_date = ""

    holding_id = str(raw.get("id") or raw.get("holding_id") or uuid.uuid4().hex)

    return {
        "id": holding_id,
        "scheme_code": scheme_code,
        "scheme_name": scheme_name,
        "units": round(units, 4),
        "avg_nav": round(avg_nav, 2),
        "invested_amount": round(invested, 2),
        "category": category,
        "folio_number": raw.get("folio_number") or raw.get("folio"),
        "investment_type": inv_type,
        "investment_date": inv_date,
        "created_at": str(raw.get("created_at") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")),
        "updated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
    }


def normalize_holdings_list(raw_list: Any) -> List[Dict[str, Any]]:
    """Normalize a list of holdings, filtering out unparseable entries."""
    if not isinstance(raw_list, list):
        return []
    normalized = []
    seen_codes = set()
    for item in raw_list:
        clean = normalize_holding(item)
        if clean.get("scheme_code") and clean["scheme_code"] not in seen_codes:
            seen_codes.add(clean["scheme_code"])
            normalized.append(clean)
    return normalized


# ─────────────────────────────────────────────────────────────────────────────
# 2. Watchlist Migration & Normalization
# ─────────────────────────────────────────────────────────────────────────────

def normalize_watchlist_item(raw: Any) -> Optional[Dict[str, Any]]:
    """
    Transforms any watchlist item (including legacy raw integers or old schema dicts)
    into the canonical WatchlistItem format.
    """
    if isinstance(raw, (int, str)):
        try:
            code = int(raw)
            return {
                "scheme_code": code,
                "scheme_name": f"Mutual Fund {code}",
                "fund_house": "",
                "scheme_category": "Equity",
                "added_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            }
        except ValueError:
            return None

    if isinstance(raw, dict):
        try:
            code = int(raw.get("scheme_code") or raw.get("amfi_code") or raw.get("code") or 0)
            if code <= 0:
                return None
            return {
                "scheme_code": code,
                "scheme_name": str(raw.get("scheme_name") or raw.get("name") or f"Mutual Fund {code}").strip(),
                "fund_house": str(raw.get("fund_house") or "").strip(),
                "scheme_category": str(raw.get("scheme_category") or raw.get("category") or "Equity").strip(),
                "added_at": str(raw.get("added_at") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")),
            }
        except Exception:
            return None

    return None


def normalize_watchlist(raw_list: Any) -> List[Dict[str, Any]]:
    """Normalize entire watchlist, removing duplicates and upgrading legacy formats."""
    if not isinstance(raw_list, list):
        return []
    clean_list = []
    seen = set()
    for item in raw_list:
        clean = normalize_watchlist_item(item)
        if clean and clean["scheme_code"] not in seen:
            seen.add(clean["scheme_code"])
            clean_list.append(clean)
    return clean_list


# ─────────────────────────────────────────────────────────────────────────────
# 3. Saved Long-Term Goals Migration & Normalization
# ─────────────────────────────────────────────────────────────────────────────

def normalize_goal_plan(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizes any long-term goal plan, backfilling missing projection data,
    re-aligning target corpus fields, and migrating glide paths.
    """
    if not isinstance(raw, dict):
        return {}

    goal_id = str(raw.get("id") or uuid.uuid4().hex)
    goal_name = str(raw.get("goal_name") or raw.get("name") or "Financial Goal").strip()

    # Target corpus resolution
    target = 0.0
    for key in ("target_corpus", "target_amount", "target", "future_value"):
        if raw.get(key) is not None:
            try:
                target = float(raw[key])
                break
            except (ValueError, TypeError):
                pass
    if target <= 0:
        target = 2500000.0  # ₹25 Lakh default baseline

    # Horizon years
    years = 10.0
    for key in ("years", "horizon_years", "duration", "tenure"):
        if raw.get(key) is not None:
            try:
                years = float(raw[key])
                break
            except (ValueError, TypeError):
                pass
    years = max(1.0, min(50.0, years))

    # Required monthly SIP
    sip = 0.0
    for key in ("required_monthly_sip", "monthly_sip", "sip_amount", "sip"):
        if raw.get(key) is not None:
            try:
                sip = float(raw[key])
                break
            except (ValueError, TypeError):
                pass
    if sip <= 0:
        # Standard compound interest formula: target * r / ((1+r)^n - 1)
        r = 0.12 / 12.0
        n = years * 12.0
        sip = round(target * r / (math.pow(1.0 + r, n) - 1.0), 2) if n > 0 else 5000.0

    projected = float(raw.get("projected_corpus") or raw.get("projected") or target)
    equity_pct = float(raw.get("equity_pct") or 100.0)
    liquid_pct = float(raw.get("liquid_pct") or (100.0 - equity_pct))

    glide_path = raw.get("glide_path") or raw.get("glide_path_schedule") or []
    if not isinstance(glide_path, list):
        glide_path = []

    return {
        "id": goal_id,
        "goal_name": goal_name,
        "target_corpus": round(target, 2),
        "years": round(years, 1),
        "required_monthly_sip": round(sip, 2),
        "projected_corpus": round(projected, 2),
        "equity_pct": round(equity_pct, 1),
        "liquid_pct": round(liquid_pct, 1),
        "glide_path": glide_path,
        "milestone_alerts": raw.get("milestone_alerts") or [],
        "created_at": str(raw.get("created_at") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")),
        "updated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
    }


def normalize_goals_list(raw_list: Any) -> List[Dict[str, Any]]:
    """Normalize a list of saved goal plans."""
    if not isinstance(raw_list, list):
        return []
    normalized = []
    seen_ids = set()
    for item in raw_list:
        clean = normalize_goal_plan(item)
        if clean.get("id") and clean["id"] not in seen_ids:
            seen_ids.add(clean["id"])
            normalized.append(clean)
    return normalized


# ─────────────────────────────────────────────────────────────────────────────
# 4. Saved Tactical Investment Plan Migration & Normalization
# ─────────────────────────────────────────────────────────────────────────────

def normalize_saved_plan(raw: Any) -> Optional[Dict[str, Any]]:
    """Normalizes saved investment plan, supporting both wrapped and flat structures."""
    if not isinstance(raw, dict) or not raw:
        return None

    capital = float(raw.get("capital") or 100000.0)
    plan_data = raw.get("plan") or raw.get("plan_data") or raw

    return {
        "capital": capital,
        "plan_data": plan_data,
        "saved_at": str(raw.get("saved_at") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")),
        "updated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. Alert & App Settings Migration & Normalization
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_ALERT_PREFERENCES = {
    "entry_alert": True,
    "macro_alert": True,
    "sip_reminder": True,
    "dud_alert": True,
}

def normalize_alert_preferences(raw: Any) -> Dict[str, bool]:
    """Ensures all current alert toggles exist, merging with defaults for newly added types."""
    if not isinstance(raw, dict):
        return DEFAULT_ALERT_PREFERENCES.copy()

    prefs = DEFAULT_ALERT_PREFERENCES.copy()
    for k in prefs.keys():
        if k in raw:
            prefs[k] = bool(raw[k])
    return prefs
