"""
src/analytics/macro_engine.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Downturn Probability Score Engine (0–100%).

Aggregates all macro signals into a single "Market Danger Score":
  - 0–20   : Low risk — green light
  - 20–45  : Moderate risk — cautious
  - 45–65  : Elevated risk — reduce lump sum
  - 65–80  : High risk — protect capital, dry powder mode
  - 80–100 : Crisis / Crash warning — maximum caution

Inputs:
  - Live macro snapshot (VIX, Crude, USD/INR, US 10Y, DXY, Gold)
  - Macro history for trend analysis
  - Scheduled event calendar (Budget, RBI MPC, FOMC)
  - News RSS sentiment (optional)
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

CALENDAR_PATH = Path(__file__).parent.parent / "data" / "macro_calendar.json"

# ─────────────────────────────────────────────────────────────────────────────
# Individual Signal Scorers  (each returns a danger contribution 0–100)
# ─────────────────────────────────────────────────────────────────────────────

def _vix_danger(vix: float | None) -> float:
    """VIX-based fear gauge. Higher VIX = higher danger."""
    if vix is None:
        return 20.0
    if vix >= 40:
        return 100.0
    if vix >= 30:
        return 75.0
    if vix >= 22:
        return 45.0
    if vix >= 18:
        return 25.0
    return 10.0


def _crude_danger(crude_change_pct: float | None, crude_level: float | None) -> float:
    """Crude oil shock and level-based danger."""
    danger = 0.0
    if crude_change_pct is not None:
        chg = abs(crude_change_pct)
        if chg >= 8:
            danger += 50
        elif chg >= 5:
            danger += 30
        elif chg >= 3:
            danger += 15
    if crude_level is not None:
        if crude_level >= 110:
            danger += 30
        elif crude_level >= 90:
            danger += 15
        elif crude_level <= 50:
            danger += 10  # deflation signal
    return min(danger, 100.0)


def _usdinr_danger(usdinr_change_pct: float | None, usdinr_level: float | None) -> float:
    """USD/INR rupee depreciation danger."""
    danger = 0.0
    if usdinr_change_pct is not None:
        chg = usdinr_change_pct  # positive = INR weakening (bad for India)
        if chg >= 2.0:
            danger += 60
        elif chg >= 1.0:
            danger += 35
        elif chg >= 0.5:
            danger += 15
        elif chg <= -1.5:
            danger += 5  # sharp INR strengthening also a signal of volatility
    if usdinr_level is not None:
        if usdinr_level >= 90:
            danger += 25
        elif usdinr_level >= 85:
            danger += 10
    return min(danger, 100.0)


def _us10y_danger(us10y: float | None) -> float:
    """US 10Y yield danger — high yields → global risk-off → EM outflows."""
    if us10y is None:
        return 15.0
    if us10y >= 5.5:
        return 80.0
    if us10y >= 5.0:
        return 55.0
    if us10y >= 4.5:
        return 30.0
    if us10y >= 4.0:
        return 15.0
    return 5.0


def _dxy_danger(dxy_change_pct: float | None, dxy_level: float | None) -> float:
    """Dollar Index danger — strong dollar = bad for EM equities."""
    danger = 0.0
    if dxy_change_pct is not None:
        if dxy_change_pct >= 1.5:
            danger += 40
        elif dxy_change_pct >= 0.8:
            danger += 20
    if dxy_level is not None:
        if dxy_level >= 110:
            danger += 30
        elif dxy_level >= 105:
            danger += 15
    return min(danger, 100.0)


def _gold_danger(gold_change_pct: float | None) -> float:
    """Gold surge as safe-haven signal — indicates fear / flight to safety."""
    if gold_change_pct is None:
        return 5.0
    if gold_change_pct >= 3.0:
        return 55.0
    if gold_change_pct >= 1.5:
        return 30.0
    if gold_change_pct >= 0.8:
        return 12.0
    return 2.0


def _calendar_danger(upcoming_days: int = 7) -> float:
    """
    Check if a high-volatility scheduled event is within `upcoming_days` days.
    Reads from macro_calendar.json.

    Returns danger contribution (0–40).
    """
    if not CALENDAR_PATH.exists():
        return 0.0

    try:
        with open(CALENDAR_PATH) as f:
            events = json.load(f)
    except Exception:
        return 0.0

    today = date.today()
    threshold = today + timedelta(days=upcoming_days)
    max_danger = 0.0

    for ev in events:
        try:
            ev_date = date.fromisoformat(ev["date"])
        except Exception:
            continue

        if today <= ev_date <= threshold:
            volatility_hint = ev.get("historical_volatility_impact", "low").lower()
            if "high" in volatility_hint:
                max_danger = max(max_danger, 40.0)
            elif "medium" in volatility_hint:
                max_danger = max(max_danger, 20.0)
            elif "low" in volatility_hint:
                max_danger = max(max_danger, 8.0)

    return max_danger


# ─────────────────────────────────────────────────────────────────────────────
# Trend Component — 30-day deterioration check
# ─────────────────────────────────────────────────────────────────────────────

def _trend_danger(macro_df: pd.DataFrame | None) -> float:
    """
    Compare current macro state vs 30-day average.
    If conditions are deteriorating, add danger.

    Parameters
    ----------
    macro_df : DataFrame with columns matching macro_snapshot keys, indexed by date.

    Returns
    -------
    float : 0–30 trend danger.
    """
    if macro_df is None or macro_df.empty:
        return 0.0

    danger = 0.0
    recent_30 = macro_df.iloc[-30:] if len(macro_df) >= 30 else macro_df
    if recent_30.empty:
        return 0.0

    # VIX trending up
    if "vix" in recent_30.columns:
        vix_slope = recent_30["vix"].diff().mean()
        if vix_slope > 0.3:
            danger += 10
        elif vix_slope > 0.1:
            danger += 5

    # USD/INR trending up (depreciation)
    if "usdinr" in recent_30.columns:
        inr_slope = recent_30["usdinr"].diff().mean()
        if inr_slope > 0.05:
            danger += 10
        elif inr_slope > 0.02:
            danger += 5

    # US10Y trending up
    if "us10y" in recent_30.columns:
        bond_slope = recent_30["us10y"].diff().mean()
        if bond_slope > 0.02:
            danger += 10
        elif bond_slope > 0.01:
            danger += 5

    return min(danger, 30.0)


# ─────────────────────────────────────────────────────────────────────────────
# Unified Danger Score
# ─────────────────────────────────────────────────────────────────────────────

# Weights for each danger component
_DANGER_WEIGHTS = {
    "vix": 0.25,
    "crude": 0.18,
    "usdinr": 0.18,
    "us10y": 0.15,
    "dxy": 0.10,
    "gold": 0.06,
    "calendar": 0.05,
    "trend": 0.03,
}


def compute_downturn_probability(
    macro_snapshot: dict[str, Any],
    macro_df: pd.DataFrame | None = None,
) -> dict:
    """
    Compute the overall Downturn Probability Score (0–100%).

    Parameters
    ----------
    macro_snapshot : Latest macro data dict (from macro_client).
    macro_df       : Optional historical macro DataFrame for trend analysis.

    Returns
    -------
    dict with keys:
      - danger_score       : 0–100 overall danger level
      - risk_level         : str label (LOW / MODERATE / ELEVATED / HIGH / CRISIS)
      - component_dangers  : individual component danger scores
      - active_alerts      : list of triggered alert strings
      - dry_powder_pct     : recommended % of investable capital to keep in liquid fund
      - summary            : human-readable summary paragraph
    """
    components: dict[str, float] = {}

    components["vix"] = _vix_danger(macro_snapshot.get("vix"))
    components["crude"] = _crude_danger(
        macro_snapshot.get("crude_change_pct"),
        macro_snapshot.get("crude"),
    )
    components["usdinr"] = _usdinr_danger(
        macro_snapshot.get("usdinr_change_pct"),
        macro_snapshot.get("usdinr"),
    )
    components["us10y"] = _us10y_danger(macro_snapshot.get("us10y"))
    components["dxy"] = _dxy_danger(
        macro_snapshot.get("dxy_change_pct"),
        macro_snapshot.get("dxy"),
    )
    components["gold"] = _gold_danger(macro_snapshot.get("gold_change_pct"))
    components["calendar"] = _calendar_danger()
    components["trend"] = _trend_danger(macro_df)

    # Weighted sum
    total = sum(_DANGER_WEIGHTS[k] * components[k] for k in _DANGER_WEIGHTS)
    total = round(float(np.clip(total, 0, 100)), 1)

    # Risk level
    if total < 20:
        risk_level = "🟢 LOW"
        dry_powder_pct = 0
        summary = "Macro environment is calm. Full deployment into equity SIPs is appropriate."
    elif total < 40:
        risk_level = "🟡 MODERATE"
        dry_powder_pct = 10
        summary = "Some macro stress present. Continue SIPs normally. Hold 10% in liquid as buffer."
    elif total < 60:
        risk_level = "🟠 ELEVATED"
        dry_powder_pct = 20
        summary = "Elevated macro risk detected. Reduce lump-sum deployments. Hold 20% dry powder."
    elif total < 75:
        risk_level = "🔴 HIGH"
        dry_powder_pct = 35
        summary = "High macro danger — multiple signals flashing. Protect capital. 35% dry powder in liquid fund."
    else:
        risk_level = "☠️ CRISIS"
        dry_powder_pct = 50
        summary = "Crisis-level signals active. Hold 50% in liquid fund. Minimum SIP continuation only."

    # Collect active alerts
    alerts: list[str] = []
    if (macro_snapshot.get("vix") or 0) > 25:
        alerts.append(f"⚠️ VIX elevated at {macro_snapshot['vix']:.1f}")
    if abs(macro_snapshot.get("crude_change_pct") or 0) > 4:
        alerts.append(f"⚠️ Crude oil shock: {macro_snapshot.get('crude_change_pct', 0):.1f}% move")
    if (macro_snapshot.get("usdinr_change_pct") or 0) > 0.8:
        alerts.append(f"⚠️ INR depreciating fast: {macro_snapshot.get('usdinr_change_pct', 0):.2f}% drop")
    if (macro_snapshot.get("us10y") or 0) > 4.8:
        alerts.append(f"⚠️ US 10Y yield high at {macro_snapshot.get('us10y', 0):.2f}%")
    if components["calendar"] >= 20:
        alerts.append("📅 High-volatility macro event approaching (Budget / RBI MPC / FOMC)")

    return {
        "danger_score": total,
        "risk_level": risk_level,
        "component_dangers": {k: round(v, 1) for k, v in components.items()},
        "active_alerts": alerts,
        "dry_powder_pct": dry_powder_pct,
        "summary": summary,
    }

