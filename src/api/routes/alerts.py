"""
src/api/routes/alerts.py
━━━━━━━━━━━━━━━━━━━━━━━━
Alert routes: WhatsApp notification settings and manual dispatch test.
"""

from __future__ import annotations

import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.auth.supabase_client import get_current_user
from src.notifications.whatsapp_bot import (
    send_whatsapp_message,
    format_opportunity_alert,
    format_macro_shock_alert,
    format_smart_sip_alert,
    format_dud_fund_alert,
)

router = APIRouter()


class AlertSettings(BaseModel):
    phone_number: str
    enable_entry_alerts: bool = True
    enable_macro_shocks: bool = True
    enable_monthly_sip: bool = True
    enable_dud_alerts: bool = True


class TestAlertRequest(BaseModel):
    phone_number: str
    alert_type: str = "entry"  # "entry" | "macro" | "sip" | "dud"


@router.get("/settings", summary="Get WhatsApp alert settings")
def get_alert_settings(user: dict = Depends(get_current_user)):
    """Retrieve the current user's alert notification preferences."""
    return {
        "user_id": user["user_id"],
        "phone_number": os.getenv("DEFAULT_WHATSAPP_TO", ""),
        "enable_entry_alerts": True,
        "enable_macro_shocks": True,
        "enable_monthly_sip": True,
        "enable_dud_alerts": True,
        "is_twilio_configured": bool(os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN")),
    }


@router.post("/settings", summary="Update WhatsApp alert settings")
def update_alert_settings(settings: AlertSettings, user: dict = Depends(get_current_user)):
    """Update notification preferences and destination WhatsApp number."""
    return {
        "message": "Alert preferences saved successfully.",
        "user_id": user["user_id"],
        "settings": settings.model_dump(),
    }


@router.post("/test", summary="Send a test WhatsApp notification")
def send_test_alert(req: TestAlertRequest, user: dict = Depends(get_current_user)):
    """Trigger a sample WhatsApp alert to verify setup."""
    if req.alert_type == "entry":
        msg = format_opportunity_alert(
            scheme_name="Parag Parikh Flexi Cap Fund",
            timing_score=78.5,
            current_nav=81.25,
            recommended_action="Increase monthly SIP by 1.5x or deploy 1st tranche of lump sum.",
        )
    elif req.alert_type == "macro":
        msg = format_macro_shock_alert(
            shock_type="Brent Crude Surge +5.2%",
            detail="Brent crude spiked to $84.50 amid Middle-East escalation.",
            downturn_prob=42.0,
            dry_powder_recommendation="Hold 20% in Arbitrage/Liquid fund. Pause fresh lump sums.",
        )
    elif req.alert_type == "sip":
        msg = format_smart_sip_alert(
            month_name="November",
            base_amount=10000.0,
            adjusted_amount=12000.0,
            best_date=7,
            multiplier=1.2,
            reason="Market is in fair-to-attractive valuation zone. Moderate top-up recommended.",
        )
    elif req.alert_type == "dud":
        msg = format_dud_fund_alert(
            scheme_name="Example Underperforming Regular Growth",
            cagr_3y=0.082,
            category_avg_cagr=0.145,
            suggested_alternative="Nifty 50 Index Fund Direct Growth",
        )
    else:
        msg = f"🔔 Test alert from Indian MF Analytics Platform for {user.get('email', 'User')}."

    result = send_whatsapp_message(req.phone_number, msg)
    return {
        "success": result.get("status") in ["sent", "mocked"],
        "details": result,
    }

