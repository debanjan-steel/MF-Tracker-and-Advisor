"""
src/analytics/macro_analogue.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Historical Macro Analogue & Dynamic Capital Hedging Engine.

Quantifies the current macroeconomic vector against landmark Indian market
crisis regimes using multidimensional similarity metrics:
  - India VIX (Market fear & volatility)
  - Brent Crude Oil (CAD & inflation pressure)
  - US 10-Year Treasury Yield (FII capital outflow driver)
  - USD/INR (Currency depreciation risk)
  - US Dollar Index DXY (Global risk-off dollar hoarding)

Outputs:
  - Closest historical market crisis analogue & similarity score (%)
  - Historical drawdown depths for Nifty, Midcap, Smallcap, and Debt
  - Trough duration and recovery months
  - Dynamic Hedging Recommendation (exact % allocation to Liquid/Arbitrage safe havens)
  - Un-hedging exit trigger to resume 100% equity deployment
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Reference Crisis Regimes Database (Quantified Indian Market Signatures)
# ─────────────────────────────────────────────────────────────────────────────

HISTORICAL_REGIMES = [
    {
        "id": "2008_gfc",
        "name": "2008 Global Financial Crisis (Lehman Shock)",
        "period": "Jan 2008 – Mar 2009",
        "vector": {
            "vix": 55.0,
            "crude": 135.0,
            "us10y": 3.8,
            "usdinr": 50.5,
            "dxy": 88.0,
        },
        "description": "Massive global liquidity freeze and subprime debt collapse leading to aggressive FII liquidation in emerging markets.",
        "drawdowns": {
            "nifty_50": -60.0,
            "midcap": -68.0,
            "smallcap": -75.0,
            "liquid_debt": +8.8,
        },
        "duration_months": 14,
        "recovery_months": 24,
        "best_performer": "Sovereign Debt & Cash Reserves",
        "institutional_lesson": "Extreme small-cap illiquidity during global deleveraging. Systematic dip accumulation created generational wealth.",
    },
    {
        "id": "2013_taper_tantrum",
        "name": "2013 Fed Taper Tantrum & Fragile Five",
        "period": "May 2013 – Sep 2013",
        "vector": {
            "vix": 23.5,
            "crude": 108.0,
            "us10y": 2.9,     # spiked +130 bps in 3 months
            "usdinr": 68.8,    # Rupee crashed from ₹54 to ₹68.8
            "dxy": 84.5,
        },
        "description": "US Fed signaled quantitative easing taper, triggering sudden capital flight from emerging market currencies.",
        "drawdowns": {
            "nifty_50": -13.0,
            "midcap": -26.0,
            "smallcap": -34.0,
            "liquid_debt": +8.5,
        },
        "duration_months": 5,
        "recovery_months": 10,
        "best_performer": "IT Exporters & Arbitrage Funds",
        "institutional_lesson": "Rupee weakness crushed high-debt smallcaps; exporters and liquid funds protected wealth.",
    },
    {
        "id": "2015_china_deval",
        "name": "2015-16 Yuan Devaluation & Commodity Slump",
        "period": "Aug 2015 – Feb 2016",
        "vector": {
            "vix": 22.0,
            "crude": 36.0,     # Global deflation scare
            "us10y": 2.1,
            "usdinr": 68.5,
            "dxy": 98.0,
        },
        "description": "China unexpectedly devalued the Yuan, causing global commodity collapse and fears of global slowdown.",
        "drawdowns": {
            "nifty_50": -22.0,
            "midcap": -19.0,
            "smallcap": -23.0,
            "liquid_debt": +7.5,
        },
        "duration_months": 7,
        "recovery_months": 12,
        "best_performer": "Consumer Staples & Debt",
        "institutional_lesson": "Deflationary shocks favor high-quality FMCG and fixed-income assets over capital goods.",
    },
    {
        "id": "2020_covid_crash",
        "name": "2020 COVID-19 Flash Crash & Supply Lockdown",
        "period": "Feb 2020 – Apr 2020",
        "vector": {
            "vix": 83.5,
            "crude": 24.0,
            "us10y": 0.65,
            "usdinr": 76.5,
            "dxy": 102.5,
        },
        "description": "Unprecedented global shutdown and complete liquidity panic across all financial assets simultaneously.",
        "drawdowns": {
            "nifty_50": -38.0,
            "midcap": -42.0,
            "smallcap": -50.0,
            "liquid_debt": +6.5,
        },
        "duration_months": 2,
        "recovery_months": 6,
        "best_performer": "Pharma & Sovereign Gold",
        "institutional_lesson": "Fastest recovery in market history driven by central bank stimulus. Panic sellers locked in permanent losses.",
    },
    {
        "id": "2022_inflation_rate_hikes",
        "name": "2022 Russia-Ukraine & Global Rate Hike Cycle",
        "period": "Jan 2022 – Jun 2022",
        "vector": {
            "vix": 31.0,
            "crude": 125.0,
            "us10y": 4.1,
            "usdinr": 82.5,
            "dxy": 112.0,
        },
        "description": "Geopolitical conflict in Ukraine drove crude over $120, triggering highest global inflation in 40 years and rapid rate hikes.",
        "drawdowns": {
            "nifty_50": -18.0,
            "midcap": -16.0,
            "smallcap": -25.0,
            "liquid_debt": +5.5,
        },
        "duration_months": 6,
        "recovery_months": 8,
        "best_performer": "Banking & Equity Arbitrage",
        "institutional_lesson": "Tech/growth multiples compressed due to rising cost of capital; value and arbitrage outperformed.",
    },
    {
        "id": "2024_geopolitical_sticky_inflation",
        "name": "2024 Middle East Escalation & High US Yields",
        "period": "Apr 2024 – Oct 2024",
        "vector": {
            "vix": 18.5,
            "crude": 88.0,
            "us10y": 4.4,
            "usdinr": 83.9,
            "dxy": 105.0,
        },
        "description": "Middle East shipping tensions and resilient US economic data keeping interest rates 'higher for longer'.",
        "drawdowns": {
            "nifty_50": -8.5,
            "midcap": -12.0,
            "smallcap": -15.0,
            "liquid_debt": +7.1,
        },
        "duration_months": 2,
        "recovery_months": 3,
        "best_performer": "Large Cap & Gold",
        "institutional_lesson": "Smallcaps exhibited elevated valuation vulnerability; mega caps provided downside defense.",
    },
    {
        "id": "goldilocks_expansion",
        "name": "Goldilocks Low-Volatility Bull Expansion",
        "period": "Normal Bullish Benchmark",
        "vector": {
            "vix": 13.0,
            "crude": 74.0,
            "us10y": 3.7,
            "usdinr": 83.0,
            "dxy": 102.0,
        },
        "description": "Calm macro regime with moderate crude, stable currency, controlled inflation, and steady domestic SIP inflows.",
        "drawdowns": {
            "nifty_50": 0.0,
            "midcap": 0.0,
            "smallcap": 0.0,
            "liquid_debt": +7.0,
        },
        "duration_months": 0,
        "recovery_months": 0,
        "best_performer": "Small & Mid Cap Equity",
        "institutional_lesson": "Unhedged pure equity deployment maximizes wealth accumulation during calm volatility regimes.",
    },
]

# Feature normalization scales [mean, std]
FEATURE_SCALES = {
    "vix": (22.0, 14.0),
    "crude": (85.0, 25.0),
    "us10y": (3.5, 1.2),
    "usdinr": (78.0, 8.0),
    "dxy": (98.0, 8.0),
}


# ─────────────────────────────────────────────────────────────────────────────
# Analogue Matching Engine
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AnalogueMatch:
    id: str
    name: str
    period: str
    similarity_score: float      # 0 to 100%
    description: str
    drawdowns: dict[str, float]
    duration_months: int
    recovery_months: int
    best_performer: str
    institutional_lesson: str


@dataclass
class DynamicHedgingPlan:
    macro_danger_score: float
    recommended_hedge_pct: float        # e.g. 25.0 for 25% of new capital
    hedge_category: str
    preservation_posture: str          # Normal | Guarded | Defensive | Maximum Capital Protection
    hedging_rationale: str
    unhedge_exit_trigger: str
    safe_haven_funds: list[dict] = field(default_factory=list)


@dataclass
class MacroAnalogueReport:
    current_snapshot: dict[str, float]
    top_analogue: AnalogueMatch
    runner_up: AnalogueMatch
    hedging_plan: DynamicHedgingPlan
    ranked_analogues: list[dict] = field(default_factory=list)


def compute_macro_analogues(
    current_macro: dict[str, Any],
    macro_danger_score: float = 35.0,
) -> MacroAnalogueReport:
    """
    Find the closest historical crisis analogue to the current market macro readings.
    """
    vix = float(current_macro.get("vix") or 14.5)
    crude = float(current_macro.get("crude") or 78.0)
    us10y = float(current_macro.get("us10y") or 4.2)
    usdinr = float(current_macro.get("usdinr") or 84.0)
    dxy = float(current_macro.get("dxy") or 104.0)

    # Normalize current vector
    def normalize_vec(v_dict: dict[str, float]) -> np.ndarray:
        return np.array([
            (v_dict["vix"] - FEATURE_SCALES["vix"][0]) / FEATURE_SCALES["vix"][1],
            (v_dict["crude"] - FEATURE_SCALES["crude"][0]) / FEATURE_SCALES["crude"][1],
            (v_dict["us10y"] - FEATURE_SCALES["us10y"][0]) / FEATURE_SCALES["us10y"][1],
            (v_dict["usdinr"] - FEATURE_SCALES["usdinr"][0]) / FEATURE_SCALES["usdinr"][1],
            (v_dict["dxy"] - FEATURE_SCALES["dxy"][0]) / FEATURE_SCALES["dxy"][1],
        ])

    curr_vec = normalize_vec({
        "vix": vix,
        "crude": crude,
        "us10y": us10y,
        "usdinr": usdinr,
        "dxy": dxy,
    })

    scored: list[tuple[float, dict]] = []

    for reg in HISTORICAL_REGIMES:
        hist_vec = normalize_vec(reg["vector"])
        # Euclidean distance in normalized feature space
        dist = float(np.linalg.norm(curr_vec - hist_vec))
        # Convert distance to similarity score: similarity = 1 / (1 + 0.5 * dist)
        sim_pct = round(100.0 / (1.0 + 0.45 * dist), 1)
        scored.append((sim_pct, reg))

    scored.sort(key=lambda x: x[0], reverse=True)

    top_sim, top_reg = scored[0]
    runner_sim, runner_reg = scored[1]

    top_match = AnalogueMatch(
        id=top_reg["id"],
        name=top_reg["name"],
        period=top_reg["period"],
        similarity_score=top_sim,
        description=top_reg["description"],
        drawdowns=top_reg["drawdowns"],
        duration_months=top_reg["duration_months"],
        recovery_months=top_reg["recovery_months"],
        best_performer=top_reg["best_performer"],
        institutional_lesson=top_reg["institutional_lesson"],
    )

    runner_match = AnalogueMatch(
        id=runner_reg["id"],
        name=runner_reg["name"],
        period=runner_reg["period"],
        similarity_score=runner_sim,
        description=runner_reg["description"],
        drawdowns=runner_reg["drawdowns"],
        duration_months=runner_reg["duration_months"],
        recovery_months=runner_reg["recovery_months"],
        best_performer=runner_reg["best_performer"],
        institutional_lesson=runner_reg["institutional_lesson"],
    )

    # ── Dynamic Hedging Determination ──
    # Synthesize similarity to high-stress periods + macro danger score
    is_crisis_analogue = top_reg["id"] in ["2008_gfc", "2020_covid_crash", "2022_inflation_rate_hikes"]

    if macro_danger_score >= 65.0 or (is_crisis_analogue and top_sim >= 65.0):
        hedge_pct = 35.0
        posture = "Maximum Capital Protection"
        hedge_cat = "Arbitrage & Liquid Overnight Funds"
        rationale = (
            f"Active macro stress signatures align closely with {top_reg['name']} ({top_sim}% similarity). "
            f"VIX ({vix:.1f}) and high crude/yields suggest near-term downside risk. "
            f"Rotate 35% of upcoming deployment into Arbitrage/Liquid funds to protect capital."
        )
        unhedge = "Rebalance to 100% Equity when India VIX drops below 16.0 and crude cools below $82."
    elif macro_danger_score >= 45.0 or top_reg["id"] in ["2013_taper_tantrum", "2024_geopolitical_sticky_inflation"]:
        hedge_pct = 20.0
        posture = "Guarded Staggered Accumulation"
        hedge_cat = "Liquid Funds & Large-Cap Value"
        rationale = (
            f"Macro indicators exhibit moderate tension resembling {top_reg['name']} ({top_sim}% match). "
            f"Park 20% of new capital into Liquid funds to maintain dry powder for impending dip triggers."
        )
        unhedge = "Deploy parked dry powder into Small/Mid Cap equity when Nifty 50 approaches 200 EMA."
    else:
        hedge_pct = 0.0
        posture = "Unhedged Pure Equity Growth"
        hedge_cat = "Pure Equity (Small/Mid/Flexi Cap)"
        rationale = (
            f"Macro conditions reflect calm expansion ({top_reg['name']}, {top_sim}% similarity). "
            f"VIX is subdued ({vix:.1f}). No defensive hedging required; maintain 100% pure equity SIP."
        )
        unhedge = "No hedging active. Continue normal monthly SIP execution."

    hedging_plan = DynamicHedgingPlan(
        macro_danger_score=round(macro_danger_score, 1),
        recommended_hedge_pct=hedge_pct,
        hedge_category=hedge_cat,
        preservation_posture=posture,
        hedging_rationale=rationale,
        unhedge_exit_trigger=unhedge,
        safe_haven_funds=[
            {"category": "Arbitrage", "scheme_name": "Kotak Equity Arbitrage Fund - Direct Growth", "yield_est": "6.8% - 7.2% (Tax-efficient)"},
            {"category": "Liquid", "scheme_name": "Nippon India Liquid Fund - Direct Growth", "yield_est": "6.7% annualized"},
            {"category": "Gold ETF/Fund", "scheme_name": "Nippon India ETF Gold BeES", "yield_est": "Safe-Haven Inflation Hedge"},
        ],
    )

    ranked_list = [
        {
            "id": r["id"],
            "name": r["name"],
            "period": r["period"],
            "similarity_score": s,
            "drawdowns": r["drawdowns"],
            "recovery_months": r["recovery_months"],
        }
        for s, r in scored
    ]

    return MacroAnalogueReport(
        current_snapshot={
            "vix": vix,
            "crude": crude,
            "us10y": us10y,
            "usdinr": usdinr,
            "dxy": dxy,
        },
        top_analogue=top_match,
        runner_up=runner_match,
        hedging_plan=hedging_plan,
        ranked_analogues=ranked_list,
    )

