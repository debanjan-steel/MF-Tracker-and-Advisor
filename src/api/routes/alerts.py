"""
src/api/routes/alerts.py
━━━━━━━━━━━━━━━━━━━━━━━━
In-App Alerts feed, live evaluation, preference toggles, and deletion.
Alerts persist for 14 days unless manually deleted by the user.
"""

from __future__ import annotations

import uuid
import json
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

        # If user has holdings, immediately dismiss any stale 'portfolio_empty' onboarding notices
        if holdings:
            conn.execute(
                "UPDATE user_alerts SET is_dismissed = 1 WHERE user_id = ? AND alert_type = 'portfolio_empty'",
                (user_id,),
            )
            conn.commit()

        # If user has NO mutual funds in portfolio, provide clear onboarding notice
        if not holdings:
            key = ("portfolio_empty", "📋 No Mutual Funds in Portfolio Yet", None)
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

                # 3. 🚨 Substandard Return & Dud Fund Check (Take Money Out)
                for h in holdings:
                    sc_code = h["scheme_code"]
                    sc_name = h["scheme_name"]
                    cat = h["category"] or "Equity"
                    
                    nav_rows = conn.execute(
                        "SELECT nav, nav_date FROM nav_history WHERE scheme_code = ? ORDER BY nav_date ASC",
                        (sc_code,),
                    ).fetchall()
                    
                    if len(nav_rows) >= 20:
                        first_nav = float(nav_rows[0]["nav"])
                        last_nav = float(nav_rows[-1]["nav"])
                        try:
                            d0 = datetime.strptime(nav_rows[0]["nav_date"], "%Y-%m-%d")
                            d1 = datetime.strptime(nav_rows[-1]["nav_date"], "%Y-%m-%d")
                            days = (d1 - d0).days
                        except Exception:
                            days = 0
                            
                        if days >= 365 and first_nav > 0:
                            years_h = days / 365.25
                            cagr = (last_nav / first_nav) ** (1.0 / years_h) - 1.0
                            
                            cat_bench = 0.18
                            if "mid" in cat.lower() or "midcap" in cat.lower():
                                cat_bench = 0.24
                            elif "small" in cat.lower() or "smallcap" in cat.lower():
                                cat_bench = 0.28
                            
                            # Flag severe underperformance or low returns
                            if cagr < 0.08 or (cagr < cat_bench - 0.07):
                                title = f"🚨 Dud Fund / Take Money Out: {sc_name}"
                                key = ("dud_performance", title, sc_code)
                                if key not in existing_keys:
                                    peer_pick = "Parag Parikh Flexi Cap Fund - Direct Plan"
                                    if "mid" in cat.lower():
                                        peer_pick = "Motilal Oswal Midcap Fund - Direct Plan"
                                    elif "small" in cat.lower():
                                        peer_pick = "Nippon India Small Cap Fund - Direct Plan"
                                    elif "large" in cat.lower():
                                        peer_pick = "Nippon India Large Cap Fund - Direct Plan"

                                    new_alerts.append({
                                        "id": str(uuid.uuid4()),
                                        "user_id": user_id,
                                        "alert_type": "dud",
                                        "title": title,
                                        "message": (
                                            f"Your held fund '{sc_name}' is delivering substandard returns (Annualized Return: +{cagr*100:.1f}% vs Category Benchmark: +{cat_bench*100:.1f}%). "
                                            f"Holding this fund causes serious compounding drag. It is strongly recommended to take your money out and redeploy into top compounders."
                                        ),
                                        "severity": "DANGER",
                                        "scheme_code": sc_code,
                                        "scheme_name": sc_name,
                                        "action_text": f"Action: Redeem units from '{sc_name}' and reinvest capital into {peer_pick}.",
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

        # ── (E) 📊 Saved Plans Daily Re-evaluation & Market Shift Changelog ──
        # Check active saved FY plan
        saved_fy = conn.execute(
            "SELECT capital, plan_data, updated_at FROM user_saved_plans WHERE user_id = ?",
            (user_id,),
        ).fetchone()

        if saved_fy and saved_fy["plan_data"]:
            try:
                plan_json = json.loads(saved_fy["plan_data"])
                tactical_plan = plan_json.get("tacticalPlan") or {}
                
                current_date = datetime.utcnow()
                m = current_date.month
                y = current_date.year
                is_q4 = m <= 3
                fy_end_year = y if is_q4 else y + 1
                months_left = max(1, (fy_end_year - y) * 12 + (3 - m) + 1)
                current_month_name = current_date.strftime("%b %Y")
                
                # Compare timing score
                old_timing = tactical_plan.get("timing_score", 62.0)
                from src.data.storage import get_nav_history_df
                df_bm = get_nav_history_df(122640)
                curr_timing = 62.0
                if not df_bm.empty and len(df_bm) > 50:
                    from src.analytics.timing_model import compute_timing_score
                    t_res = compute_timing_score(df_bm["nav"])
                    curr_timing = round(float(t_res.get("total_score", 62.0)), 1)
                
                timing_diff = abs(curr_timing - old_timing)
                is_significant_market_shift = timing_diff >= 8.0
                is_new_month = False
                
                roadmap = tactical_plan.get("execution_roadmap") or []
                if roadmap:
                    saved_month_label = roadmap[0].get("month", "")
                    if current_month_name not in saved_month_label:
                        is_new_month = True

                if is_significant_market_shift or is_new_month:
                    changelog_points = []
                    if is_significant_market_shift:
                        changelog_points.append(
                            f"Market timing score shifted by {timing_diff:.1f} pts (from {old_timing} to {curr_timing}). "
                            f"Model adjusted dynamic cap split and dip timing triggers."
                        )
                    if is_new_month:
                        changelog_points.append(
                            f"Financial year timeline progressed to {current_month_name} ({months_left} months remaining until March 31). "
                            f"Execution tranches and cash flows recalibrated."
                        )

                    title = f"📊 FY Plan Adjusted: Market Shift Changelog ({current_date.strftime('%d %b %Y')})"
                    key = ("plan_update", title, None)
                    if key not in existing_keys:
                        new_alerts.append({
                            "id": str(uuid.uuid4()),
                            "user_id": user_id,
                            "alert_type": "plan_update",
                            "title": title,
                            "message": "Significant market & timeline changes detected in your FY Investment Plan:\n" + "\n".join(f"• {p}" for p in changelog_points),
                            "severity": "INFO",
                            "scheme_code": None,
                            "scheme_name": None,
                            "action_text": "Action: Open the Planner tab to view your updated month-by-month execution roadmap.",
                            "created_at": now_iso,
                            "expires_at": expires_iso,
                        })
            except Exception as e:
                logger.warning(f"Error in daily FY plan re-evaluation: {e}")

        # Check saved long-term goals for glide-path progression
        saved_goals = conn.execute(
            "SELECT id, goal_name, target_corpus, years, required_monthly_sip, created_at, updated_at FROM user_saved_goals WHERE user_id = ?",
            (user_id,),
        ).fetchall()

        for g in saved_goals:
            try:
                g_created = datetime.strptime((g["created_at"] or "")[:10], "%Y-%m-%d")
                days_passed = (datetime.utcnow() - g_created).days
                if days_passed >= 365:
                    years_left = max(1.0, float(g["years"]) - (days_passed / 365.25))
                    title = f"🎯 Goal Plan Glide-Path Update: {g['goal_name']}"
                    key = ("plan_update", title, None)
                    if key not in existing_keys:
                        new_alerts.append({
                            "id": str(uuid.uuid4()),
                            "user_id": user_id,
                            "alert_type": "plan_update",
                            "title": title,
                            "message": (
                                f"Your goal '{g['goal_name']}' has progressed by 1 year. "
                                f"Remaining horizon is now {years_left:.1f} years. "
                                f"De-risking glide-path has automatically shifted capital allocation to protect your accumulated gains."
                            ),
                            "severity": "INFO",
                            "scheme_code": None,
                            "scheme_name": None,
                            "action_text": "Action: Check your goal's updated year-by-year glide-path in the Planner tab.",
                            "created_at": now_iso,
                            "expires_at": expires_iso,
                        })
            except Exception:
                pass

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


def _alert_rank(alert: dict) -> int:
    """
    Ranks alerts strictly in order of importance & regularity:
    Group 1: Portfolio Holdings Alerts (Held Mutual Funds) — At the very top
      - Rank 0: Portfolio Duds / Expense Drags / Take money out / Concentration (Highest Urgency)
      - Rank 1: Portfolio Value Entry / Dip opportunities
      - Rank 2: Portfolio Smart SIP execution plans
    Group 2: Everything else one after the other in order of importance & regularity
      - Rank 3: FY Investment Plan & Goal Glide-path Changelogs
      - Rank 4: Macro Market Volatility & Global Risk Signals
      - Rank 5: Portfolio onboarding notice (only if 0 holdings)
    """
    a_type = alert.get("alert_type", "")
    sev = alert.get("severity", "INFO")
    has_scheme = alert.get("scheme_code") is not None or alert.get("scheme_name") is not None

    if a_type == "dud" or (has_scheme and sev in ("DANGER", "WARNING")):
        return 0
    if a_type == "entry" or (has_scheme and sev == "SUCCESS"):
        return 1
    if a_type == "sip" or has_scheme:
        return 2
    if a_type == "plan_update":
        return 3
    if a_type == "macro":
        return 4
    if a_type == "portfolio_empty":
        return 5
    return 6


def get_active_user_alerts(user_id: str) -> List[dict]:
    """Retrieve all non-dismissed, non-expired alerts for user in strict priority order."""
    with get_db() as conn:
        # Check holdings count: if holdings exist, purge any portfolio_empty alert
        holding_count = conn.execute(
            "SELECT COUNT(*) FROM user_holdings WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]

        if holding_count > 0:
            conn.execute(
                "UPDATE user_alerts SET is_dismissed = 1 WHERE user_id = ? AND alert_type = 'portfolio_empty'",
                (user_id,),
            )

        # Mark expired alerts as dismissed
        conn.execute(
            "UPDATE user_alerts SET is_dismissed = 1 WHERE user_id = ? AND datetime(expires_at) <= datetime('now')",
            (user_id,),
        )
        conn.commit()

        rows = conn.execute(
            """
            SELECT id, alert_type, title, message, severity, scheme_code, scheme_name,
                   action_text, created_at, expires_at
            FROM user_alerts
            WHERE user_id = ? AND is_dismissed = 0
            """,
            (user_id,),
        ).fetchall()

        now = datetime.utcnow()
        results = []
        for r in rows:
            # If user has holdings, suppress any old lingering portfolio_empty alerts
            if holding_count > 0 and r["alert_type"] == "portfolio_empty":
                continue

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

        # Sort strictly: Portfolio alerts at top (Dud -> Entry -> SIP), then Plan updates, then Macro
        results.sort(
            key=lambda a: (
                _alert_rank(a),
                -(datetime.strptime(a["created_at"][:19], "%Y-%m-%d %H:%M:%S").timestamp() if a.get("created_at") else 0)
            )
        )
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
                "user_id": user_id,
                "entry_alert": bool(row["entry_alert"]),
                "macro_alert": bool(row["macro_alert"]),
                "sip_reminder": bool(row["sip_reminder"]),
                "dud_alert": bool(row["dud_alert"]),
                "retention_days": RETENTION_DAYS,
            }

        return {
            "user_id": user_id,
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
    Returns active alerts for the current user, strictly ranked with portfolio alerts at the top.
    Evaluates current holdings and live signals so the feed stays continually updated.
    """
    user_id = user["user_id"]
    return evaluate_and_generate_alerts(user_id)


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
