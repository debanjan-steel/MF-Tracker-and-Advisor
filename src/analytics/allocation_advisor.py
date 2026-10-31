"""
src/analytics/allocation_advisor.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Unified Allocation Posture Advisor.

Combines the Market Timing Score + Macro Danger Score + Goal Glide Paths
into a single actionable allocation posture:

  Posture A — AGGRESSIVE   : 100% equity, max SIP deployment
  Posture B — GROWTH       : 90% equity, standard SIPs
  Posture C — BALANCED     : 75% equity, reduce lump sum
  Posture D — DEFENSIVE    : 60% equity, hold dry powder
  Posture E — CAPITAL SAFE : 40% equity, maximum dry powder in liquid fund

Also handles:
  - Per-category overweight / underweight recommendations
  - SIP multiplier per fund based on thermometer temperature
  - Hero capital deployment planner (large lump sums)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


# ─────────────────────────────────────────────────────────────────────────────
# Posture Definitions
# ─────────────────────────────────────────────────────────────────────────────

POSTURES = {
    "AGGRESSIVE": {
        "equity_pct": 100,
        "liquid_pct": 0,
        "sip_multiplier": 1.5,
        "lumpsum_allowed": True,
        "emoji": "🚀",
        "description": "Full throttle equity. Market is deeply attractive — deploy maximum capital.",
    },
    "GROWTH": {
        "equity_pct": 90,
        "liquid_pct": 10,
        "sip_multiplier": 1.2,
        "lumpsum_allowed": True,
        "emoji": "📈",
        "description": "Strong growth posture. Equity-dominant with a small liquid buffer.",
    },
    "BALANCED": {
        "equity_pct": 75,
        "liquid_pct": 25,
        "sip_multiplier": 1.0,
        "lumpsum_allowed": False,
        "emoji": "⚖️",
        "description": "Balanced posture. Stick to SIP plan, avoid fresh lump sums.",
    },
    "DEFENSIVE": {
        "equity_pct": 60,
        "liquid_pct": 40,
        "sip_multiplier": 0.75,
        "lumpsum_allowed": False,
        "emoji": "🛡️",
        "description": "Defensive mode. Reduce equity exposure, park 40% in liquid fund.",
    },
    "CAPITAL_SAFE": {
        "equity_pct": 40,
        "liquid_pct": 60,
        "sip_multiplier": 0.5,
        "lumpsum_allowed": False,
        "emoji": "🏦",
        "description": "Capital safety mode. Macro crisis or extreme valuations detected. Minimum equity.",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Posture Selection
# ─────────────────────────────────────────────────────────────────────────────

def select_posture(
    timing_score: float,
    danger_score: float,
    goal_equity_cap: Optional[float] = None,
) -> str:
    """
    Select the appropriate allocation posture.

    Parameters
    ----------
    timing_score     : 0–100 from timing_model.compute_timing_score()
    danger_score     : 0–100 from macro_engine.compute_downturn_probability()
    goal_equity_cap  : Max equity % from goal glide path (None = no cap)

    Returns
    -------
    str : Posture key ("AGGRESSIVE", "GROWTH", "BALANCED", "DEFENSIVE", "CAPITAL_SAFE")
    """
    # Convert to a combined "opportunity" score (higher = more equity)
    opportunity = timing_score * 0.6 + (100 - danger_score) * 0.4

    if opportunity >= 75:
        posture = "AGGRESSIVE"
    elif opportunity >= 60:
        posture = "GROWTH"
    elif opportunity >= 45:
        posture = "BALANCED"
    elif opportunity >= 30:
        posture = "DEFENSIVE"
    else:
        posture = "CAPITAL_SAFE"

    # Apply goal equity cap override
    if goal_equity_cap is not None:
        posture_equity = POSTURES[posture]["equity_pct"]
        if posture_equity > goal_equity_cap:
            # Downgrade posture until equity cap is satisfied
            for p_key in ["CAPITAL_SAFE", "DEFENSIVE", "BALANCED", "GROWTH", "AGGRESSIVE"]:
                if POSTURES[p_key]["equity_pct"] <= goal_equity_cap:
                    posture = p_key
                    break

    return posture


@dataclass
class AllocationAdvice:
    """Full allocation advice output."""
    posture: str
    equity_pct: float
    liquid_pct: float
    sip_multiplier: float
    lumpsum_allowed: bool
    emoji: str
    description: str
    timing_score: float
    danger_score: float
    opportunity_score: float
    category_weights: dict[str, float] = field(default_factory=dict)
    action_items: list[str] = field(default_factory=list)
    hero_deployment_plan: Optional[dict] = None


def compute_allocation_advice(
    timing_score: float,
    danger_score: float,
    category_temperatures: dict[str, float] | None = None,
    goal_equity_cap: float | None = None,
    hero_capital: float | None = None,
) -> AllocationAdvice:
    """
    Generate a full allocation advice package.

    Parameters
    ----------
    timing_score          : 0–100 market timing score.
    danger_score          : 0–100 macro danger score.
    category_temperatures : Dict of {category: temperature_0_to_100} (optional).
    goal_equity_cap       : Max equity % from goal glide path (optional).
    hero_capital          : Large lump sum to deploy (₹, optional).

    Returns
    -------
    AllocationAdvice
    """
    opportunity_score = timing_score * 0.6 + (100 - danger_score) * 0.4
    posture_key = select_posture(timing_score, danger_score, goal_equity_cap)
    posture = POSTURES[posture_key]

    action_items: list[str] = []

    # Build category overweight / underweight recommendations
    category_weights: dict[str, float] = {}
    if category_temperatures:
        cold_cats = [c for c, t in category_temperatures.items() if t < 40]
        hot_cats = [c for c, t in category_temperatures.items() if t > 65]

        for cat, temp in category_temperatures.items():
            if temp < 30:
                weight = 1.5
                action_items.append(f"📈 OVERWEIGHT {cat} — category is cold ({temp:.0f}/100). Increase SIP allocation.")
            elif temp < 50:
                weight = 1.2
            elif temp < 65:
                weight = 1.0
            elif temp < 80:
                weight = 0.75
                action_items.append(f"📉 UNDERWEIGHT {cat} — category is hot ({temp:.0f}/100). Reduce SIP allocation.")
            else:
                weight = 0.5
                action_items.append(f"⛔ AVOID fresh investment in {cat} — category is overheated ({temp:.0f}/100).")
            category_weights[cat] = weight

    # Standard action items per posture
    if posture_key == "AGGRESSIVE":
        action_items.insert(0, "🚀 Deploy maximum SIP + lump sum. Market conditions are optimal.")
    elif posture_key == "GROWTH":
        action_items.insert(0, "📈 Increase SIP by 20%. Lump sum in tranches over 2–3 months.")
    elif posture_key == "BALANCED":
        action_items.insert(0, "⚖️ Maintain base SIPs. Hold all dry powder in liquid fund.")
    elif posture_key == "DEFENSIVE":
        action_items.insert(0, "🛡️ Reduce SIP by 25%. Move 40% of investable capital to liquid fund.")
        action_items.append("⚠️ Do NOT deploy any lump sum until posture improves.")
    else:
        action_items.insert(0, "🏦 Minimum SIPs only. Protect capital. 60% in liquid/arbitrage fund.")
        action_items.append("☠️ Macro environment or valuations are extreme. Patience is strategy.")

    # Hero capital deployment plan
    hero_plan = None
    if hero_capital and hero_capital > 0:
        hero_plan = _hero_deployment_plan(
            hero_capital=hero_capital,
            posture_key=posture_key,
            timing_score=timing_score,
            category_weights=category_weights,
        )

    return AllocationAdvice(
        posture=posture_key,
        equity_pct=float(posture["equity_pct"]),
        liquid_pct=float(posture["liquid_pct"]),
        sip_multiplier=float(posture["sip_multiplier"]),
        lumpsum_allowed=bool(posture["lumpsum_allowed"]),
        emoji=posture["emoji"],
        description=posture["description"],
        timing_score=round(timing_score, 1),
        danger_score=round(danger_score, 1),
        opportunity_score=round(opportunity_score, 1),
        category_weights=category_weights,
        action_items=action_items,
        hero_deployment_plan=hero_plan,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Hero Capital Deployment Planner (Task 3.11)
# ─────────────────────────────────────────────────────────────────────────────

def _hero_deployment_plan(
    hero_capital: float,
    posture_key: str,
    timing_score: float,
    category_weights: dict[str, float],
) -> dict:
    """
    Plan phased deployment of a large lump sum ("hero capital").

    Splits into tranches based on posture:
      - AGGRESSIVE : Deploy 100% immediately (1 tranche)
      - GROWTH     : 50% now + 50% over 2 months
      - BALANCED   : 33% / 33% / 33% over 3 months
      - DEFENSIVE  : 25% × 4 months
      - CAPITAL_SAFE: Hold 80% in liquid, deploy 20% over 6 months
    """
    tranche_plans = {
        "AGGRESSIVE":   [(1.0, "Month 1 — Deploy immediately")],
        "GROWTH":       [(0.50, "Month 1"), (0.50, "Month 2")],
        "BALANCED":     [(0.34, "Month 1"), (0.33, "Month 2"), (0.33, "Month 3")],
        "DEFENSIVE":    [(0.25, "Month 1"), (0.25, "Month 2"), (0.25, "Month 3"), (0.25, "Month 4")],
        "CAPITAL_SAFE": [(0.05, f"Month {i+1}") for i in range(4)] + [(0.80, "Keep in liquid fund till posture improves")],
    }

    tranches = tranche_plans.get(posture_key, tranche_plans["BALANCED"])
    tranche_amounts = [
        {"label": label, "amount": round(hero_capital * pct, 2), "pct": round(pct * 100)}
        for pct, label in tranches
    ]

    # Category split for equity tranche (weighted by temperature)
    equity_pct = POSTURES[posture_key]["equity_pct"] / 100
    equity_capital = hero_capital * equity_pct

    category_split: dict[str, float] = {}
    if category_weights:
        total_weight = sum(category_weights.values())
        for cat, w in category_weights.items():
            category_split[cat] = round(equity_capital * (w / total_weight), 2)
    else:
        category_split["Recommended Funds (no thermometer data)"] = round(equity_capital, 2)

    return {
        "total_capital": hero_capital,
        "equity_amount": round(equity_capital, 2),
        "liquid_amount": round(hero_capital * (1 - equity_pct), 2),
        "tranches": tranche_amounts,
        "category_split": category_split,
        "note": (
            f"Deploy ₹{hero_capital:,.0f} in {len(tranches)} tranche(s). "
            f"Timing score: {timing_score:.0f}/100 → {posture_key} posture."
        ),
    }


def format_advice_report(advice: AllocationAdvice) -> str:
    """Format allocation advice as readable text."""
    lines = [
        f"# {advice.emoji} Allocation Posture: {advice.posture}",
        f"**{advice.description}**\n",
        f"| Signal | Score |",
        f"|--------|-------|",
        f"| Market Timing | {advice.timing_score}/100 |",
        f"| Macro Danger | {advice.danger_score}/100 |",
        f"| Opportunity Score | {advice.opportunity_score:.0f}/100 |",
        f"\n**Recommended Allocation**: {advice.equity_pct:.0f}% Equity / {advice.liquid_pct:.0f}% Liquid",
        f"**SIP Multiplier**: {advice.sip_multiplier}×",
        f"**Lump Sum**: {'✅ Allowed' if advice.lumpsum_allowed else '❌ Not Recommended'}",
    ]

    if advice.action_items:
        lines.append("\n## 📋 Action Items")
        for item in advice.action_items:
            lines.append(f"  - {item}")

    if advice.hero_deployment_plan:
        hp = advice.hero_deployment_plan
        lines.append(f"\n## 💰 Hero Capital Deployment Plan")
        lines.append(f"  Total: ₹{hp['total_capital']:,.0f} | Equity: ₹{hp['equity_amount']:,.0f} | Liquid: ₹{hp['liquid_amount']:,.0f}")
        lines.append("  **Tranches**:")
        for t in hp["tranches"]:
            lines.append(f"    - {t['label']}: ₹{t['amount']:,.0f} ({t['pct']}%)")

    return "\n".join(lines)

