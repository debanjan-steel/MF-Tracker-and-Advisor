"""
src/analytics/goal_planner.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Goal-Based De-Risking Glide Path Planner.

As the user approaches a financial goal (retirement, house, education),
the engine automatically recommends shifting equity → liquid/arbitrage fund
to protect accumulated gains.

Glide path logic:
  - >5 years to goal  : 100% equity (full growth mode)
  - 3–5 years         : 85% equity / 15% liquid
  - 2–3 years         : 70% equity / 30% liquid
  - 1–2 years         : 50% equity / 50% liquid
  - 6–12 months       : 25% equity / 75% liquid
  - <6 months         : 5% equity / 95% liquid (near-full capital protection)

Also includes:
  - Goal corpus calculator (how much to invest monthly to reach target)
  - Inflation-adjusted goal projection
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

import numpy as np


# ─────────────────────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FinancialGoal:
    """Represents a user-defined financial goal."""
    name: str                           # e.g., "Retirement", "Child Education"
    target_corpus: float                # Target amount in ₹
    target_date: date                   # When they need the money
    current_corpus: float = 0.0        # Already accumulated towards this goal
    expected_equity_return: float = 0.12    # 12% p.a. default for Indian equity
    expected_liquid_return: float = 0.07    # 7% p.a. for liquid/arbitrage fund
    inflation_rate: float = 0.06        # 6% inflation for goal adjustment


@dataclass
class GlidePathRecommendation:
    """Output of the glide path calculation."""
    goal_name: str
    years_remaining: float
    equity_pct: float               # 0–100 (e.g., 70 = 70% in equity)
    liquid_pct: float               # 0–100 (e.g., 30 = 30% in liquid fund)
    monthly_sip_required: float     # ₹/month to reach goal
    projected_corpus: float         # What current plan will yield
    goal_gap: float                 # Shortfall (negative = surplus)
    de_risk_action: str             # What to do right now
    milestone_alerts: list[str] = field(default_factory=list)
    glide_path_schedule: list[dict] = field(default_factory=list)  # year-by-year


# ─────────────────────────────────────────────────────────────────────────────
# Glide Path Engine
# ─────────────────────────────────────────────────────────────────────────────

# De-risking schedule: (years_to_goal_threshold, equity_pct, liquid_pct)
_GLIDE_STEPS = [
    (5.0,  100, 0),
    (3.0,  85,  15),
    (2.0,  70,  30),
    (1.0,  50,  50),
    (0.5,  25,  75),
    (0.0,  5,   95),
]


def get_allocation_for_horizon(years_remaining: float) -> tuple[float, float]:
    """
    Return (equity_pct, liquid_pct) for given years remaining to goal.

    Returns
    -------
    tuple[float, float] : (equity_pct, liquid_pct)
    """
    for threshold, eq, lq in _GLIDE_STEPS:
        if years_remaining >= threshold:
            return float(eq), float(lq)
    return 5.0, 95.0  # <6 months


def compute_years_remaining(target_date: date) -> float:
    today = date.today()
    delta_days = (target_date - today).days
    return max(0.0, delta_days / 365.25)


def calculate_required_monthly_sip(
    target_corpus: float,
    current_corpus: float,
    years_remaining: float,
    equity_pct: float,
    expected_equity_return: float,
    expected_liquid_return: float,
) -> float:
    """
    Calculate required monthly SIP to reach target corpus.

    Uses blended return based on equity/liquid allocation.

    Returns
    -------
    float : Monthly SIP required in ₹.
    """
    if years_remaining <= 0:
        return max(0.0, target_corpus - current_corpus)

    eq_weight = equity_pct / 100
    lq_weight = (100 - equity_pct) / 100
    annual_return = eq_weight * expected_equity_return + lq_weight * expected_liquid_return
    monthly_rate = (1 + annual_return) ** (1 / 12) - 1
    n = int(years_remaining * 12)

    if n == 0:
        return max(0.0, target_corpus - current_corpus)

    # Future value of current corpus
    fv_current = current_corpus * (1 + monthly_rate) ** n

    # Remaining needed from SIPs
    remaining = target_corpus - fv_current
    if remaining <= 0:
        return 0.0

    # PMT formula: remaining = SIP × [(1+r)^n - 1] / r × (1+r)
    if monthly_rate == 0:
        return remaining / n

    fv_factor = ((1 + monthly_rate) ** n - 1) / monthly_rate * (1 + monthly_rate)
    return remaining / fv_factor


def build_glide_path_schedule(goal: FinancialGoal) -> list[dict]:
    """
    Build a year-by-year de-risking schedule from now to goal date.

    Returns
    -------
    list[dict] : Each dict has 'year', 'years_remaining', 'equity_pct', 'liquid_pct', 'milestone'.
    """
    schedule = []
    today = date.today()
    total_years = compute_years_remaining(goal.target_date)

    for yr_offset in range(int(total_years) + 1):
        future_date = date(today.year + yr_offset, today.month, today.day)
        yr_remaining = compute_years_remaining(goal.target_date) - yr_offset
        yr_remaining = max(0.0, yr_remaining)
        eq_pct, lq_pct = get_allocation_for_horizon(yr_remaining)

        milestone = ""
        if yr_remaining <= 0.5:
            milestone = "⚡ FINAL PHASE — Protect capital, near-full liquid"
        elif yr_remaining <= 1.0:
            milestone = "🔴 DE-RISK NOW — Move 50% to liquid"
        elif yr_remaining <= 2.0:
            milestone = "🟠 REDUCE EQUITY — Move 30% to liquid"
        elif yr_remaining <= 3.0:
            milestone = "🟡 BEGIN SHIFTING — 15% into liquid fund"

        schedule.append({
            "year": future_date.year,
            "years_remaining": round(yr_remaining, 1),
            "equity_pct": eq_pct,
            "liquid_pct": lq_pct,
            "milestone": milestone,
        })

    return schedule


def generate_glide_path_recommendation(goal: FinancialGoal) -> GlidePathRecommendation:
    """
    Full glide path recommendation for a financial goal.

    Parameters
    ----------
    goal : FinancialGoal object.

    Returns
    -------
    GlidePathRecommendation
    """
    years_remaining = compute_years_remaining(goal.target_date)
    equity_pct, liquid_pct = get_allocation_for_horizon(years_remaining)

    # Required SIP
    monthly_sip = calculate_required_monthly_sip(
        target_corpus=goal.target_corpus,
        current_corpus=goal.current_corpus,
        years_remaining=years_remaining,
        equity_pct=equity_pct,
        expected_equity_return=goal.expected_equity_return,
        expected_liquid_return=goal.expected_liquid_return,
    )

    # Projected corpus (if current SIP continues)
    # (Here we calculate what the current allocation + SIP will produce)
    n = int(years_remaining * 12)
    eq_weight = equity_pct / 100
    lq_weight = liquid_pct / 100
    blended_annual = eq_weight * goal.expected_equity_return + lq_weight * goal.expected_liquid_return
    monthly_r = (1 + blended_annual) ** (1 / 12) - 1

    if n > 0 and monthly_r > 0:
        projected = (goal.current_corpus * (1 + monthly_r) ** n +
                     monthly_sip * ((1 + monthly_r) ** n - 1) / monthly_r * (1 + monthly_r))
    else:
        projected = goal.current_corpus

    goal_gap = projected - goal.target_corpus

    # De-risk action text
    if equity_pct >= 100:
        action = "✅ Full equity mode — no de-risking needed yet. Focus on growing your corpus."
    elif equity_pct >= 85:
        action = f"🟡 Shift 15% of your equity holdings into a liquid/arbitrage fund now."
    elif equity_pct >= 70:
        action = f"🟠 Move 30% of equity allocation into liquid fund. Review equity selections."
    elif equity_pct >= 50:
        action = f"🔴 De-risk to 50/50. Move half your equity corpus to liquid fund immediately."
    elif equity_pct >= 25:
        action = f"🚨 High urgency — keep only 25% in equity. Move 75% to liquid/FD for capital safety."
    else:
        action = f"☠️ GOAL IMMINENT — Move 95% to savings/FD. Equity exposure nearly zero."

    # Milestone alerts
    alerts = []
    if years_remaining <= 1.0 and equity_pct > 50:
        alerts.append("⚠️ Goal is within 1 year but equity exposure is still high!")
    if goal_gap < 0:
        alerts.append(f"⚠️ Projected corpus ₹{projected:,.0f} is ₹{abs(goal_gap):,.0f} SHORT of target!")
    if years_remaining <= 0:
        alerts.append("🎯 Goal date has passed! Take action on your corpus.")

    schedule = build_glide_path_schedule(goal)

    return GlidePathRecommendation(
        goal_name=goal.name,
        years_remaining=round(years_remaining, 1),
        equity_pct=equity_pct,
        liquid_pct=liquid_pct,
        monthly_sip_required=round(monthly_sip, 2),
        projected_corpus=round(projected, 2),
        goal_gap=round(goal_gap, 2),
        de_risk_action=action,
        milestone_alerts=alerts,
        glide_path_schedule=schedule,
    )


def format_goal_report(rec: GlidePathRecommendation) -> str:
    """Format a goal recommendation as human-readable text."""
    gap_str = (
        f"**SURPLUS**: ₹{rec.goal_gap:,.0f} ahead of target 🎉"
        if rec.goal_gap >= 0
        else f"**SHORTFALL**: ₹{abs(rec.goal_gap):,.0f} behind target ⚠️"
    )
    lines = [
        f"# 🎯 Goal: {rec.goal_name}",
        f"**Time Remaining**: {rec.years_remaining:.1f} years",
        f"**Allocation**: {rec.equity_pct:.0f}% Equity / {rec.liquid_pct:.0f}% Liquid",
        f"**Monthly SIP Required**: ₹{rec.monthly_sip_required:,.0f}",
        f"**Projected Corpus**: ₹{rec.projected_corpus:,.0f}",
        gap_str,
        f"\n**Action**: {rec.de_risk_action}",
    ]
    if rec.milestone_alerts:
        lines.append("\n**⚠️ Alerts**:")
        for a in rec.milestone_alerts:
            lines.append(f"  - {a}")
    return "\n".join(lines)

