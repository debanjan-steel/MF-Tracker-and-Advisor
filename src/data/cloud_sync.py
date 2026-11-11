"""
src/data/cloud_sync.py
━━━━━━━━━━━━━━━━━━━━━━
Multi-tier Cloud Persistence & Disaster Recovery Layer.

Problem:
  Render and similar PaaS providers run web services on ephemeral containers.
  Every code update, git push, or service restart wipes local files (including SQLite data/mf_platform.db).

Solution:
  1. Primary Cloud Storage: Supabase Cloud (PostgreSQL / GoTrue user_metadata).
     - Persists forever across all deployments, rebuilds, and restarts.
     - Automatically tied to the authenticated user's cloud account.
  2. Local Fast Cache: SQLite user_holdings table.
     - On container restart/redeploy, if SQLite table is empty for a user,
       automatically rehydrates (restores) all holdings from Supabase Cloud.
  3. Client Browser Local Backup:
     - Frontend caches holdings in localStorage and can re-hydrate if needed.
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from typing import Any, Dict, List, Optional
import requests

from src.auth.supabase_client import _get_supabase_config, _is_supabase_configured
from src.config import get_settings

logger = logging.getLogger(__name__)


def _get_db_conn() -> sqlite3.Connection:
    settings = get_settings()
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ─────────────────────────────────────────────────────────────────────────────
# Cloud Read / Write (Supabase)
# ─────────────────────────────────────────────────────────────────────────────

def _is_valid_uuid(val: str) -> bool:
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def get_user_holdings_from_cloud(user_id: str) -> List[Dict[str, Any]]:
    """
    Fetch user holdings from Supabase Cloud.
    First tries Supabase PostgREST table 'public.user_holdings'.
    If the table is not created (404), falls back to Supabase user_metadata.
    """
    if not _is_supabase_configured() or not _is_valid_uuid(user_id):
        logger.debug("[CloudSync] Supabase not configured or invalid UUID; skipping cloud fetch.")
        return []

    url, _, sec_key = _get_supabase_config()
    if not sec_key:
        return []

    headers = {
        "apikey": sec_key,
        "Authorization": f"Bearer {sec_key}",
    }

    # 1. Try Supabase PostgREST table (if user created public.user_holdings)
    try:
        res = requests.get(
            f"{url}/rest/v1/user_holdings",
            headers=headers,
            params={"user_id": f"eq.{user_id}", "select": "*"},
            timeout=4,
        )
        if res.status_code == 200:
            rows = res.json()
            if rows:
                logger.info("[CloudSync] Loaded %d holdings from Supabase table for user %s", len(rows), user_id)
                return rows
    except Exception as e:
        logger.debug("[CloudSync] PostgREST table lookup error: %s", e)

    # 2. Primary cloud fallback: Supabase GoTrue user_metadata
    try:
        res = requests.get(
            f"{url}/auth/v1/admin/users/{user_id}",
            headers=headers,
            timeout=5,
        )
        if res.status_code == 200:
            user_data = res.json()
            meta = user_data.get("user_metadata", {}) or {}
            holdings = meta.get("portfolio_holdings", [])
            if isinstance(holdings, list) and holdings:
                logger.info("[CloudSync] Loaded %d holdings from Supabase user_metadata for user %s", len(holdings), user_id)
                return holdings
    except Exception as e:
        logger.warning("[CloudSync] Failed to fetch holdings from Supabase user_metadata: %s", e)

    return []


def save_user_holdings_to_cloud(user_id: str, holdings: List[Dict[str, Any]]) -> bool:
    """
    Persist current holdings to Supabase Cloud so they survive container restarts and deploys.
    Saves to Supabase user_metadata and also to public.user_holdings table if available.
    """
    if not _is_supabase_configured() or not _is_valid_uuid(user_id):
        return False

    url, _, sec_key = _get_supabase_config()
    if not sec_key:
        return False

    headers = {
        "apikey": sec_key,
        "Authorization": f"Bearer {sec_key}",
        "Content-Type": "application/json",
    }

    success = False

    # 1. Save to Supabase GoTrue user_metadata (guaranteed to work without DDL tables)
    try:
        # Retrieve existing metadata to preserve other user attributes
        r_get = requests.get(f"{url}/auth/v1/admin/users/{user_id}", headers=headers, timeout=5)
        existing_meta = {}
        if r_get.status_code == 200:
            existing_meta = r_get.json().get("user_metadata", {}) or {}

        # Strip unneeded runtime fields before saving to keep payload lean
        clean_holdings = []
        for h in holdings:
            clean_holdings.append({
                "id": str(h.get("id") or uuid.uuid4().hex),
                "scheme_code": int(h.get("scheme_code") or 0),
                "scheme_name": str(h.get("scheme_name") or ""),
                "units": float(h.get("units") or 0.0),
                "avg_nav": float(h.get("avg_nav") or 0.0),
                "invested_amount": float(h.get("invested_amount") or h.get("invested") or 0.0),
                "category": str(h.get("category") or "Equity"),
                "folio_number": h.get("folio_number"),
                "investment_type": str(h.get("investment_type") or "LUMPSUM"),
                "investment_date": h.get("investment_date"),
                "created_at": h.get("created_at"),
                "updated_at": h.get("updated_at"),
            })

        existing_meta["portfolio_holdings"] = clean_holdings

        r_put = requests.put(
            f"{url}/auth/v1/admin/users/{user_id}",
            headers=headers,
            json={"user_metadata": existing_meta},
            timeout=5,
        )
        if r_put.status_code == 200:
            logger.info("[CloudSync] Successfully synced %d holdings to Supabase Cloud for user %s", len(clean_holdings), user_id)
            success = True
        else:
            logger.warning("[CloudSync] Supabase user_metadata update failed (%d): %s", r_put.status_code, r_put.text[:200])
    except Exception as e:
        logger.warning("[CloudSync] Error saving holdings to Supabase user_metadata: %s", e)

    # 2. Also try writing to Supabase table if it exists
    try:
        res = requests.post(
            f"{url}/rest/v1/user_holdings",
            headers={**headers, "Prefer": "resolution=merge-duplicates"},
            json=[{**h, "user_id": user_id} for h in clean_holdings],
            timeout=4,
        )
        if res.status_code in (200, 201):
            success = True
    except Exception:
        pass

    return success


# ─────────────────────────────────────────────────────────────────────────────
# Local SQLite Rehydration (Self-Healing on Container Restart)
# ─────────────────────────────────────────────────────────────────────────────

def ensure_user_holdings_hydrated(user_id: str) -> List[Dict[str, Any]]:
    """
    Check if local SQLite has holdings for user_id.
    If local SQLite is empty (e.g. after a Render deployment or server restart),
    automatically fetches the saved holdings from Supabase Cloud and rehydrates local SQLite.
    Returns the list of current holdings.
    """
    conn = _get_db_conn()
    try:
        cur = conn.execute(
            "SELECT * FROM user_holdings WHERE user_id = ? ORDER BY invested_amount DESC",
            (user_id,),
        )
        local_rows = [dict(r) for r in cur.fetchall()]
        if local_rows:
            return local_rows

        # Local SQLite is empty! Check Supabase Cloud for restored holdings
        cloud_holdings = get_user_holdings_from_cloud(user_id)
        if not cloud_holdings:
            return []

        logger.info("[CloudSync] Rehydrating %d holdings from cloud into local SQLite for user %s", len(cloud_holdings), user_id)
        for h in cloud_holdings:
            h_id = h.get("id") or uuid.uuid4().hex
            scheme_code = int(h.get("scheme_code") or 0)
            scheme_name = str(h.get("scheme_name") or "")
            units = float(h.get("units") or 0.0)
            avg_nav = float(h.get("avg_nav") or 0.0)
            invested = float(h.get("invested_amount") or h.get("invested") or 0.0)
            category = str(h.get("category") or "Equity")
            folio = h.get("folio_number")
            inv_type = str(h.get("investment_type") or "LUMPSUM")
            inv_date = h.get("investment_date")

            if scheme_code <= 0 or (units <= 0 and invested <= 0):
                continue

            conn.execute(
                """
                INSERT OR REPLACE INTO user_holdings (
                    id, user_id, scheme_code, scheme_name, units, avg_nav,
                    invested_amount, category, folio_number, investment_type, investment_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (h_id, user_id, scheme_code, scheme_name, units, avg_nav, invested, category, folio, inv_type, inv_date),
            )
        conn.commit()

        # Re-query hydrated rows
        cur = conn.execute(
            "SELECT * FROM user_holdings WHERE user_id = ? ORDER BY invested_amount DESC",
            (user_id,),
        )
        return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error("[CloudSync] Error during holdings rehydration for user %s: %s", user_id, e)
        return []
    finally:
        conn.close()


def sync_local_holdings_to_cloud(user_id: str) -> bool:
    """
    Read all holdings currently in local SQLite for user_id and push to Supabase Cloud.
    Called immediately after any add, update, CAS import, or delete operation.
    """
    conn = _get_db_conn()
    try:
        cur = conn.execute("SELECT * FROM user_holdings WHERE user_id = ?", (user_id,))
        holdings = [dict(r) for r in cur.fetchall()]
        return save_user_holdings_to_cloud(user_id, holdings)
    finally:
        conn.close()


def save_user_alert_preferences_to_cloud(user_id: str, prefs: dict) -> bool:
    """Save alert toggles to Supabase Cloud metadata."""
    if not _is_supabase_configured() or not _is_valid_uuid(user_id):
        return False
    url, _, sec_key = _get_supabase_config()
    if not sec_key:
        return False
    headers = {"apikey": sec_key, "Authorization": f"Bearer {sec_key}", "Content-Type": "application/json"}
    try:
        r_get = requests.get(f"{url}/auth/v1/admin/users/{user_id}", headers=headers, timeout=4)
        meta = r_get.json().get("user_metadata", {}) or {} if r_get.status_code == 200 else {}
        meta["alert_preferences"] = prefs
        r_put = requests.put(f"{url}/auth/v1/admin/users/{user_id}", headers=headers, json={"user_metadata": meta}, timeout=4)
        return r_put.status_code == 200
    except Exception as e:
        logger.warning("[CloudSync] Failed to save alert preferences to cloud: %s", e)
        return False


def ensure_user_alert_preferences_hydrated(user_id: str) -> Optional[dict]:
    """Hydrate alert preferences from Supabase Cloud if local DB is reset."""
    conn = _get_db_conn()
    try:
        row = conn.execute("SELECT entry_alert, macro_alert, sip_reminder, dud_alert FROM user_alert_preferences WHERE user_id = ?", (user_id,)).fetchone()
        if row:
            return dict(row)
        if not _is_supabase_configured():
            return None
        url, _, sec_key = _get_supabase_config()
        if not sec_key:
            return None
        headers = {"apikey": sec_key, "Authorization": f"Bearer {sec_key}"}
        res = requests.get(f"{url}/auth/v1/admin/users/{user_id}", headers=headers, timeout=4)
        if res.status_code == 200:
            prefs = res.json().get("user_metadata", {}).get("alert_preferences")
            if prefs and isinstance(prefs, dict):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO user_alert_preferences (user_id, entry_alert, macro_alert, sip_reminder, dud_alert, updated_at)
                    VALUES (?, ?, ?, ?, ?, datetime('now'))
                    """,
                    (
                        user_id,
                        int(prefs.get("entry_alert", True)),
                        int(prefs.get("macro_alert", True)),
                        int(prefs.get("sip_reminder", True)),
                        int(prefs.get("dud_alert", True)),
                    )
                )
                conn.commit()
                return prefs
    except Exception as e:
        logger.warning("[CloudSync] Error hydrating alert preferences: %s", e)
    finally:
        conn.close()
    return None
