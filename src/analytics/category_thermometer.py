"""
src/analytics/category_thermometer.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Category Thermometer — "heat" of each mutual fund category.

Shows whether each category (Large Cap, Mid Cap, Small Cap, Flexi Cap,
Sectoral, etc.) is currently:
  - 🥶 COLD (historically cheap, great entry point)
  - 😐 WARM (fairly valued)
  - 🔥 HOT  (expensive, stretched valuations)
  - 🌋 OVERHEATED (extreme, bubble risk)

This is a portfolio-level tool: helps users see which categories to
overweight or underweight their SIPs in.

Thermometer logic per category:
  - Uses rolling 3Y CAGR percentile rank vs 10Y history
  - Uses max drawdown recovery status
  - Combines with market timing signal
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from .metrics import calculate_cagr, calculate_rolling_returns, calculate_max_drawdown


# ─────────────────────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CategoryTemperature:
    """Temperature reading for a single mutual fund category."""
    category: str
    temperature: float              # 0 (freezing) to 100 (burning)
    label: str                      # "COLD" / "WARM" / "HOT" / "OVERHEATED"
    emoji: str
    cagr_3y: float
    cagr_3y_percentile: float       # vs 10Y history
    max_drawdown: float
    in_recovery: bool               # Still below previous ATH?
    recovery_pct: float             # % recovered from last major drawdown
    sip_recommendation: str
    lumpsum_recommendation: str
    rationale: str


# ─────────────────────────────────────────────────────────────────────────────
# Temperature Calculation
# ─────────────────────────────────────────────────────────────────────────────

def _compute_rolling_percentile(nav: pd.Series, window_years: float = 3) -> float:
    """
    Compute the percentile of the current 3Y CAGR vs the last 10Y of 3Y CAGRs.
    0 = historically cheapest (low CAGRs in recent past), 100 = most expensive.
    """
    rolling = calculate_rolling_returns(nav, window_years=window_years)
    if rolling.empty or len(rolling) < 20:
        return 50.0

    current = rolling.iloc[-1]
    percentile = (rolling < current).mean() * 100
    return float(percentile)


def _recovery_status(nav: pd.Series) -> tuple[bool, float]:
    """
    Check if the NAV is still in recovery from its all-time high.

    Returns
    -------
    tuple: (in_recovery: bool, recovery_pct: float 0–100)
        100 = back at ATH, 0 = at the bottom of the drawdown.
    """
    nav = nav.sort_index().dropna()
    ath = nav.cummax().iloc[-1]
    current = nav.iloc[-1]

    if ath <= 0:
        return False, 100.0

    if current >= ath * 0.999:
        return False, 100.0  # At ATH

    # Find the trough after the last ATH
    peak_idx = nav.idxmax()
    post_peak = nav[nav.index >= peak_idx]
    trough = post_peak.min()

    if ath == trough:
        return False, 100.0

    recovery_pct = (current - trough) / (ath - trough) * 100
    return True, float(np.clip(recovery_pct, 0, 100))


def compute_category_temperature(
    category: str,
    representative_nav: pd.Series | pd.DataFrame,
) -> CategoryTemperature:
    """
    Compute the temperature for a single category.

    Parameters
    ----------
    category         : Category name (e.g., "Small Cap", "Large Cap").
    representative_nav : NAV series of a representative fund or category index.

    Returns
    -------
    CategoryTemperature
    """
    if isinstance(representative_nav, pd.DataFrame):
        representative_nav = representative_nav["nav"] if "nav" in representative_nav.columns else representative_nav.iloc[:, 0]
    nav = representative_nav.sort_index().dropna()
    if len(nav) < 50:
        return CategoryTemperature(
            category=category,
            temperature=50.0,
            label="WARM",
            emoji="😐",
            cagr_3y=float("nan"),
            cagr_3y_percentile=50.0,
            max_drawdown=float("nan"),
            in_recovery=False,
            recovery_pct=100.0,
            sip_recommendation="Insufficient data for category temperature.",
            lumpsum_recommendation="Insufficient data.",
            rationale="Less than 50 data points available.",
        )

    cagr_3y = calculate_cagr(nav, years=3)
    percentile = _compute_rolling_percentile(nav, window_years=3)
    mdd = calculate_max_drawdown(nav)
    in_recovery, recovery_pct = _recovery_status(nav)

    # Temperature formula:
    # High percentile (recent 3Y CAGR near historical peak) → HOT
    # Low percentile (3Y CAGR at historical trough) → COLD
    base_temp = percentile  # 0–100 directly from CAGR percentile

    # Adjust for recovery: deep in recovery from crash → COOLER (buy zone)
    if in_recovery and recovery_pct < 50:
        base_temp = max(0, base_temp - 20)  # extra cooling — it's a dip
    elif in_recovery and recovery_pct < 80:
        base_temp = max(0, base_temp - 10)

    temperature = round(float(np.clip(base_temp, 0, 100)), 1)

    # Labels
    if temperature >= 80:
        label, emoji = "OVERHEATED", "🌋"
        sip_rec = "Continue SIPs but do NOT add lump sum. Category is running very hot."
        lump_rec = "❌ Avoid lump sum. Valuations are stretched. Wait for a correction."
        rationale = f"3Y CAGR at {percentile:.0f}th percentile of historical range — near peak."
    elif temperature >= 60:
        label, emoji = "HOT", "🔥"
        sip_rec = "Maintain base SIPs. Reduce top-ups."
        lump_rec = "🟠 Exercise caution with lump sum. Markets are running above fair value."
        rationale = f"Category has had strong recent run ({cagr_3y*100:.1f}% 3Y CAGR). Premium to history."
    elif temperature >= 40:
        label, emoji = "WARM", "😐"
        sip_rec = "✅ Normal SIP is ideal. Category is fairly valued."
        lump_rec = "✅ Lump sum acceptable in tranches. Fair valuation zone."
        rationale = f"3Y CAGR at {percentile:.0f}th percentile — moderate historical range."
    elif temperature >= 20:
        label, emoji = "COLD", "❄️"
        sip_rec = "✅ Excellent for SIP. Increase SIP amount if possible."
        lump_rec = "✅ Strong lump sum opportunity. Category at attractive valuations."
        rationale = (
            f"Category is below historical averages ({percentile:.0f}th percentile). "
            + ("In recovery from drawdown — classic buying opportunity." if in_recovery else "")
        )
    else:
        label, emoji = "FREEZING", "🥶"
        sip_rec = "🟢 Maximum SIP opportunity. Category at historical lows."
        lump_rec = "🟢 Deploy significant lump sum. Generational buying opportunity if fundamentals intact."
        rationale = (
            f"Category at {percentile:.0f}th percentile — deeply below historical averages. "
            f"Max drawdown: {mdd*100:.1f}%. "
            + ("Heavily in recovery — extreme contrarian opportunity." if in_recovery else "")
        )

    return CategoryTemperature(
        category=category,
        temperature=temperature,
        label=label,
        emoji=emoji,
        cagr_3y=cagr_3y,
        cagr_3y_percentile=percentile,
        max_drawdown=mdd,
        in_recovery=in_recovery,
        recovery_pct=recovery_pct,
        sip_recommendation=sip_rec,
        lumpsum_recommendation=lump_rec,
        rationale=rationale,
    )


def run_thermometer(
    category_navs: dict[str, pd.Series],
) -> list[CategoryTemperature]:
    """
    Run thermometer across multiple categories.

    Parameters
    ----------
    category_navs : Dict mapping category name → representative NAV series.

    Returns
    -------
    list[CategoryTemperature] sorted hottest → coldest.
    """
    results = []
    for category, nav in category_navs.items():
        temp = compute_category_temperature(category, nav)
        results.append(temp)

    results.sort(key=lambda x: -x.temperature)
    return results


def format_thermometer_report(temps: list[CategoryTemperature]) -> str:
    """Format thermometer results as a readable dashboard."""
    lines = ["# 🌡️ Category Thermometer\n"]
    for t in temps:
        bar_len = int(t.temperature / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        lines.append(
            f"## {t.emoji} {t.category} — {t.label} ({t.temperature:.0f}/100)"
        )
        lines.append(f"  `[{bar}]` {t.temperature:.0f}°")
        if not np.isnan(t.cagr_3y):
            lines.append(f"  3Y CAGR: {t.cagr_3y*100:.1f}%  |  Percentile: {t.cagr_3y_percentile:.0f}th  |  MDD: {t.max_drawdown*100:.1f}%")
        if t.in_recovery:
            lines.append(f"  Recovery: {t.recovery_pct:.0f}% recovered from last drawdown")
        lines.append(f"  **SIP**: {t.sip_recommendation}")
        lines.append(f"  **Lump Sum**: {t.lumpsum_recommendation}")
        lines.append("")
    return "\n".join(lines)

