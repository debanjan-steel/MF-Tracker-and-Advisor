"""
src/api/routes/planner.py
━━━━━━━━━━━━━━━━━━━━━━━━━
Investment planner routes:
  - SIP recommendation card (optimal dates + dynamic amount)
  - Allocation advice (posture: AGGRESSIVE / GROWTH / BALANCED etc.)
  - Goal planner + glide path
  - Value averaging schedule
  - Capital gains tax pack
"""
from __future__ import annotations
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.auth.supabase_client import get_current_user
from src.data.storage import get_nav_history_df
from src.analytics.smart_sip import (
    format_sip_recommendation, compute_value_averaging_schedule, get_optimal_sip_dates
)
from src.analytics.allocation_advisor import compute_allocation_advice
from src.analytics.goal_planner import FinancialGoal, generate_glide_path_recommendation
from src.analytics.tax_pack import PurchaseLot, RedemptionTransaction, compute_capital_gains

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# SIP Planner
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/sip-dates", summary="Empirical best SIP dates for Indian equity funds")
def best_sip_dates(user: dict = Depends(get_current_user)):
    """
    Returns the 3 empirically best days of the month for SIP investment
    in Indian equity mutual funds, with supporting rationale.
    """
    return {"best_sip_dates": get_optimal_sip_dates()}


@router.get("/sip-recommendation", summary="Dynamic SIP recommendation card")
def sip_recommendation(
    monthly_amount: float = Query(..., description="Base monthly SIP amount in ₹"),
    scheme_code: Optional[int] = Query(None, description="Scheme code for timing score"),
    preferred_day: Optional[int] = Query(None, description="Preferred SIP day (1–28)"),
    user: dict = Depends(get_current_user),
):
    """
    Returns a full SIP recommendation:
    - Adjusted monthly amount (based on market timing)
    - Optimal SIP date
    - Dynamic amount reasoning
    - Next SIP date
    """
    timing_score = None
    if scheme_code:
        df = get_nav_history_df(scheme_code)
        if not df.empty:
            from src.analytics.timing_model import compute_timing_score
            result = compute_timing_score(df["nav"])
            timing_score = result["total_score"]

    card = format_sip_recommendation(
        monthly_amount=monthly_amount,
        preferred_day=preferred_day,
        timing_score=timing_score,
    )
    return card


# ─────────────────────────────────────────────────────────────────────────────
# Allocation Advisor
# ─────────────────────────────────────────────────────────────────────────────

class AllocationRequest(BaseModel):
    timing_score: float
    danger_score: float
    hero_capital: Optional[float] = None
    goal_equity_cap: Optional[float] = None
    category_temperatures: Optional[dict[str, float]] = None


@router.post("/allocation-advice", summary="Unified allocation posture recommendation")
def allocation_advice(body: AllocationRequest, user: dict = Depends(get_current_user)):
    """
    Get an actionable allocation posture (AGGRESSIVE / GROWTH / BALANCED / DEFENSIVE / CAPITAL_SAFE)
    based on market timing and macro conditions.
    """
    advice = compute_allocation_advice(
        timing_score=body.timing_score,
        danger_score=body.danger_score,
        category_temperatures=body.category_temperatures,
        goal_equity_cap=body.goal_equity_cap,
        hero_capital=body.hero_capital,
    )
    return {
        "posture": advice.posture,
        "emoji": advice.emoji,
        "description": advice.description,
        "equity_pct": advice.equity_pct,
        "liquid_pct": advice.liquid_pct,
        "sip_multiplier": advice.sip_multiplier,
        "lumpsum_allowed": advice.lumpsum_allowed,
        "opportunity_score": advice.opportunity_score,
        "action_items": advice.action_items,
        "category_weights": advice.category_weights,
        "hero_deployment_plan": advice.hero_deployment_plan,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Goal Planner
# ─────────────────────────────────────────────────────────────────────────────

class GoalRequest(BaseModel):
    name: str
    target_corpus: float
    target_date: str               # ISO date string "YYYY-MM-DD"
    current_corpus: float = 0.0
    expected_equity_return: float = 0.12
    expected_liquid_return: float = 0.07
    inflation_rate: float = 0.06


@router.post("/goal", summary="Generate goal-based glide path recommendation")
def goal_planner(body: GoalRequest, user: dict = Depends(get_current_user)):
    """
    Returns:
    - Required monthly SIP to reach goal
    - Equity / Liquid allocation based on time horizon
    - Year-by-year de-risking schedule
    - Alerts if on track or behind
    """
    goal = FinancialGoal(
        name=body.name,
        target_corpus=body.target_corpus,
        target_date=date.fromisoformat(body.target_date),
        current_corpus=body.current_corpus,
        expected_equity_return=body.expected_equity_return,
        expected_liquid_return=body.expected_liquid_return,
        inflation_rate=body.inflation_rate,
    )
    rec = generate_glide_path_recommendation(goal)
    return {
        "goal_name": rec.goal_name,
        "years_remaining": rec.years_remaining,
        "equity_pct": rec.equity_pct,
        "liquid_pct": rec.liquid_pct,
        "monthly_sip_required": rec.monthly_sip_required,
        "projected_corpus": rec.projected_corpus,
        "goal_gap": rec.goal_gap,
        "de_risk_action": rec.de_risk_action,
        "milestone_alerts": rec.milestone_alerts,
        "glide_path_schedule": rec.glide_path_schedule,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Value Averaging Schedule
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/value-averaging/{scheme_code}", summary="Dynamic value averaging schedule")
def value_averaging(
    scheme_code: int,
    monthly_target_growth: float = Query(5000, description="₹ target portfolio growth per month"),
    current_portfolio_value: float = Query(..., description="Current portfolio value in ₹"),
    base_monthly_sip: float = Query(10000, description="Base monthly SIP amount in ₹"),
    months_ahead: int = Query(12, description="How many months forward to plan"),
    user: dict = Depends(get_current_user),
):
    """
    Generate a value averaging schedule — adjusts monthly SIP to keep
    portfolio growth on a steady target path.
    """
    df = get_nav_history_df(scheme_code)
    if df.empty:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="NAV data not found for scheme.")

    schedule = compute_value_averaging_schedule(
        nav_history=df["nav"],
        monthly_target_growth=monthly_target_growth,
        current_portfolio_value=current_portfolio_value,
        base_monthly_sip=base_monthly_sip,
        months_ahead=months_ahead,
    )
    return {
        "scheme_code": scheme_code,
        "months_planned": len(schedule),
        "schedule": [
            {
                "month": m.month,
                "target_value": m.target_portfolio_value,
                "projected_value": m.actual_portfolio_value,
                "invest_amount": m.suggested_investment,
                "action": m.action,
                "note": m.note,
            }
            for m in schedule
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 1-Click Capital Gains Tax Pack
# ─────────────────────────────────────────────────────────────────────────────

class LotInput(BaseModel):
    scheme_code: int
    scheme_name: str
    purchase_date: str             # YYYY-MM-DD
    units: float
    purchase_nav: float
    purchase_amount: float
    nav_on_31jan2018: Optional[float] = None


class RedemptionInput(BaseModel):
    scheme_code: int
    scheme_name: str
    redemption_date: str           # YYYY-MM-DD
    units_redeemed: float
    redemption_nav: float
    redemption_amount: float


class TaxPackRequest(BaseModel):
    purchase_lots: list[LotInput]
    redemptions: list[RedemptionInput]
    financial_year_end: Optional[str] = None  # YYYY-MM-DD, e.g. "2025-03-31"


@router.post("/tax-pack", summary="1-click capital gains tax pack for ITR filing")
def tax_pack(body: TaxPackRequest, user: dict = Depends(get_current_user)):
    """
    Generates a full capital gains summary for the financial year.
    Covers:
    - STCG (< 1 year, taxed at 20%)
    - LTCG (≥ 1 year, taxed at 12.5%, exempt up to ₹1.25L)
    - Grandfathering for pre-Jan 2018 lots
    - Per-transaction breakdown
    - Downloadable CSV data
    """
    lots = [
        PurchaseLot(
            scheme_code=l.scheme_code,
            scheme_name=l.scheme_name,
            purchase_date=date.fromisoformat(l.purchase_date),
            units=l.units,
            purchase_nav=l.purchase_nav,
            purchase_amount=l.purchase_amount,
            nav_on_31jan2018=l.nav_on_31jan2018,
        )
        for l in body.purchase_lots
    ]
    redemptions = [
        RedemptionTransaction(
            scheme_code=r.scheme_code,
            scheme_name=r.scheme_name,
            redemption_date=date.fromisoformat(r.redemption_date),
            units_redeemed=r.units_redeemed,
            redemption_nav=r.redemption_nav,
            redemption_amount=r.redemption_amount,
        )
        for r in body.redemptions
    ]
    fy_end = date.fromisoformat(body.financial_year_end) if body.financial_year_end else None
    summary = compute_capital_gains(lots, redemptions, fy_end)
    return {
        "financial_year": summary.financial_year,
        "transaction_count": len(summary.records),
        "total_stcg": summary.total_stcg,
        "total_ltcg": summary.total_ltcg,
        "ltcg_after_exemption": summary.ltcg_after_exemption,
        "estimated_stcg_tax": summary.estimated_stcg_tax,
        "estimated_ltcg_tax": summary.estimated_ltcg_tax,
        "estimated_total_tax_with_cess": summary.estimated_tax_with_cess,
        "warnings": summary.warnings,
        "csv_download": summary.csv_data,
        "transactions": [
            {
                "fund": r.scheme_name,
                "buy_date": r.purchase_date.isoformat(),
                "sell_date": r.redemption_date.isoformat(),
                "units": r.units,
                "holding_days": r.holding_days,
                "gain_type": r.gain_type,
                "gain": r.gain,
                "estimated_tax": r.estimated_tax,
                "grandfathered": r.grandfathered,
            }
            for r in summary.records
        ],
    }

