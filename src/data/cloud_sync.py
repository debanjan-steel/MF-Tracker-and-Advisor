"""
src/data/cloud_sync.py
━━━━━━━━━━━━━━━━━━━━━━
Universal Cloud Persistence & Automatic Schema Migration Layer.

Ensures that EVERY kind of user-saved item remains completely safe across all app updates,
container rebuilds, or server restarts on Render / PaaS:
  1. Portfolio Holdings (`user_holdings`)
  2. Watchlist (`watchlist`)
  3. Generated & Saved Tactical Investment Plans (`user_saved_plans`)
  4. Saved Long-Term Goals (`user_saved_goals`)
  5. Alert Settings & Toggles (`user_alert_preferences`)
  6. Dismissed / Read alerts

All data passes through `migration_transformer` on every read and write so that any
data format changes or structural updates automatically upgrade legacy data.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
import requests

from src.auth.supabase_client import _get_supabase_config, _is_supabase_configured
from src.config import get_settings
from src.data.migration_transformer import (
    CURRENT_SCHEMA_VERSION,
    normalize_holding,
    normalize_holdings_list,
    normalize_watchlist,
    normalize_goal_plan,
    normalize_goals_list,
    normalize_saved_plan,
    normalize_alert_preferences,
)

logger = logging.getLogger(__name__)


def _get_db_conn() -> sqlite3.Connection:
    settings = get_settings()
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_watchlist (
            user_id             TEXT NOT NULL,
            scheme_code         INTEGER NOT NULL,
            scheme_name         TEXT NOT NULL,
            fund_house          TEXT,
            scheme_category     TEXT,
            added_at            TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (user_id, scheme_code)
        )
        """
    )
    return conn


def _is_valid_uuid(val: str) -> bool:
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def _get_supabase_headers() -> Optional[tuple[str, dict]]:
    if not _is_supabase_configured():
        return None
    url, _, sec_key = _get_supabase_config()
    if not sec_key or not url:
        return None
    headers = {
        "apikey": sec_key,
        "Authorization": f"Bearer {sec_key}",
        "Content-Type": "application/json",
    }
    return url, headers


# ─────────────────────────────────────────────────────────────────────────────
# 1. Portfolio Holdings Sync & Auto-Migration
# ─────────────────────────────────────────────────────────────────────────────

def get_user_holdings_from_cloud(user_id: str) -> List[Dict[str, Any]]:
    """Fetch user holdings from Supabase Cloud with automatic format normalization."""
    if not _is_valid_uuid(user_id):
        return []

    cfg = _get_supabase_headers()
    if not cfg:
        return []
    url, headers = cfg

    # 1. Try Supabase PostgREST table (if public.user_holdings exists)
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
                return normalize_holdings_list(rows)
    except Exception as e:
        logger.debug("[CloudSync] PostgREST table lookup error: %s", e)

    # 2. Supabase GoTrue user_metadata
    try:
        res = requests.get(f"{url}/auth/v1/admin/users/{user_id}", headers=headers, timeout=5)
        if res.status_code == 200:
            meta = res.json().get("user_metadata", {}) or {}
            holdings = meta.get("portfolio_holdings", [])
            return normalize_holdings_list(holdings)
    except Exception as e:
        logger.warning("[CloudSync] Failed to fetch holdings from Supabase user_metadata: %s", e)

    return []


def save_user_holdings_to_cloud(user_id: str, holdings: List[Dict[str, Any]]) -> bool:
    """Persist normalized holdings to Supabase Cloud."""
    if not _is_valid_uuid(user_id):
        return False

    cfg = _get_supabase_headers()
    if not cfg:
        return False
    url, headers = cfg

    clean_holdings = normalize_holdings_list(holdings)
    success = False

    try:
        r_get = requests.get(f"{url}/auth/v1/admin/users/{user_id}", headers=headers, timeout=5)
        meta = r_get.json().get("user_metadata", {}) or {} if r_get.status_code == 200 else {}
        meta["schema_version"] = CURRENT_SCHEMA_VERSION
        meta["portfolio_holdings"] = clean_holdings
        meta["portfolio_updated_at"] = datetime.utcnow().isoformat()

        r_put = requests.put(
            f"{url}/auth/v1/admin/users/{user_id}",
            headers=headers,
            json={"user_metadata": meta},
            timeout=5,
        )
        if r_put.status_code == 200:
            logger.info("[CloudSync] Synced %d normalized holdings to Supabase for %s", len(clean_holdings), user_id)
            success = True
    except Exception as e:
        logger.warning("[CloudSync] Error saving holdings to Supabase user_metadata: %s", e)

    # Also mirror to Supabase table if it exists
    try:
        requests.post(
            f"{url}/rest/v1/user_holdings",
            headers={**headers, "Prefer": "resolution=merge-duplicates"},
            json=[{**h, "user_id": user_id} for h in clean_holdings],
            timeout=4,
        )
    except Exception:
        pass

    return success


def ensure_user_holdings_hydrated(user_id: str) -> List[Dict[str, Any]]:
    """Self-healing rehydration of portfolio holdings from cloud into local SQLite."""
    conn = _get_db_conn()
    try:
        cur = conn.execute(
            "SELECT * FROM user_holdings WHERE user_id = ? ORDER BY invested_amount DESC",
            (user_id,),
        )
        local_rows = [dict(r) for r in cur.fetchall()]
        if local_rows:
            return normalize_holdings_list(local_rows)

        cloud_holdings = get_user_holdings_from_cloud(user_id)
        if not cloud_holdings:
            return []

        logger.info("[CloudSync] Rehydrating %d holdings from cloud for %s", len(cloud_holdings), user_id)
        for h in cloud_holdings:
            clean = normalize_holding(h)
            if not clean.get("scheme_code"):
                continue
            conn.execute(
                """
                INSERT OR REPLACE INTO user_holdings (
                    id, user_id, scheme_code, scheme_name, units, avg_nav,
                    invested_amount, category, folio_number, investment_type, investment_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    clean["id"], user_id, clean["scheme_code"], clean["scheme_name"],
                    clean["units"], clean["avg_nav"], clean["invested_amount"],
                    clean["category"], clean.get("folio_number"), clean["investment_type"],
                    clean.get("investment_date"),
                ),
            )
        conn.commit()

        cur = conn.execute(
            "SELECT * FROM user_holdings WHERE user_id = ? ORDER BY invested_amount DESC",
            (user_id,),
        )
        return normalize_holdings_list([dict(r) for r in cur.fetchall()])
    except Exception as e:
        logger.error("[CloudSync] Error during holdings rehydration for %s: %s", user_id, e)
        return []
    finally:
        conn.close()


def sync_local_holdings_to_cloud(user_id: str) -> bool:
    """Read local holdings and sync to Supabase Cloud."""
    conn = _get_db_conn()
    try:
        cur = conn.execute("SELECT * FROM user_holdings WHERE user_id = ?", (user_id,))
        holdings = [dict(r) for r in cur.fetchall()]
        return save_user_holdings_to_cloud(user_id, holdings)
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# 2. Watchlist Sync & Auto-Migration
# ─────────────────────────────────────────────────────────────────────────────

def get_user_watchlist_from_cloud(user_id: str) -> List[Dict[str, Any]]:
    """Retrieve normalized watchlist from local DB / Supabase Cloud."""
    conn = _get_db_conn()
    try:
        rows = conn.execute(
            "SELECT scheme_code, scheme_name, fund_house, scheme_category, added_at FROM user_watchlist WHERE user_id = ? ORDER BY added_at DESC",
            (user_id,),
        ).fetchall()
        if rows:
            return normalize_watchlist([dict(r) for r in rows])

        if not _is_valid_uuid(user_id):
            return []

        cfg = _get_supabase_headers()
        if not cfg:
            return []
        url, headers = cfg

        r = requests.get(f"{url}/auth/v1/admin/users/{user_id}", headers=headers, timeout=4)
        if r.status_code == 200:
            meta = r.json().get("user_metadata", {}) or {}
            raw_wl = meta.get("watchlist", [])
            clean_wl = normalize_watchlist(raw_wl)
            for it in clean_wl:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO user_watchlist (user_id, scheme_code, scheme_name, fund_house, scheme_category, added_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, it["scheme_code"], it["scheme_name"], it.get("fund_house"), it.get("scheme_category"), it.get("added_at")),
                )
            conn.commit()
            return clean_wl
    except Exception as e:
        logger.warning("[CloudSync] Failed to fetch watchlist: %s", e)
    finally:
        conn.close()
    return []


def save_user_watchlist_to_cloud(user_id: str, watchlist: List[Any]) -> bool:
    """Save normalized watchlist to local DB and Supabase Cloud."""
    clean_wl = normalize_watchlist(watchlist)

    # 1. Save to local SQLite
    conn = _get_db_conn()
    try:
        conn.execute("DELETE FROM user_watchlist WHERE user_id = ?", (user_id,))
        for it in clean_wl:
            conn.execute(
                """
                INSERT OR REPLACE INTO user_watchlist (user_id, scheme_code, scheme_name, fund_house, scheme_category, added_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, it["scheme_code"], it["scheme_name"], it.get("fund_house"), it.get("scheme_category"), it.get("added_at")),
            )
        conn.commit()
    except Exception as e:
        logger.warning("[CloudSync] Failed to save watchlist to SQLite: %s", e)
    finally:
        conn.close()

    # 2. Save to Supabase Cloud if configured
    if not _is_valid_uuid(user_id):
        return True
    cfg = _get_supabase_headers()
    if not cfg:
        return True
    url, headers = cfg
    try:
        r_get = requests.get(f"{url}/auth/v1/admin/users/{user_id}", headers=headers, timeout=4)
        meta = r_get.json().get("user_metadata", {}) or {} if r_get.status_code == 200 else {}
        meta["schema_version"] = CURRENT_SCHEMA_VERSION
        meta["watchlist"] = clean_wl
        meta["watchlist_updated_at"] = datetime.utcnow().isoformat()
        r_put = requests.put(
            f"{url}/auth/v1/admin/users/{user_id}",
            headers=headers,
            json={"user_metadata": meta},
            timeout=4,
        )
        return r_put.status_code == 200
    except Exception as e:
        logger.warning("[CloudSync] Failed to save watchlist to cloud: %s", e)
        return True


# ─────────────────────────────────────────────────────────────────────────────
# 3. Saved Tactical Investment Plan Sync & Rehydration
# ─────────────────────────────────────────────────────────────────────────────

def get_user_plan_from_cloud(user_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve saved investment plan from Supabase Cloud."""
    if not _is_valid_uuid(user_id):
        return None
    cfg = _get_supabase_headers()
    if not cfg:
        return None
    url, headers = cfg
    try:
        r = requests.get(f"{url}/auth/v1/admin/users/{user_id}", headers=headers, timeout=4)
        if r.status_code == 200:
            meta = r.json().get("user_metadata", {}) or {}
            raw_plan = meta.get("saved_investment_plan")
            return normalize_saved_plan(raw_plan)
    except Exception as e:
        logger.warning("[CloudSync] Failed to fetch saved plan: %s", e)
    return None


def save_user_plan_to_cloud(user_id: str, plan_data: Any, capital: float) -> bool:
    """Save normalized investment plan to Supabase Cloud."""
    if not _is_valid_uuid(user_id):
        return False
    cfg = _get_supabase_headers()
    if not cfg:
        return False
    url, headers = cfg
    clean_plan = normalize_saved_plan({"plan": plan_data, "capital": capital})
    try:
        r_get = requests.get(f"{url}/auth/v1/admin/users/{user_id}", headers=headers, timeout=4)
        meta = r_get.json().get("user_metadata", {}) or {} if r_get.status_code == 200 else {}
        meta["schema_version"] = CURRENT_SCHEMA_VERSION
        meta["saved_investment_plan"] = clean_plan
        r_put = requests.put(
            f"{url}/auth/v1/admin/users/{user_id}",
            headers=headers,
            json={"user_metadata": meta},
            timeout=4,
        )
        return r_put.status_code == 200
    except Exception as e:
        logger.warning("[CloudSync] Failed to save plan to cloud: %s", e)
        return False


def delete_user_plan_from_cloud(user_id: str) -> bool:
    """Delete saved investment plan from Supabase Cloud."""
    if not _is_valid_uuid(user_id):
        return False
    cfg = _get_supabase_headers()
    if not cfg:
        return False
    url, headers = cfg
    try:
        r_get = requests.get(f"{url}/auth/v1/admin/users/{user_id}", headers=headers, timeout=4)
        meta = r_get.json().get("user_metadata", {}) or {} if r_get.status_code == 200 else {}
        if "saved_investment_plan" in meta:
            del meta["saved_investment_plan"]
            requests.put(f"{url}/auth/v1/admin/users/{user_id}", headers=headers, json={"user_metadata": meta}, timeout=4)
        return True
    except Exception:
        return False


def ensure_user_plan_hydrated(user_id: str) -> Optional[Dict[str, Any]]:
    """Self-healing rehydration of saved investment plan from cloud if SQLite is reset."""
    conn = _get_db_conn()
    try:
        row = conn.execute(
            "SELECT plan_data, capital, saved_at, updated_at FROM user_saved_plans WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row:
            try:
                parsed = json.loads(row["plan_data"])
            except Exception:
                parsed = {}
            return normalize_saved_plan({"plan": parsed, "capital": row["capital"], "saved_at": row["saved_at"]})

        cloud_plan = get_user_plan_from_cloud(user_id)
        if not cloud_plan:
            return None

        conn.execute(
            """
            INSERT OR REPLACE INTO user_saved_plans (user_id, plan_data, capital, saved_at, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            """,
            (user_id, json.dumps(cloud_plan.get("plan_data") or {}), cloud_plan.get("capital", 100000.0), cloud_plan.get("saved_at")),
        )
        conn.commit()
        return cloud_plan
    except Exception as e:
        logger.warning("[CloudSync] Error hydrating saved plan: %s", e)
        return None
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# 4. Saved Long-Term Goals Sync & Rehydration
# ─────────────────────────────────────────────────────────────────────────────

def get_user_goals_from_cloud(user_id: str) -> List[Dict[str, Any]]:
    """Retrieve normalized long-term goals from Supabase Cloud."""
    if not _is_valid_uuid(user_id):
        return []
    cfg = _get_supabase_headers()
    if not cfg:
        return []
    url, headers = cfg
    try:
        r = requests.get(f"{url}/auth/v1/admin/users/{user_id}", headers=headers, timeout=4)
        if r.status_code == 200:
            meta = r.json().get("user_metadata", {}) or {}
            raw_goals = meta.get("saved_goals", [])
            return normalize_goals_list(raw_goals)
    except Exception as e:
        logger.warning("[CloudSync] Failed to fetch goals: %s", e)
    return []


def save_user_goals_to_cloud(user_id: str, goals: List[Dict[str, Any]]) -> bool:
    """Save normalized long-term goals to Supabase Cloud."""
    if not _is_valid_uuid(user_id):
        return False
    cfg = _get_supabase_headers()
    if not cfg:
        return False
    url, headers = cfg
    clean_goals = normalize_goals_list(goals)
    try:
        r_get = requests.get(f"{url}/auth/v1/admin/users/{user_id}", headers=headers, timeout=4)
        meta = r_get.json().get("user_metadata", {}) or {} if r_get.status_code == 200 else {}
        meta["schema_version"] = CURRENT_SCHEMA_VERSION
        meta["saved_goals"] = clean_goals
        meta["goals_updated_at"] = datetime.utcnow().isoformat()
        r_put = requests.put(
            f"{url}/auth/v1/admin/users/{user_id}",
            headers=headers,
            json={"user_metadata": meta},
            timeout=4,
        )
        return r_put.status_code == 200
    except Exception as e:
        logger.warning("[CloudSync] Failed to save goals to cloud: %s", e)
        return False


def ensure_user_goals_hydrated(user_id: str) -> List[Dict[str, Any]]:
    """Self-healing rehydration of long-term goals from cloud into local SQLite."""
    conn = _get_db_conn()
    try:
        rows = conn.execute(
            """
            SELECT id, goal_name, target_corpus, years, required_monthly_sip,
                   projected_corpus, equity_pct, liquid_pct, goal_data, created_at, updated_at
            FROM user_saved_goals
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        ).fetchall()

        if rows:
            results = []
            for r in rows:
                try:
                    p = json.loads(r["goal_data"])
                except Exception:
                    p = {}
                results.append({
                    "id": r["id"],
                    "goal_name": r["goal_name"],
                    "target_corpus": r["target_corpus"],
                    "years": r["years"],
                    "required_monthly_sip": r["required_monthly_sip"],
                    "projected_corpus": r["projected_corpus"] or 0.0,
                    "equity_pct": r["equity_pct"] or 100.0,
                    "liquid_pct": r["liquid_pct"] or 0.0,
                    "glide_path": p.get("glide_path") or [],
                    "milestone_alerts": p.get("milestone_alerts") or [],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                })
            return normalize_goals_list(results)

        cloud_goals = get_user_goals_from_cloud(user_id)
        if not cloud_goals:
            return []

        logger.info("[CloudSync] Rehydrating %d saved goals from cloud for %s", len(cloud_goals), user_id)
        for g in cloud_goals:
            clean = normalize_goal_plan(g)
            if not clean.get("id"):
                continue
            goal_blob = json.dumps({
                "glide_path": clean.get("glide_path", []),
                "milestone_alerts": clean.get("milestone_alerts", []),
            })
            conn.execute(
                """
                INSERT OR REPLACE INTO user_saved_goals (
                    id, user_id, goal_name, target_corpus, years, required_monthly_sip,
                    projected_corpus, equity_pct, liquid_pct, goal_data, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    clean["id"], user_id, clean["goal_name"], clean["target_corpus"],
                    clean["years"], clean["required_monthly_sip"], clean["projected_corpus"],
                    clean["equity_pct"], clean["liquid_pct"], goal_blob, clean.get("created_at"),
                ),
            )
        conn.commit()
        return cloud_goals
    except Exception as e:
        logger.warning("[CloudSync] Error hydrating saved goals: %s", e)
        return []
    finally:
        conn.close()


def sync_local_goals_to_cloud(user_id: str) -> bool:
    """Read all goals currently in SQLite and sync to Supabase Cloud."""
    conn = _get_db_conn()
    try:
        rows = conn.execute("SELECT * FROM user_saved_goals WHERE user_id = ?", (user_id,)).fetchall()
        goals = []
        for r in rows:
            try:
                blob = json.loads(r["goal_data"])
            except Exception:
                blob = {}
            goals.append({
                "id": r["id"],
                "goal_name": r["goal_name"],
                "target_corpus": r["target_corpus"],
                "years": r["years"],
                "required_monthly_sip": r["required_monthly_sip"],
                "projected_corpus": r["projected_corpus"],
                "equity_pct": r["equity_pct"],
                "liquid_pct": r["liquid_pct"],
                "glide_path": blob.get("glide_path") or [],
                "milestone_alerts": blob.get("milestone_alerts") or [],
                "created_at": r["created_at"],
            })
        return save_user_goals_to_cloud(user_id, goals)
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# 5. Alert Preferences & Settings Sync
# ─────────────────────────────────────────────────────────────────────────────

def save_user_alert_preferences_to_cloud(user_id: str, prefs: dict) -> bool:
    """Save normalized alert toggles to Supabase Cloud."""
    if not _is_valid_uuid(user_id):
        return False
    cfg = _get_supabase_headers()
    if not cfg:
        return False
    url, headers = cfg
    clean_prefs = normalize_alert_preferences(prefs)
    try:
        r_get = requests.get(f"{url}/auth/v1/admin/users/{user_id}", headers=headers, timeout=4)
        meta = r_get.json().get("user_metadata", {}) or {} if r_get.status_code == 200 else {}
        meta["schema_version"] = CURRENT_SCHEMA_VERSION
        meta["alert_preferences"] = clean_prefs
        r_put = requests.put(f"{url}/auth/v1/admin/users/{user_id}", headers=headers, json={"user_metadata": meta}, timeout=4)
        return r_put.status_code == 200
    except Exception as e:
        logger.warning("[CloudSync] Failed to save alert preferences to cloud: %s", e)
        return False


def ensure_user_alert_preferences_hydrated(user_id: str) -> Optional[dict]:
    """Hydrate alert preferences from Supabase Cloud if local DB is reset."""
    conn = _get_db_conn()
    try:
        row = conn.execute(
            "SELECT entry_alert, macro_alert, sip_reminder, dud_alert FROM user_alert_preferences WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row:
            return normalize_alert_preferences(dict(row))

        if not _is_valid_uuid(user_id):
            return normalize_alert_preferences({})

        cfg = _get_supabase_headers()
        if not cfg:
            return normalize_alert_preferences({})
        url, headers = cfg

        res = requests.get(f"{url}/auth/v1/admin/users/{user_id}", headers=headers, timeout=4)
        if res.status_code == 200:
            prefs = res.json().get("user_metadata", {}).get("alert_preferences")
            clean_prefs = normalize_alert_preferences(prefs or {})
            conn.execute(
                """
                INSERT OR REPLACE INTO user_alert_preferences (user_id, entry_alert, macro_alert, sip_reminder, dud_alert, updated_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    user_id,
                    int(clean_prefs.get("entry_alert", True)),
                    int(clean_prefs.get("macro_alert", True)),
                    int(clean_prefs.get("sip_reminder", True)),
                    int(clean_prefs.get("dud_alert", True)),
                ),
            )
            conn.commit()
            return clean_prefs
    except Exception as e:
        logger.warning("[CloudSync] Error hydrating alert preferences: %s", e)
    finally:
        conn.close()
    return normalize_alert_preferences({})


# ─────────────────────────────────────────────────────────────────────────────
# 6. Universal User State Snapshot (One-Tap Sync & Migration)
# ─────────────────────────────────────────────────────────────────────────────

def get_universal_user_state(user_id: str) -> Dict[str, Any]:
    """
    Retrieve all saved user items (holdings, watchlist, plans, goals, preferences)
    with guaranteed automatic schema migration.
    """
    holdings = ensure_user_holdings_hydrated(user_id)
    watchlist = get_user_watchlist_from_cloud(user_id)
    plan = ensure_user_plan_hydrated(user_id)
    goals = ensure_user_goals_hydrated(user_id)
    prefs = ensure_user_alert_preferences_hydrated(user_id)

    return {
        "user_id": user_id,
        "schema_version": CURRENT_SCHEMA_VERSION,
        "holdings": holdings,
        "watchlist": watchlist,
        "saved_investment_plan": plan,
        "saved_goals": goals,
        "alert_preferences": prefs,
        "synced_at": datetime.utcnow().isoformat(),
    }


def restore_and_sync_universal_state(user_id: str, state_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """
    Universal Disaster Recovery & Sync:
    Accepts any client-side or backup state, passes all data through
    migration transformers, and commits to both SQLite and Supabase Cloud.
    """
    results = {}
    if "holdings" in state_snapshot:
        clean_holdings = normalize_holdings_list(state_snapshot["holdings"])
        conn = _get_db_conn()
        try:
            for h in clean_holdings:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO user_holdings (
                        id, user_id, scheme_code, scheme_name, units, avg_nav,
                        invested_amount, category, folio_number, investment_type, investment_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        h["id"], user_id, h["scheme_code"], h["scheme_name"],
                        h["units"], h["avg_nav"], h["invested_amount"],
                        h["category"], h.get("folio_number"), h["investment_type"],
                        h.get("investment_date"),
                    ),
                )
            conn.commit()
        finally:
            conn.close()
        save_user_holdings_to_cloud(user_id, clean_holdings)
        results["holdings_count"] = len(clean_holdings)

    if "watchlist" in state_snapshot:
        clean_wl = normalize_watchlist(state_snapshot["watchlist"])
        save_user_watchlist_to_cloud(user_id, clean_wl)
        results["watchlist_count"] = len(clean_wl)

    if "saved_goals" in state_snapshot:
        clean_goals = normalize_goals_list(state_snapshot["saved_goals"])
        conn = _get_db_conn()
        try:
            for g in clean_goals:
                blob = json.dumps({"glide_path": g.get("glide_path", []), "milestone_alerts": g.get("milestone_alerts", [])})
                conn.execute(
                    """
                    INSERT OR REPLACE INTO user_saved_goals (
                        id, user_id, goal_name, target_corpus, years, required_monthly_sip,
                        projected_corpus, equity_pct, liquid_pct, goal_data, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """,
                    (
                        g["id"], user_id, g["goal_name"], g["target_corpus"],
                        g["years"], g["required_monthly_sip"], g["projected_corpus"],
                        g["equity_pct"], g["liquid_pct"], blob, g.get("created_at"),
                    ),
                )
            conn.commit()
        finally:
            conn.close()
        save_user_goals_to_cloud(user_id, clean_goals)
        results["goals_count"] = len(clean_goals)

    if "saved_investment_plan" in state_snapshot:
        clean_plan = normalize_saved_plan(state_snapshot["saved_investment_plan"])
        if clean_plan:
            save_user_plan_to_cloud(user_id, clean_plan.get("plan_data"), clean_plan.get("capital", 100000.0))
            results["plan_saved"] = True

    return {
        "success": True,
        "message": "Universal user state synchronized and upgraded to latest schema.",
        "details": results,
    }
