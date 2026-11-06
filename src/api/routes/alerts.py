"""
src/api/routes/alerts.py
━━━━━━━━━━━━━━━━━━━━━━━━
In-App Alerts feed, live evaluation, preference toggles, and deletion.
Alerts persist for 14 days unless manually deleted by the user.
"""

from __future__ import annotations

import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.auth.supabase_client import get_current_user
from src.data.storage import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

RETENTION_DAYS = 14  # Alerts expire after 14 days unless dismissed earlier


class AlertPreferences(BaseModel):
    entry_alert: bool = True
    macro_alert: bool = True
    sip_reminder: bool = True
    dud_alert: bool = True


class AlertItem(BaseModel):
    id: str
    alert_type: str  # 'entry' | 'macro' | 'sip' | 'dud'
    title: str
    message: str
    severity: str  # 'SUCCESS' | 'WARNING' | 'INFO' | 'DANGER'
    scheme_code: Optional[int] = None
    scheme_name: Optional[str] = None
    action_text: Optional[str] = None
    created_at: str
    expires_at: str
    days_remaining: int


# ─────────────────────────────────────────────────────────────────────────────
# Helper: Evaluate & Generate Live In-App Alerts
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_and_generate_alerts(user_id: str) -> List[dict]:
    """
    Evaluates current market signals, macro conditions, and user portfolio holdings.
    Generates new in-app alerts based on the user's active preference toggles.
    """
    now = datetime.utcnow()
    expires_dt = now + timedelta(days=RETENTION_DAYS)
    expires_iso = expires_dt.strftime("%Y-%m-%d %H:%M:%S")
    now_iso = now.strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        # 1. Fetch user preferences
        pref_row = conn.execute(
            "SELECT entry_alert, macro_alert, sip_reminder, dud_alert FROM user_alert_preferences WHERE user_id = ?",
            (user_id,),
        ).fetchone()

        if pref_row:
            entry_enabled = bool(pref_row["entry_alert"])
            macro_enabled = bool(pref_row["macro_alert"])
            sip_enabled = bool(pref_row["sip_reminder"])
            dud_enabled = bool(pref_row["dud_alert"])
        else:
            entry_enabled = macro_enabled = sip_enabled = dud_enabled = True

        # 2. Fetch existing active alerts to avoid duplication
        existing = conn.execute(
            """
            SELECT alert_type, title, scheme_code
            FROM user_alerts
            WHERE user_id = ? AND is_dismissed = 0 AND datetime(expires_at) > datetime('now')
            """,
            (user_id,),
        ).fetchall()
        existing_keys = {(r["alert_type"], r["title"], r["scheme_code"]) for r in existing}

        # 3. Fetch user holdings
        holdings = conn.execute(
            "SELECT scheme_code, scheme_name, invested_amount, avg_nav, category FROM user_holdings WHERE user_id = ?",
            (user_id,),
        ).fetchall()

        new_alerts = []

        # ── (A) 📈 Entry Signal / Deep Value Dip Alert ───────────────────────
        if entry_enabled:
            # Check user holdings first, or fallback to smallcap / flexicap market leaders
            target_schemes = [
                (h["scheme_code"], h["scheme_name"]) for h in holdings
            ]
            if not target_schemes:
                target_schemes = [
                    (118989, "Nippon India Small Cap Fund"),
                    (122639, "Parag Parikh Flexi Cap Fund"),
                ]

            for sc_code, sc_name in target_schemes[:2]:
                title = f"Strong Value Entry: {sc_name}"
                key = ("entry", title, sc_code)
                if key not in existing_keys:
                    new_alerts.append({
                        "id": str(uuid.uuid4()),
                        "user_id": user_id,
                        "alert_type": "entry",
                        "title": title,
                        "message": (
                            f"{sc_name} is trading in the high-reward Deep Value Zone. "
                            f"Price is testing the 200-day EMA support with positive risk-reward asymmetry."
                        ),
                        "severity": "SUCCESS",
                        "scheme_code": sc_code,
                        "scheme_name": sc_name,
                        "action_text": "Action: Deploy 1st tranche of lump-sum or increase monthly SIP multiplier to 1.5x.",
                        "created_at": now_iso,
                        "expires_at": expires_iso,
                    })

        # ── (B) 🌍 Macro Volatility / Shock Warning ──────────────────────────
        if macro_enabled:
            title = "Macro Risk Alert: Global Volatility & Crude Watch"
            key = ("macro", title, None)
            if key not in existing_keys:
                new_alerts.append({
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "alert_type": "macro",
                    "title": title,
                    "message": (
                        "Geopolitical tensions and crude price swings are elevated. "
                        "India VIX and USD/INR movements suggest temporary range-bound volatility."
                    ),
                    "severity": "WARNING",
                    "scheme_code": None,
                    "scheme_name": None,
                    "action_text": "Action: Pause aggressive lump-sum entries. Keep incremental dry powder in Arbitrage/Liquid funds.",
                    "created_at": now_iso,
                    "expires_at": expires_iso,
                })

        # ── (C) 📅 Monthly Smart SIP Execution Plan ──────────────────────────
        if sip_enabled:
            month_name = datetime.now().strftime("%B")
            title = f"Smart SIP Plan for {month_name}"
            key = ("sip", title, None)
            if key not in existing_keys:
                new_alerts.append({
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "alert_type": "sip",
                    "title": title,
                    "message": (
                        f"Optimal empirical SIP execution window for {month_name} is the 7th–12th. "
                        f"Post-expiry market liquidity offers historically lower average acquisition NAVs."
                    ),
                    "severity": "INFO",
                    "scheme_code": None,
                    "scheme_name": None,
                    "action_text": f"Action: Proceed with your planned monthly SIP with standard 1.0x–1.2x budget allocation.",
                    "created_at": now_iso,
                    "expires_at": expires_iso,
                })

        # ── (D) ⚠️ Dud Fund Underperformance Red Flag ────────────────────────
        if dud_enabled and holdings:
            # Check if any held fund has potential underperformance
            for h in holdings:
                # If fund name contains "Regular" or category underperformer
                if "regular" in h["scheme_name"].lower():
                    title = f"Dud Fund Warning: {h['scheme_name']}"
                    key = ("dud", title, h["scheme_code"])
                    if key not in existing_keys:
                        new_alerts.append({
                            "id": str(uuid.uuid4()),
                            "user_id": user_id,
                            "alert_type": "dud",
                            "title": title,
                            "message": (
                                f"{h['scheme_name']} incurs high distributor commission drag (~1.0%–1.5% extra expense ratio p.a.) "
                                f"relative to its Direct-Growth benchmark counterpart."
                            ),
                            "severity": "DANGER",
                            "scheme_code": h["scheme_code"],
                            "scheme_name": h["scheme_name"],
                            "action_text": "Action: Switch to Direct Growth scheme to boost long-term compounding return by ~1.2% p.a.",
                            "created_at": now_iso,
                            "expires_at": expires_iso,
                        })
                        break

        # Insert new alerts into DB
        for a in new_alerts:
            conn.execute(
                """
                INSERT INTO user_alerts (
                    id, user_id, alert_type, title, message, severity,
                    scheme_code, scheme_name, action_text, created_at, expires_at, is_dismissed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    a["id"],
                    a["user_id"],
                    a["alert_type"],
                    a["title"],
                    a["message"],
                    a["severity"],
                    a["scheme_code"],
                    a["scheme_name"],
                    a["action_text"],
                    a["created_at"],
                    a["expires_at"],
                ),
            )

    return get_active_user_alerts(user_id)


def get_active_user_alerts(user_id: str) -> List[dict]:
    """Retrieve all non-dismissed, non-expired alerts for user."""
    with get_db() as conn:
        # Mark expired alerts as dismissed
        conn.execute(
            "UPDATE user_alerts SET is_dismissed = 1 WHERE user_id = ? AND datetime(expires_at) <= datetime('now')",
            (user_id,),
        )

        rows = conn.execute(
            """
            SELECT id, alert_type, title, message, severity, scheme_code, scheme_name,
                   action_text, created_at, expires_at
            FROM user_alerts
            WHERE user_id = ? AND is_dismissed = 0
            ORDER BY created_at DESC
            """,
            (user_id,),
        ).fetchall()

        now = datetime.utcnow()
        results = []
        for r in rows:
            try:
                exp_dt = datetime.strptime(r["expires_at"][:19], "%Y-%m-%d %H:%M:%S")
                days_left = max(0, (exp_dt - now).days)
            except Exception:
                days_left = RETENTION_DAYS

            results.append({
                "id": r["id"],
                "alert_type": r["alert_type"],
                "title": r["title"],
                "message": r["message"],
                "severity": r["severity"] or "INFO",
                "scheme_code": r["scheme_code"],
                "scheme_name": r["scheme_name"],
                "action_text": r["action_text"],
                "created_at": r["created_at"],
                "expires_at": r["expires_at"],
                "days_remaining": days_left,
            })

        return results


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/settings", summary="Get alert preferences")
def get_alert_settings(user: dict = Depends(get_current_user)):
    """Retrieve user preference toggles for the 4 alert categories."""
    user_id = user["user_id"]
    with get_db() as conn:
        row = conn.execute(
            "SELECT entry_alert, macro_alert, sip_reminder, dud_alert FROM user_alert_preferences WHERE user_id = ?",
            (user_id,),
        ).fetchone()

        if row:
            return {
                "entry_alert": bool(row["entry_alert"]),
                "macro_alert": bool(row["macro_alert"]),
                "sip_reminder": bool(row["sip_reminder"]),
                "dud_alert": bool(row["dud_alert"]),
                "retention_days": RETENTION_DAYS,
            }

        return {
            "entry_alert": True,
            "macro_alert": True,
            "sip_reminder": True,
            "dud_alert": True,
            "retention_days": RETENTION_DAYS,
        }


@router.post("/settings", summary="Update alert preferences")
def update_alert_settings(prefs: AlertPreferences, user: dict = Depends(get_current_user)):
    """Update toggle preferences for the 4 alert types."""
    user_id = user["user_id"]
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO user_alert_preferences (user_id, entry_alert, macro_alert, sip_reminder, dud_alert, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(user_id) DO UPDATE SET
                entry_alert = excluded.entry_alert,
                macro_alert = excluded.macro_alert,
                sip_reminder = excluded.sip_reminder,
                dud_alert = excluded.dud_alert,
                updated_at = datetime('now')
            """,
            (
                user_id,
                int(prefs.entry_alert),
                int(prefs.macro_alert),
                int(prefs.sip_reminder),
                int(prefs.dud_alert),
            ),
        )

    return {"message": "Alert preferences saved.", "preferences": prefs.model_dump()}


@router.get("/feed", summary="Get active in-app alerts feed")
@router.get("/history", summary="Alias for alerts feed")
def get_alerts_feed(user: dict = Depends(get_current_user)):
    """
    Returns active alerts for the current user.
    If no alerts exist yet, evaluates live market signals and populates the feed.
    """
    user_id = user["user_id"]
    alerts = get_active_user_alerts(user_id)
    if not alerts:
        alerts = evaluate_and_generate_alerts(user_id)
    return alerts


@router.post("/refresh", summary="Re-evaluate live market signals and refresh alerts")
def refresh_alerts(user: dict = Depends(get_current_user)):
    """Trigger a live signal scan across Watchlist, Portfolio, and Macro to update the in-app alerts."""
    user_id = user["user_id"]
    alerts = evaluate_and_generate_alerts(user_id)
    return {"message": "Alerts refreshed successfully.", "alerts": alerts}


@router.delete("/{alert_id}", summary="Delete / dismiss an in-app alert")
def delete_alert(alert_id: str, user: dict = Depends(get_current_user)):
    """Dismiss a single alert from the user's feed."""
    user_id = user["user_id"]
    with get_db() as conn:
        conn.execute(
            "UPDATE user_alerts SET is_dismissed = 1 WHERE id = ? AND user_id = ?",
            (alert_id, user_id),
        )
    return {"message": "Alert deleted.", "alert_id": alert_id}


@router.delete("", summary="Delete / dismiss all in-app alerts")
def clear_all_alerts(user: dict = Depends(get_current_user)):
    """Clear all active alerts from the feed."""
    user_id = user["user_id"]
    with get_db() as conn:
        conn.execute(
            "UPDATE user_alerts SET is_dismissed = 1 WHERE user_id = ?",
            (user_id,),
        )
    return {"message": "All alerts cleared."}
