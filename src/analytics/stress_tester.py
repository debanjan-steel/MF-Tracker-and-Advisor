"""
src/analytics/stress_tester.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"What-If" Scenario Stress Tester & Black Swan Simulator.

Answers: "What would happen to my portfolio if a severe macroeconomic anomaly occurs?"

Built-in scenarios:
  1. COVID-19 Crash (Feb–Mar 2020): Nifty -38% in 40 days
  2. 2008 GFC: Nifty -60% over 12 months
  3. Crude Oil Spike (>$120): Historical impact on Indian MFs (-12%)
  4. US Fed Rate Hike & FII Outflow Cycle (-18%)
  5. Rupee Collapse (>₹90/$): Macro currency stress (-10%)
  6. Indian Election / Hung Coalition Uncertainty (-8%)
  7. Taiwan Strait / Geopolitical Tech Supply Shock (-24%)
  8. Custom: User-defined drawdown % and duration

Output:
  - Projected portfolio value after shock
  - Exact loss in ₹ and %
  - Category-by-category breakdown with relative vulnerability
  - Recovery time estimate (months and estimated date)
  - Institutional action playbook & SIP opportunity analysis
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
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
        "category_tag": "Global Pandemic & Liquidity Shock",
        "description": "Nifty 50 fell 38% in 40 days (Jan 14 → Mar 23, 2020). Recovered fully in 6 months by Nov 2020.",
        "category_impacts": {
            "Large Cap": -34.0,
            "Mid Cap": -42.0,
            "Small Cap": -50.0,
            "Flexi Cap": -38.0,
            "Arbitrage": +1.5,
            "Liquid / Debt": +3.0,
            "Sectoral — Healthcare": +10.0,
            "Sectoral — IT": -20.0,
        },
    },
    "gfc_2008": {
        "name": "Global Financial Crisis (2008–09)",
        "peak_to_trough_pct": -60.0,
        "duration_days": 365,
        "recovery_months": 24,
        "category_tag": "Systemic Credit & FII Liquidation",
        "description": "Nifty 50 collapsed 60% over 12 months following Lehman Brothers failure. Full recovery took ~24 months.",
        "category_impacts": {
            "Large Cap": -56.0,
            "Mid Cap": -68.0,
            "Small Cap": -75.0,
            "Flexi Cap": -60.0,
            "Arbitrage": +5.5,
            "Liquid / Debt": +8.8,
        },
    },
    "crude_spike_120": {
        "name": "Crude Oil Shock (>$120/barrel)",
        "peak_to_trough_pct": -12.0,
        "duration_days": 60,
        "recovery_months": 4,
        "category_tag": "Commodity & CAD Expansion",
        "description": "Brent crude surging past $120 triggers CAD expansion, imported inflation, and corporate margin squeeze.",
        "category_impacts": {
            "Large Cap": -10.0,
            "Mid Cap": -15.0,
            "Small Cap": -18.0,
            "Flexi Cap": -12.0,
            "Arbitrage": +2.2,
            "Liquid / Debt": +2.5,
            "Sectoral — Oil & Gas": +8.0,
        },
    },
    "fed_rate_hike": {
        "name": "US Fed Aggressive Rate Hike Cycle",
        "peak_to_trough_pct": -18.0,
        "duration_days": 180,
        "recovery_months": 12,
        "category_tag": "US Yield Spike & FII Flight",
        "description": "Rising US Treasury yields pull foreign capital from emerging markets. 2022 analogue: Nifty fell 18% in H1 2022.",
        "category_impacts": {
            "Large Cap": -15.0,
            "Mid Cap": -22.0,
            "Small Cap": -28.0,
            "Flexi Cap": -18.0,
            "Arbitrage": +4.0,
            "Liquid / Debt": +5.5,
            "Sectoral — IT": -30.0,
            "Sectoral — Banking": -12.0,
        },
    },
    "rupee_collapse": {
        "name": "Rupee Freefall (USD/INR > ₹90)",
        "peak_to_trough_pct": -10.0,
        "duration_days": 90,
        "recovery_months": 6,
        "category_tag": "Currency Depreciation Stress",
        "description": "Sharp INR depreciation leads to imported inflation, RBI defense measures, and FII selling pressure.",
        "category_impacts": {
            "Large Cap": -9.0,
            "Mid Cap": -12.0,
            "Small Cap": -14.0,
            "Flexi Cap": -10.0,
            "Arbitrage": +2.0,
            "Liquid / Debt": +3.0,
            "Sectoral — IT": +6.0,
            "Sectoral — Pharma": +4.0,
        },
    },
    "taiwan_strait_geopolitical": {
        "name": "Geopolitical Tech & Trade Shock",
        "peak_to_trough_pct": -24.0,
        "duration_days": 120,
        "recovery_months": 10,
        "category_tag": "Supply Chain & Tech Disruption",
        "description": "Escalation in key global shipping or semiconductor straits causing worldwide manufacturing bottlenecks.",
        "category_impacts": {
            "Large Cap": -20.0,
            "Mid Cap": -27.0,
            "Small Cap": -34.0,
            "Flexi Cap": -23.0,
            "Arbitrage": +3.5,
            "Liquid / Debt": +4.0,
            "Sectoral — IT": -35.0,
        },
    },
    "india_election_uncertainty": {
        "name": "Coalition / Election Policy Uncertainty",
        "peak_to_trough_pct": -8.0,
        "duration_days": 30,
        "recovery_months": 3,
        "category_tag": "Domestic Policy Uncertainty",
        "description": "Unexpected political outcomes or coalition frictions causing temporary capital market freeze.",
        "category_impacts": {
            "Large Cap": -7.0,
            "Mid Cap": -10.0,
            "Small Cap": -12.0,
            "Flexi Cap": -8.0,
            "Arbitrage": +1.5,
            "Liquid / Debt": +2.0,
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
    scenario_description: str
    current_portfolio_value: float
    projected_trough_value: float
    projected_loss_amount: float
    projected_loss_pct: float
    recovery_months: int
    recovery_date_estimate: str
    category_breakdown: list[dict] = field(default_factory=list)
    worst_hit_category: str = ""
    most_resilient_category: str = ""
    recommended_action: str = ""
    silver_lining: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Stress Test Engine
# ─────────────────────────────────────────────────────────────────────────────

def run_stress_test(
    current_portfolio_value: float,
    scenario_key: str = "covid_crash_2020",
    holdings: Optional[list[dict]] = None,
    custom_drawdown_pct: Optional[float] = None,
    custom_recovery_months: Optional[int] = None,
    custom_macro_inputs: Optional[dict] = None,
) -> StressTestResult:
    """
    Run an institutional-grade stress test on user or simulated portfolio.
    """
    if scenario_key == "custom":
        drawdown_pct = custom_drawdown_pct if custom_drawdown_pct is not None else -20.0
        # If user passed custom macro inputs, compute dynamic drawdown
        if custom_macro_inputs:
            c_crude = float(custom_macro_inputs.get("crude") or 78)
            c_vix = float(custom_macro_inputs.get("vix") or 14)
            c_us10y = float(custom_macro_inputs.get("us10y") or 4.2)
            c_usdinr = float(custom_macro_inputs.get("usdinr") or 84)

            # Sensitivity coefficients
            crude_impact = max(0.0, (c_crude - 85.0) * 0.25)
            vix_impact = max(0.0, (c_vix - 16.0) * 0.9)
            yield_impact = max(0.0, (c_us10y - 4.2) * 5.0)
            inr_impact = max(0.0, (c_usdinr - 84.0) * 1.5)
            computed_drawdown = -(crude_impact + vix_impact + yield_impact + inr_impact)
            if computed_drawdown < -2.0:
                drawdown_pct = max(-65.0, round(computed_drawdown, 1))

        rec_months = custom_recovery_months or max(3, int(abs(drawdown_pct) * 0.5))
        scenario = {
            "name": f"Custom Macro Shock ({drawdown_pct:.1f}% Drawdown)",
            "peak_to_trough_pct": drawdown_pct,
            "duration_days": 90,
            "recovery_months": rec_months,
            "category_tag": "Custom Simulation",
            "description": "User-defined shock parameterized by custom market stress variables.",
            "category_impacts": {
                "Large Cap": round(drawdown_pct * 0.88, 1),
                "Mid Cap": round(drawdown_pct * 1.15, 1),
                "Small Cap": round(drawdown_pct * 1.35, 1),
                "Flexi Cap": round(drawdown_pct * 0.95, 1),
                "Arbitrage": +2.5,
                "Liquid / Debt": +3.5,
            },
        }
    else:
        scenario = BUILT_IN_SCENARIOS.get(scenario_key, BUILT_IN_SCENARIOS["covid_crash_2020"])
        drawdown_pct = scenario["peak_to_trough_pct"]
        rec_months = scenario["recovery_months"]

    category_impacts = scenario.get("category_impacts", {})

    # Calculate portfolio-level trough
    # If explicit holdings are provided with categories, aggregate weighted loss
    category_breakdown = []
    if holdings and len(holdings) > 0:
        total_val = sum(float(h.get("value") or h.get("current_value") or 0.0) for h in holdings)
        if total_val <= 0:
            total_val = current_portfolio_value

        agg_trough = 0.0
        for h in holdings:
            cat = h.get("category") or h.get("scheme_category") or "Flexi Cap"
            # Normalize category string
            matched_impact = None
            for k, imp in category_impacts.items():
                if k.lower() in cat.lower() or cat.lower() in k.lower():
                    matched_impact = imp
                    break
            if matched_impact is None:
                matched_impact = drawdown_pct

            val = float(h.get("value") or h.get("current_value") or 0.0)
            trough_val = val * (1.0 + matched_impact / 100.0)
            loss_val = val - trough_val
            agg_trough += trough_val

            category_breakdown.append({
                "category": cat,
                "scheme_name": h.get("scheme_name") or cat,
                "current_value": round(val, 2),
                "scenario_impact_pct": round(matched_impact, 1),
                "projected_trough_value": round(trough_val, 2),
                "loss": round(loss_val, 2),
            })

        projected_trough = agg_trough
        loss_amount = total_val - projected_trough
        effective_drawdown_pct = round(-((loss_amount / total_val) * 100.0), 1) if total_val > 0 else drawdown_pct
    else:
        # Default synthesized portfolio split (Large 35%, Mid 30%, Small 25%, Debt 10%)
        effective_drawdown_pct = drawdown_pct
        projected_trough = current_portfolio_value * (1.0 + drawdown_pct / 100.0)
        loss_amount = current_portfolio_value - projected_trough

        synthesized_split = [
            ("Large Cap", 0.35, category_impacts.get("Large Cap", drawdown_pct * 0.9)),
            ("Mid Cap", 0.30, category_impacts.get("Mid Cap", drawdown_pct * 1.15)),
            ("Small Cap", 0.25, category_impacts.get("Small Cap", drawdown_pct * 1.35)),
            ("Liquid / Debt", 0.10, category_impacts.get("Liquid / Debt", +3.0)),
        ]
        for c_name, share, imp in synthesized_split:
            c_val = current_portfolio_value * share
            c_trough = c_val * (1.0 + imp / 100.0)
            category_breakdown.append({
                "category": c_name,
                "scheme_name": f"Hypothetical {c_name} Allocation",
                "current_value": round(c_val, 2),
                "scenario_impact_pct": round(imp, 1),
                "projected_trough_value": round(c_trough, 2),
                "loss": round(c_val - c_trough, 2),
            })

    # Find worst hit & most resilient
    sorted_by_impact = sorted(category_breakdown, key=lambda x: x["scenario_impact_pct"])
    worst_hit = sorted_by_impact[0]["category"] if sorted_by_impact else "Small Cap"
    most_resilient = sorted_by_impact[-1]["category"] if sorted_by_impact else "Liquid / Debt"

    # Recovery date estimate
    today = date.today()
    total_months = today.month + rec_months
    rec_year = today.year + (total_months - 1) // 12
    rec_month = (total_months - 1) % 12 + 1
    try:
        from datetime import date as dt_cls
        rec_date = dt_cls(rec_year, rec_month, 1)
        recovery_date_str = rec_date.strftime("%b %Y")
    except Exception:
        recovery_date_str = f"~{rec_months} months from now"

    # Recommended action playbook
    if effective_drawdown_pct >= -12.0:
        action = (
            "📋 MILD CORRECTION PLAYBOOK: Stay 100% invested. Continue regular monthly SIPs without interruption. "
            "Market drawdowns below 12% are standard noise. Do NOT redeem equity units."
        )
    elif effective_drawdown_pct >= -25.0:
        action = (
            "🛡️ ELEVATED CORRECTION PLAYBOOK: Maintain core equity SIPs. Double SIP amount on days when Nifty falls "
            ">2% in a single session. Avoid panic exits; historical recovery took under 10 months."
        )
    else:
        action = (
            "⚡ BLACK SWAN / CRISIS PLAYBOOK: Extreme market dislocation. Step 1: Zero panic selling. "
            "Step 2: Deploy accumulated liquid/arbitrage dry powder in 3 staggered tranches at 30-day intervals. "
            "Historically, every crash above -30% (2008, 2020) created massive 5-year multi-bagger returns."
        )

    # Silver lining: SIP unit accumulation boost
    units_benefit = (abs(effective_drawdown_pct) / (100.0 + effective_drawdown_pct)) * 100.0
    silver_lining = (
        f"📈 SIP DISPLACEMENT ADVANTAGE: At the projected market trough, every ₹10,000 SIP purchases "
        f"{units_benefit:+.1f}% more fund units than today. Systematic buyers profit most from crash recoveries."
    )

    return StressTestResult(
        scenario_name=scenario["name"],
        scenario_description=scenario["description"],
        current_portfolio_value=round(current_portfolio_value, 2),
        projected_trough_value=round(projected_trough, 2),
        projected_loss_amount=round(loss_amount, 2),
        projected_loss_pct=round(effective_drawdown_pct, 1),
        recovery_months=rec_months,
        recovery_date_estimate=recovery_date_str,
        category_breakdown=category_breakdown,
        worst_hit_category=worst_hit,
        most_resilient_category=most_resilient,
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
    results.sort(key=lambda r: r.projected_loss_pct)
    return results
