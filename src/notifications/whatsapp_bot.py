"""
src/notifications/whatsapp_bot.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WhatsApp Alert Dispatcher via Twilio / Meta WhatsApp API.

Sends real-time actionable notifications to user's WhatsApp:
  1. Entry Opportunity Alert (Market Timing score > 75 / Deep Value Dip)
  2. Macro Shock Warning (Crude oil spike > 4%, VIX > 25, USD/INR flight)
  3. Monthly Smart SIP Alert (Multiplier 0.7x - 2.0x + Empirical Best Execution Date)
  4. Dud Fund Warning (Underperforming category average for 4 quarters)
  5. Goal Horizon Warning (Approaching goal horizon, systematic de-risking reminder)

Configuration via .env:
  TWILIO_ACCOUNT_SID
  TWILIO_AUTH_TOKEN
  TWILIO_WHATSAPP_FROM (e.g. 'whatsapp:+14155238886' for Twilio sandbox)
  DEFAULT_WHATSAPP_TO  (e.g. 'whatsapp:+919876543210')
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def send_whatsapp_message(to_number: str, message: str) -> dict:
    """
    Send a WhatsApp message via Twilio REST API.

    Parameters
    ----------
    to_number : User's WhatsApp number in E.164 format (e.g. '+919876543210' or 'whatsapp:+919876543210')
    message   : Text content with emoji formatting

    Returns
    -------
    dict with status and message_sid or error info
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

    # Format destination number for Twilio
    if not to_number.startswith("whatsapp:"):
        formatted_to = f"whatsapp:{to_number}"
    else:
        formatted_to = to_number

    # If credentials are missing, log gracefully (e.g. local dev / preview mode)
    if not account_sid or not auth_token:
        logger.warning(
            "Twilio credentials not configured. Mocking WhatsApp alert to %s:\n%s",
            formatted_to,
            message,
        )
        return {
            "status": "mocked",
            "message": "Twilio credentials missing. Message logged to console.",
            "recipient": formatted_to,
            "preview": message[:120] + "...",
        }

    try:
        from twilio.rest import Client

        client = Client(account_sid, auth_token)
        msg = client.messages.create(
            from_=from_number,
            body=message,
            to=formatted_to,
        )
        return {"status": "sent", "sid": msg.sid, "recipient": formatted_to}
    except Exception as e:
        logger.error("Failed to send WhatsApp message: %s", e)
        return {"status": "error", "error": str(e), "recipient": formatted_to}


# ─────────────────────────────────────────────────────────────────────────────
# Pre-formatted Alert Templates
# ─────────────────────────────────────────────────────────────────────────────

def format_opportunity_alert(
    scheme_name: str,
    timing_score: float,
    current_nav: float,
    recommended_action: str,
) -> str:
    """Alert for strong dip buying / lump sum entry opportunity."""
    return (
        f"🟢 *INDIAN MF TIMING ALERT: STRONG BUY*\n\n"
        f"📈 *Fund*: {scheme_name}\n"
        f"🎯 *Timing Score*: {timing_score:.0f}/100 (Deep Value Zone)\n"
        f"💵 *Latest NAV*: ₹{current_nav:.2f}\n\n"
        f"💡 *Action*: {recommended_action}\n\n"
        f"Check your app dashboard for optimal capital tranche sizing."
    )


def format_macro_shock_alert(
    shock_type: str,
    detail: str,
    downturn_prob: float,
    dry_powder_recommendation: str,
) -> str:
    """Alert for breaking macro shock (Crude surge, VIX spike, etc.)."""
    return (
        f"⚠️ *MACRO SHOCK DETECTED*\n\n"
        f"🚨 *Event*: {shock_type}\n"
        f"📊 *Detail*: {detail}\n"
        f"📉 *Downturn Danger Score*: {downturn_prob:.0f}%\n\n"
        f"🛡️ *Recommended Posture*: {dry_powder_recommendation}\n\n"
        f"Tip: Do not panic sell. Keep temporary dry powder parked in Liquid/Arbitrage."
    )


def format_smart_sip_alert(
    month_name: str,
    base_amount: float,
    adjusted_amount: float,
    best_date: int,
    multiplier: float,
    reason: str,
) -> str:
    """Monthly 1st of the month Smart SIP execution alert."""
    return (
        f"📅 *MONTHLY SMART SIP PLAN — {month_name.upper()}*\n\n"
        f"💰 *Base SIP*: ₹{base_amount:,.0f}\n"
        f"⚡ *Adjusted SIP ({multiplier:.1f}x)*: ₹{adjusted_amount:,.0f}\n"
        f"🗓️ *Empirical Best Date*: {best_date}th of this month\n\n"
        f"📝 *Rationale*: {reason}\n\n"
        f"Open app to execute or adjust your portfolio allocations."
    )


def format_dud_fund_alert(
    scheme_name: str,
    cagr_3y: float,
    category_avg_cagr: float,
    suggested_alternative: str,
) -> str:
    """Red flag alert for consistent underperformer."""
    lag = abs(category_avg_cagr - cagr_3y) * 100
    return (
        f"🚨 *DUD FUND RED FLAG DETECTED*\n\n"
        f"Fund *{scheme_name}* has consistently underperformed its category average.\n\n"
        f"• 3Y CAGR: {cagr_3y*100:.1f}%\n"
        f"• Category Average: {category_avg_cagr*100:.1f}%\n"
        f"• Underperformance Drag: -{lag:.1f}% p.a.\n\n"
        f"🔄 *Suggested Alternative*: {suggested_alternative}\n\n"
        f"Consider pausing fresh SIPs and reviewing phased tax-optimized switch."
    )

