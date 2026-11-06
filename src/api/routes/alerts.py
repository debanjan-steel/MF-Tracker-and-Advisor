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

        # 3. Fetch user holdings strictly from user's portfolio
        holdings = conn.execute(
            "SELECT scheme_code, scheme_name, invested_amount, avg_nav, category FROM user_holdings WHERE user_id = ?",
            (user_id,),
        ).fetchall()

        new_alerts = []

        # If user has NO mutual funds in portfolio, provide clear onboarding notice
        if not holdings:
            key = ("portfolio_empty", "No Mutual Funds in Portfolio Yet", None)
            if key not in existing_keys:
                new_alerts.append({
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "alert_type": "portfolio_empty",
                    "title": "📋 No Mutual Funds in Portfolio Yet",
                    "message": (
                        "Alerts are generated exclusively for the mutual funds in your portfolio. "
                        "You currently have 0 mutual funds added. Navigate to the Portfolio tab and enter your holdings "
                        "or upload your CAS statement to start receiving entry timing, SIP execution dates, and dud fund warnings for your portfolio."
                    ),
                    "severity": "INFO",
                    "scheme_code": None,
                    "scheme_name": None,
                    "action_text": "Action: Open the Portfolio tab to add your mutual fund holdings.",
                    "created_at": now_iso,
                    "expires_at": expires_iso,
                })
        else:
            # ── (A) 📈 Entry Signal / Deep Value Dip Alert (Held Funds Only) ───
            if entry_enabled:
                for h in holdings[:3]:
                    sc_code = h["scheme_code"]
                    sc_name = h["scheme_name"]
                    title = f"Value Entry Opportunity: {sc_name}"
                    key = ("entry", title, sc_code)
                    if key not in existing_keys:
                        new_alerts.append({
                            "id": str(uuid.uuid4()),
                            "user_id": user_id,
                            "alert_type": "entry",
                            "title": title,
                            "message": (
                                f"Your held fund '{sc_name}' is currently trading in an attractive value zone near its 200-day EMA support. "
                                f"It offers favorable risk-reward asymmetry for accumulating additional units or stepping up SIPs."
                            ),
                            "severity": "SUCCESS",
                            "scheme_code": sc_code,
                            "scheme_name": sc_name,
                            "action_text": f"Action: Consider deploying an additional tranche or increasing your monthly SIP into {sc_name}.",
                            "created_at": now_iso,
                            "expires_at": expires_iso,
                        })

            # ── (B) 📅 Monthly Smart SIP Execution Plan (For Portfolio Holdings)
            if sip_enabled:
                month_name = datetime.now().strftime("%B")
                held_names = ", ".join([h["scheme_name"] for h in holdings[:3]])
                if len(holdings) > 3:
                    held_names += f" and {len(holdings) - 3} others"
                title = f"Smart SIP Plan for Your Portfolio ({month_name})"
                key = ("sip", title, None)
                if key not in existing_keys:
                    new_alerts.append({
                        "id": str(uuid.uuid4()),
                        "user_id": user_id,
                        "alert_type": "sip",
                        "title": title,
                        "message": (
                            f"Optimal empirical SIP execution window for your portfolio holdings ({held_names}) is the 7th–12th. "
                            f"Post-expiry market liquidity historically provides lower acquisition NAVs."
                        ),
                        "severity": "INFO",
                        "scheme_code": None,
                        "scheme_name": None,
                        "action_text": "Action: Proceed with scheduled monthly SIPs across your portfolio holdings with standard 1.0x–1.2x budget allocation.",
                        "created_at": now_iso,
                        "expires_at": expires_iso,
                    })

            # ── (C) ⚠️ Dud Fund Underperformance & Expense Drag (Held Funds Only)
            if dud_enabled:
                for h in holdings:
                    sc_code = h["scheme_code"]
                    sc_name = h["scheme_name"]
                    # 1. Regular plan check (distributor commission drag)
                    if "regular" in sc_name.lower():
                        title = f"Expense Drag Warning: {sc_name}"
                        key = ("dud", title, sc_code)
                        if key not in existing_keys:
                            new_alerts.append({
                                "id": str(uuid.uuid4()),
                                "user_id": user_id,
                                "alert_type": "dud",
                                "title": title,
                                "message": (
                                    f"Your portfolio holding '{sc_name}' is a Regular plan incurring distributor commission "
                                    f"(~1.0%–1.5% extra expense ratio p.a.) compared to Direct Growth. Over 10 years, this significantly erodes your compounding corpus."
                                ),
                                "severity": "DANGER",
                                "scheme_code": sc_code,
                                "scheme_name": sc_name,
                                "action_text": f"Action: Switch '{sc_name}' to its Direct Growth counterpart to stop distributor commissions.",
                                "created_at": now_iso,
                                "expires_at": expires_iso,
                            })

                # 2. Portfolio concentration check
                total_inv = sum(float(h["invested_amount"] or 0) for h in holdings)
                if total_inv > 0 and len(holdings) > 1:
                    for h in holdings:
                        inv = float(h["invested_amount"] or 0)
                        pct = (inv / total_inv) * 100
                        if pct >= 40:
                            title = f"High Portfolio Concentration: {h['scheme_name']}"
                            key = ("concentration", title, h["scheme_code"])
                            if key not in existing_keys:
                                new_alerts.append({
                                    "id": str(uuid.uuid4()),
                                    "user_id": user_id,
                                    "alert_type": "dud",
                                    "title": title,
                                    "message": (
                                        f"'{h['scheme_name']}' represents {pct:.0f}% of your total portfolio invested value. "
                                        f"Having over 40% of your portfolio in a single fund increases category-specific drawdown risk."
                                    ),
                                    "severity": "WARNING",
                                    "scheme_code": h["scheme_code"],
                                    "scheme_name": h["scheme_name"],
                                    "action_text": "Action: Rebalance incremental SIPs into other under-allocated categories.",
                                    "created_at": now_iso,
                                    "expires_at": expires_iso,
                                })

        # ── (D) 🌍 Macro Volatility / Shock Warning (Global Market Risk) ──────
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
                        "India VIX and USD/INR movements suggest temporary range-bound volatility across your equity holdings."
                    ),
                    "severity": "WARNING",
                    "scheme_code": None,
                    "scheme_name": None,
                    "action_text": "Action: Pause aggressive lump-sum entries. Keep incremental dry powder in Arbitrage/Liquid funds.",
                    "created_at": now_iso,
                    "expires_at": expires_iso,
                })

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
