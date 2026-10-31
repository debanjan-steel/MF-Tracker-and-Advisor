"""
src/api/routes/analytics.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Analytics routes: timing score, macro danger, fund metrics, backtester,
stress tests, dud scanner, portfolio X-ray, category thermometer, manager track record.
"""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from src.auth.supabase_client import get_current_user
from src.data.storage import get_nav_history_df
from src.analytics.metrics import full_scorecard
from src.analytics.timing_model import compute_timing_score
from src.analytics.macro_engine import compute_downturn_probability
from src.analytics.backtester import simulate_static_sip, simulate_dynamic_sip, compare_strategies
from src.analytics.stress_tester import run_stress_test, run_all_scenarios, BUILT_IN_SCENARIOS
from src.analytics.category_thermometer import compute_category_temperature
from src.analytics.underperformance_scanner import FundProfile, scan_fund_for_dud

router = APIRouter()


def _get_nav_or_404(scheme_code: int):
    """Helper: load NAV from SQLite or raise 404."""
    df = get_nav_history_df(scheme_code)
    if df.empty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No NAV data for scheme {scheme_code}. Sync it first."
        )
    return df["nav"]


# ─────────────────────────────────────────────────────────────────────────────
# Market Timing
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/timing/{scheme_code}", summary="Market timing score for a fund")
def timing_score(scheme_code: int, user: dict = Depends(get_current_user)):
    """
    Compute the market entry timing score (0–100) for a given fund.
    Uses 200-day EMA distance + RSI + 52W high-low position.
    """
    nav = _get_nav_or_404(scheme_code)
    result = compute_timing_score(nav)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Macro Danger
# ─────────────────────────────────────────────────────────────────────────────

class MacroSnapshotInput(BaseModel):
    vix: Optional[float] = None
    crude: Optional[float] = None
    crude_change_pct: Optional[float] = None
    usdinr: Optional[float] = None
    usdinr_change_pct: Optional[float] = None
    us10y: Optional[float] = None
    dxy: Optional[float] = None
    dxy_change_pct: Optional[float] = None
    gold: Optional[float] = None
    gold_change_pct: Optional[float] = None


@router.post("/macro-danger", summary="Macro downturn probability score")
def macro_danger(body: MacroSnapshotInput, user: dict = Depends(get_current_user)):
    """
    Compute the macro downturn danger score (0–100%) from live macro inputs.
    Pass the latest macro snapshot from your frontend.
    """
    return compute_downturn_probability(body.model_dump())


@router.get("/macro-danger/live", summary="Macro danger from live yfinance data")
async def macro_danger_live(user: dict = Depends(get_current_user)):
    """Fetch live macro data and compute danger score automatically."""
    from src.data.macro_client import fetch_latest_macro_snapshot
    snapshot = fetch_latest_macro_snapshot()
    danger = compute_downturn_probability(snapshot)
    return {**danger, "macro_snapshot": snapshot}


# ─────────────────────────────────────────────────────────────────────────────
# Fund Scorecard
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/scorecard/{scheme_code}", summary="Full fund performance scorecard")
def fund_scorecard(scheme_code: int, user: dict = Depends(get_current_user)):
    """
    Full performance scorecard: CAGR (1/3/5Y), Sharpe, Sortino, Calmar,
    Max Drawdown, Volatility, Alpha (if benchmark available).
    """
    nav = _get_nav_or_404(scheme_code)
    return full_scorecard(nav)


# ─────────────────────────────────────────────────────────────────────────────
# Backtester
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/backtest/{scheme_code}", summary="Static vs Dynamic SIP backtest")
def backtest(
    scheme_code: int,
    monthly_amount: float = Query(10000, description="Monthly SIP amount in ₹"),
    years: float = Query(5.0, description="How many years to backtest"),
    user: dict = Depends(get_current_user),
):
    """
    Compare static (fixed monthly) vs dynamic (timing-aware) SIP strategy.
    Shows which strategy would have yielded better returns historically.
    """
    import pandas as pd
    nav = _get_nav_or_404(scheme_code)
    nav_slice = nav[nav.index >= nav.index[-1] - pd.DateOffset(years=years)]

    static = simulate_static_sip(nav_slice, monthly_amount=monthly_amount)
    dynamic = simulate_dynamic_sip(nav_slice, monthly_budget=monthly_amount)
    comparison = compare_strategies(static, dynamic)

    return {
        "scheme_code": scheme_code,
        "years_backtested": years,
        "monthly_amount": monthly_amount,
        "static_sip": {
            "final_corpus": static.final_corpus,
            "total_invested": static.total_invested,
            "cagr": static.cagr,
            "xirr": static.xirr,
            "max_drawdown": static.max_drawdown,
            "sharpe": static.sharpe,
        },
        "dynamic_sip": {
            "final_corpus": dynamic.final_corpus,
            "total_invested": dynamic.total_invested,
            "cagr": dynamic.cagr,
            "xirr": dynamic.xirr,
            "max_drawdown": dynamic.max_drawdown,
            "sharpe": dynamic.sharpe,
        },
        "comparison": comparison,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Stress Tester
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/stress-test/scenarios", summary="List available stress test scenarios")
def stress_scenarios(user: dict = Depends(get_current_user)):
    """List all built-in stress test scenarios."""
    return {
        "scenarios": [
            {"key": k, "name": v["name"], "drawdown_pct": v["peak_to_trough_pct"]}
            for k, v in BUILT_IN_SCENARIOS.items()
        ]
    }


@router.get("/stress-test/{scenario_key}", summary="Run a stress test scenario")
def stress_test(
    scenario_key: str,
    portfolio_value: float = Query(..., description="Current portfolio value in ₹"),
    user: dict = Depends(get_current_user),
):
    """Run a what-if crash scenario on your portfolio."""
    result = run_stress_test(portfolio_value, scenario_key=scenario_key)
    return {
        "scenario": result.scenario_name,
        "current_value": result.current_portfolio_value,
        "projected_trough": result.projected_trough_value,
        "loss_pct": result.projected_loss_pct,
        "loss_amount": result.projected_loss_amount,
        "recovery_months": result.recovery_months,
        "recovery_estimate": result.recovery_date_estimate,
        "action": result.recommended_action,
        "silver_lining": result.silver_lining,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Category Thermometer
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/thermometer/{scheme_code}", summary="Category temperature for a fund")
def category_temp(
    scheme_code: int,
    category: str = Query("Equity", description="Category label for display"),
    user: dict = Depends(get_current_user),
):
    """
    Get the category thermometer reading for a fund's NAV.
    Shows whether this category is Cold / Warm / Hot / Overheated.
    """
    nav = _get_nav_or_404(scheme_code)
    temp = compute_category_temperature(category, nav)
    return {
        "category": temp.category,
        "temperature": temp.temperature,
        "label": temp.label,
        "emoji": temp.emoji,
        "cagr_3y": temp.cagr_3y,
        "cagr_3y_percentile": temp.cagr_3y_percentile,
        "max_drawdown": temp.max_drawdown,
        "in_recovery": temp.in_recovery,
        "recovery_pct": temp.recovery_pct,
        "sip_recommendation": temp.sip_recommendation,
        "lumpsum_recommendation": temp.lumpsum_recommendation,
        "rationale": temp.rationale,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Dud Fund Scanner
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/dud-scan/{scheme_code}", summary="Check if a fund is underperforming")
def dud_scan(
    scheme_code: int,
    category_avg_cagr_3y: Optional[float] = Query(None, description="Category avg 3Y CAGR (decimal)"),
    expense_ratio: Optional[float] = Query(None, description="Fund expense ratio (decimal, e.g. 0.012)"),
    user: dict = Depends(get_current_user),
):
    """
    Scan a fund for underperformance (dud detection).
    Returns severity: CLEAN | MILD | MODERATE | SEVERE
    """
    nav = _get_nav_or_404(scheme_code)
    fund = FundProfile(
        scheme_code=scheme_code,
        scheme_name=f"Scheme {scheme_code}",
        nav_history=nav,
        category="Equity",
        expense_ratio=expense_ratio or 0.0,
    )
    result = scan_fund_for_dud(fund, category_avg_cagr_3y=category_avg_cagr_3y)
    return {
        "scheme_code": result.scheme_code,
        "is_dud": result.is_dud,
        "severity": result.severity,
        "score": result.score,
        "reasons": result.reasons,
        "cagr_3y": result.cagr_3y,
        "sharpe": result.sharpe_ratio,
        "max_drawdown": result.max_drawdown,
        "verdict": result.reinvestment_note,
        "switch_suggestion": result.switch_suggestion,
    }

