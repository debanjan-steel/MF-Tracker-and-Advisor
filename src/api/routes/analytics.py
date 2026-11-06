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
    """Helper: load NAV from SQLite or fetch on-demand."""
    df = get_nav_history_df(scheme_code)
    if df.empty:
        try:
            from src.data.data_manager import data_manager
            from src.data.storage import upsert_schemes, bulk_insert_nav_history
            nav_data = data_manager.get_nav_history(scheme_code)
            if nav_data and nav_data.get("data"):
                meta = nav_data.get("meta", {})
                upsert_schemes([{
                    "scheme_code": scheme_code,
                    "scheme_name": meta.get("scheme_name", f"Scheme {scheme_code}"),
                    "fund_house": meta.get("fund_house", ""),
                    "scheme_type": meta.get("scheme_type", ""),
                    "scheme_category": meta.get("scheme_category", ""),
                }])
                bulk_insert_nav_history(scheme_code, nav_data["data"])
                df = get_nav_history_df(scheme_code)
        except Exception:
            pass

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
    card = full_scorecard(nav)

    # Calculate overall score (0-100) & Grade
    cagr_3y = card.get("cagr_3y") or card.get("cagr_1y") or 0.12
    sharpe = card.get("sharpe") or 1.0
    max_dd = abs(card.get("max_drawdown") or 0.20)
    score = min(100, max(10, int((cagr_3y * 100 * 1.5) + (sharpe * 25) + (100 - max_dd * 100) * 0.2)))
    if score >= 75:
        grade = "A+"
    elif score >= 65:
        grade = "A"
    elif score >= 50:
        grade = "B"
    elif score >= 40:
        grade = "C"
    else:
        grade = "D"

    from src.data.storage import get_scheme
    meta = get_scheme(scheme_code) or {}
    card["scheme_code"] = scheme_code
    card["scheme_name"] = meta.get("scheme_name", f"Scheme {scheme_code}")
    card["overall_score"] = score
    card["grade"] = grade
    return card


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
    from src.data.storage import get_scheme
    meta = get_scheme(scheme_code) or {}
    scheme_name = meta.get("scheme_name", f"Scheme {scheme_code}")
    category = meta.get("scheme_category", "Equity")
    nav_slice = nav[nav.index >= nav.index[-1] - pd.DateOffset(years=years)]

    static = simulate_static_sip(nav_slice, monthly_amount=monthly_amount)
    dynamic = simulate_dynamic_sip(nav_slice, monthly_budget=monthly_amount)
    comparison = compare_strategies(static, dynamic)

    return {
        "scheme_code": scheme_code,
        "scheme_name": scheme_name,
        "category": category,
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
        "static_xirr": static.xirr,
        "dynamic_xirr": dynamic.xirr,
        "static_final_value": static.final_corpus,
        "dynamic_final_value": dynamic.final_corpus,
        "total_invested": static.total_invested,
        "extra_gain": comparison.get("extra_gain", 0),
        "cagr_delta": comparison.get("cagr_delta", 0),
        "verdict": comparison.get("verdict", ""),
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

class BatchThermometerItem(BaseModel):
    scheme_code: int
    scheme_name: Optional[str] = None
    category: Optional[str] = None


class BatchThermometerRequest(BaseModel):
    schemes: list[BatchThermometerItem]


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
    from src.data.storage import get_scheme
    meta = get_scheme(scheme_code) or {}
    resolved_category = meta.get("scheme_category") or category or "Equity"
    scheme_name = meta.get("scheme_name", f"Scheme {scheme_code}")

    temp = compute_category_temperature(resolved_category, nav)
    return {
        "scheme_code": scheme_code,
        "scheme_name": scheme_name,
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


@router.post("/thermometer/batch", summary="Batch thermometer for multiple funds")
def batch_thermometer(
    body: BatchThermometerRequest,
    user: dict = Depends(get_current_user),
):
    """
    Get category thermometer readings for a list of mutual funds (e.g. from user's Watchlist).
    """
    results = []
    from src.data.storage import get_scheme
    for item in body.schemes:
        code = item.scheme_code
        try:
            nav = _get_nav_or_404(code)
            meta = get_scheme(code) or {}
            cat = item.category or meta.get("scheme_category") or "Equity"
            name = item.scheme_name or meta.get("scheme_name") or f"Scheme {code}"
            temp = compute_category_temperature(cat, nav)
            results.append({
                "scheme_code": code,
                "scheme_name": name,
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
            })
        except Exception as e:
            logger.warning(f"Error computing thermometer for scheme {code}: {e}")

    return {"results": results, "count": len(results)}


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

