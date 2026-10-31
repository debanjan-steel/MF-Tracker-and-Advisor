"""
src/analytics/stress_tester.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"What-If" Scenario Stress Tester.

Answers: "What would happen to my portfolio if [event] occurs?"

Built-in scenarios:
  1. Covid Crash (Feb–Mar 2020): Nifty -38% in 40 days
  2. 2008 GFC: Nifty -60% over 12 months
  3. Crude Oil Spike (>$120): Historical impact on Indian MFs
  4. US Fed Rate Hike Cycle: EM outflows → Nifty correction
  5. Rupee Collapse (>₹90/$): Macro stress scenario
  6. Custom: User-defined drawdown % and duration

Output:
  - Projected portfolio value after shock
  - Recovery time estimate (months to get back to pre-shock value)
  - Recommended action during the scenario
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from .metrics import calculate_cagr


# ─────────────────────────────────────────────────────────────────────────────
# Built-in Scenario Library
# ─────────────────────────────────────────────────────────────────────────────

BUILT_IN_SCENARIOS = {
    "covid_crash_2020": {
        "name": "COVID Crash (Feb–Mar 2020)",
        "peak_to_trough_pct": -38.0,
        "duration_days": 40,
        "recovery_months": 6,
        "description": "Nifty 50 fell 38% in 40 days (Jan 14 → Mar 23, 2020). Recovered fully by Nov 2020.",
        "category_impacts": {
            "Large Cap": -34.0,
            "Mid Cap": -42.0,
            "Small Cap": -50.0,
            "Flexi Cap": -38.0,
            "Sectoral — Healthcare": +10.0,
            "Sectoral — IT": -20.0,
        },
    },
    "gfc_2008": {
        "name": "Global Financial Crisis (2008–09)",
        "peak_to_trough_pct": -60.0,
        "duration_days": 365,
        "recovery_months": 24,
        "description": "Nifty 50 fell 60% (Jan 2008 → Mar 2009). Recovery took ~2 years.",
        "category_impacts": {
            "Large Cap": -56.0,
            "Mid Cap": -68.0,
            "Small Cap": -75.0,
            "Flexi Cap": -60.0,
        },
    },
    "crude_spike_120": {
        "name": "Crude Oil Spike (>$120/barrel)",
        "peak_to_trough_pct": -12.0,
        "duration_days": 60,
        "recovery_months": 4,
        "description": "High crude impacts India via CAD widening and INR depreciation. Historical Nifty impact: -12% average.",
        "category_impacts": {
            "Large Cap": -10.0,
            "Mid Cap": -15.0,
            "Small Cap": -18.0,
            "Sectoral — Oil & Gas": +8.0,
        },
    },
    "fed_rate_hike": {
        "name": "US Fed Aggressive Rate Hike Cycle",
        "peak_to_trough_pct": -18.0,
        "duration_days": 180,
        "recovery_months": 12,
        "description": "EM outflows when US rates rise sharply. 2022 analogue: Nifty fell ~18% in H1 2022.",
        "category_impacts": {
            "Large Cap": -15.0,
            "Mid Cap": -22.0,
            "Small Cap": -28.0,
            "Sectoral — IT": -30.0,
            "Sectoral — Banking": -12.0,
        },
    },
    "rupee_collapse": {
        "name": "Rupee Collapse (USD/INR > ₹90)",
        "peak_to_trough_pct": -10.0,
        "duration_days": 90,
        "recovery_months": 6,
        "description": "Sharp INR depreciation leads to imported inflation, RBI rate hikes, FII outflows.",
        "category_impacts": {
            "Large Cap": -9.0,
            "Mid Cap": -12.0,
            "Small Cap": -14.0,
            "Sectoral — IT": +5.0,   # IT benefits from weak INR
            "Sectoral — Pharma": +3.0,
        },
    },
    "india_election_uncertainty": {
        "name": "Indian Election — Hung Parliament Scenario",
        "peak_to_trough_pct": -8.0,
        "duration_days": 30,
        "recovery_months": 3,
        "description": "Hung parliament / coalition government formation can cause temporary -8% correction.",
        "category_impacts": {
            "Large Cap": -7.0,
            "Mid Cap": -10.0,
            "Small Cap": -12.0,
        },
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class StressTestResult:
    """Result of a single stress test scenario."""
    scenario_name: str
    current_portfolio_value: float
    projected_trough_value: float
    projected_loss_amount: float
    projected_loss_pct: float
    recovery_months: int
    recovery_date_estimate: str         # Approximate recovery date
    category_breakdown: list[dict] = field(default_factory=list)
    recommended_action: str = ""
    silver_lining: str = ""             # SIP opportunity during crash


# ─────────────────────────────────────────────────────────────────────────────
# Stress Test Engine
# ─────────────────────────────────────────────────────────────────────────────

def run_stress_test(
    current_portfolio_value: float,
    scenario_key: str = "covid_crash_2020",
    holdings: Optional[list[dict]] = None,
    custom_drawdown_pct: Optional[float] = None,
    custom_recovery_months: Optional[int] = None,
) -> StressTestResult:
    """
    Run a what-if stress test on the current portfolio.

    Parameters
    ----------
    current_portfolio_value : Current total portfolio value in ₹.
    scenario_key            : Key from BUILT_IN_SCENARIOS or "custom".
    holdings                : List of {'category': str, 'value': float} dicts.
    custom_drawdown_pct     : Custom drawdown % (e.g., -25.0 for -25%).
    custom_recovery_months  : Custom recovery time in months.

    Returns
    -------
    StressTestResult
    """
    if scenario_key == "custom":
        scenario = {
            "name": f"Custom Scenario ({custom_drawdown_pct}% drawdown)",
            "peak_to_trough_pct": custom_drawdown_pct or -20.0,
            "duration_days": 90,
            "recovery_months": custom_recovery_months or 12,
            "description": "User-defined stress scenario.",
            "category_impacts": {},
        }
    else:
        scenario = BUILT_IN_SCENARIOS.get(scenario_key, BUILT_IN_SCENARIOS["covid_crash_2020"])

    drawdown_pct = scenario["peak_to_trough_pct"]  # Negative number
    recovery_months = scenario["recovery_months"]
    category_impacts = scenario.get("category_impacts", {})

    # Portfolio-level loss
    projected_trough = current_portfolio_value * (1 + drawdown_pct / 100)
    loss_amount = current_portfolio_value - projected_trough

    # Category-level breakdown
    category_breakdown = []
    if holdings:
        for holding in holdings:
            cat = holding.get("category", "Unknown")
            value = holding.get("value", 0.0)
            cat_impact = category_impacts.get(cat, drawdown_pct)  # Use portfolio-level if no category data
            cat_trough = value * (1 + cat_impact / 100)
            category_breakdown.append({
                "category": cat,
                "current_value": value,
                "scenario_impact_pct": cat_impact,
                "projected_trough_value": round(cat_trough, 2),
                "loss": round(value - cat_trough, 2),
            })

    # Recovery date estimate
    from datetime import date
    today = date.today()
    if today.month + recovery_months > 12:
        rec_year = today.year + (today.month + recovery_months - 1) // 12
        rec_month = (today.month + recovery_months - 1) % 12 + 1
    else:
        rec_year = today.year
        rec_month = today.month + recovery_months

    try:
        from datetime import date as dt_cls
        rec_date = dt_cls(rec_year, rec_month, 1)
        recovery_date_str = rec_date.strftime("%b %Y")
    except Exception:
        recovery_date_str = f"~{recovery_months} months from now"

    # Recommended action
    if drawdown_pct >= -15:
        action = (
            "📋 MODERATE DIP PLAN: Continue all SIPs. Consider a small lump sum at trough. "
            "Do NOT sell your holdings — downturns of this magnitude are normal market behaviour."
        )
    elif drawdown_pct >= -35:
        action = (
            "🛡️ SIGNIFICANT CORRECTION PLAN: Double your SIP for 3–6 months to buy the dip. "
            "Pause all redemptions. Hold dry powder in liquid fund and deploy systematically."
        )
    else:
        action = (
            "☠️ CRISIS PLAN: Stay calm. Continue minimum SIPs. Deploy dry powder in 3–4 tranches "
            "over the drawdown period. Historically, crashes of this magnitude created the best "
            "10-year CAGR entry points for Indian equity investors."
        )

    # Silver lining — SIP opportunity
    units_per_10k_now = 10_000 / (current_portfolio_value or 1) * 100
    units_per_10k_trough = 10_000 / (projected_trough or 1) * 100
    unit_benefit = units_per_10k_trough - units_per_10k_now
    silver_lining = (
        f"📈 SIP OPPORTUNITY: A ₹10,000 SIP buys {unit_benefit:+.1f}% more units at the projected trough "
        f"than at current prices. Crashes reward patient SIP investors."
    )

    return StressTestResult(
        scenario_name=scenario["name"],
        current_portfolio_value=current_portfolio_value,
        projected_trough_value=round(projected_trough, 2),
        projected_loss_amount=round(loss_amount, 2),
        projected_loss_pct=round(drawdown_pct, 1),
        recovery_months=recovery_months,
        recovery_date_estimate=recovery_date_str,
        category_breakdown=category_breakdown,
        recommended_action=action,
        silver_lining=silver_lining,
    )


def run_all_scenarios(
    current_portfolio_value: float,
    holdings: Optional[list[dict]] = None,
) -> list[StressTestResult]:
    """Run all built-in scenarios and return sorted by severity."""
    results = []
    for key in BUILT_IN_SCENARIOS:
        result = run_stress_test(current_portfolio_value, scenario_key=key, holdings=holdings)
        results.append(result)
    results.sort(key=lambda r: r.projected_loss_pct)  # Worst scenario first
    return results


def format_stress_test_report(result: StressTestResult) -> str:
    """Format a single stress test result."""
    lines = [
        f"# 🔥 Stress Test: {result.scenario_name}",
        "",
        f"| | Value |",
        f"|---|---|",
        f"| Current Portfolio | ₹{result.current_portfolio_value:,.0f} |",
        f"| Projected Trough | ₹{result.projected_trough_value:,.0f} |",
        f"| Loss (₹) | ₹{result.projected_loss_amount:,.0f} |",
        f"| Loss (%) | {result.projected_loss_pct:.1f}% |",
        f"| Recovery Time | ~{result.recovery_months} months ({result.recovery_date_estimate}) |",
        "",
        f"**Action**: {result.recommended_action}",
        "",
        f"**{result.silver_lining}**",
    ]

    if result.category_breakdown:
        lines.append("\n## Category Impact Breakdown")
        for cat in result.category_breakdown:
            lines.append(
                f"  - **{cat['category']}**: "
                f"₹{cat['current_value']:,.0f} → ₹{cat['projected_trough_value']:,.0f} "
                f"({cat['scenario_impact_pct']:+.1f}%)"
            )

    return "\n".join(lines)

