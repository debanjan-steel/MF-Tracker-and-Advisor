"""
src/analytics/portfolio_xray.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Portfolio Sector & Thematic X-Ray.

Analyses the user's mutual fund portfolio for:
  1. Sector concentration (Technology, Banking, Healthcare, etc.)
  2. Thematic overlap between funds (multiple funds holding the same sector)
  3. Hidden concentration risk (e.g., 60% of portfolio in banking)
  4. Market-cap distribution (Large / Mid / Small cap exposure)
  5. Overlap score between any two funds

Data source: AMFI / fund factsheet sector disclosures.
Limitations: Fund house factsheets update monthly — data may lag by up to 30 days.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FundHolding:
    """A single fund in the user's portfolio."""
    scheme_code: int
    scheme_name: str
    current_value: float                  # ₹ current market value
    category: str                         # "Large Cap", "Mid Cap", etc.
    # Sector allocation as % (dict keys are sector names, values sum to ~100)
    sector_allocation: dict[str, float] = field(default_factory=dict)
    # Market cap allocation as % (Large/Mid/Small/Cash)
    market_cap_allocation: dict[str, float] = field(default_factory=dict)


@dataclass
class XRayResult:
    """Aggregated X-Ray analysis of the full portfolio."""
    total_portfolio_value: float
    # Weighted sector exposure across all funds
    sector_exposure: dict[str, float]
    # Weighted market cap exposure
    market_cap_exposure: dict[str, float]
    # Category distribution
    category_distribution: dict[str, float]
    # Overlap matrix between fund pairs (fund_a, fund_b) → overlap_score
    overlap_matrix: dict[str, float]
    # Concentration alerts
    concentration_alerts: list[str]
    # Thematic clusters
    thematic_clusters: list[str]
    # Diversification score 0–100
    diversification_score: float
    summary: str


# ─────────────────────────────────────────────────────────────────────────────
# Known Indian Market Sector Taxonomy
# ─────────────────────────────────────────────────────────────────────────────

SECTOR_THEMES = {
    "Financials": ["Banking", "Finance", "Insurance", "NBFC", "Financial Services"],
    "Technology": ["IT", "Technology", "Software", "Telecom", "Internet"],
    "Healthcare": ["Pharma", "Healthcare", "Hospitals", "Diagnostics"],
    "Consumption": ["FMCG", "Retail", "Consumer Durables", "Automobiles"],
    "Infrastructure": ["Real Estate", "Construction", "Infrastructure", "Cement"],
    "Energy": ["Oil & Gas", "Power", "Energy", "Utilities"],
    "Industrials": ["Capital Goods", "Defence", "Engineering", "Manufacturing"],
    "Materials": ["Metals", "Mining", "Chemicals", "Fertilizers"],
}

CONCENTRATION_THRESHOLD = 35.0  # Alert if any single sector > 35%
OVERLAP_HIGH_THRESHOLD = 70.0   # High overlap between 2 funds (%)


# ─────────────────────────────────────────────────────────────────────────────
# Sector Overlap Calculation
# ─────────────────────────────────────────────────────────────────────────────

def compute_overlap_score(
    fund_a_sectors: dict[str, float],
    fund_b_sectors: dict[str, float],
) -> float:
    """
    Cosine-similarity-based overlap between two funds' sector allocations.
    Returns 0–100 (100 = identical portfolios).
    """
    all_sectors = set(fund_a_sectors) | set(fund_b_sectors)
    if not all_sectors:
        return 0.0

    vec_a = np.array([fund_a_sectors.get(s, 0.0) for s in all_sectors])
    vec_b = np.array([fund_b_sectors.get(s, 0.0) for s in all_sectors])

    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    cosine_sim = np.dot(vec_a, vec_b) / (norm_a * norm_b)
    return float(np.clip(cosine_sim * 100, 0, 100))


# ─────────────────────────────────────────────────────────────────────────────
# Main X-Ray Engine
# ─────────────────────────────────────────────────────────────────────────────

def run_portfolio_xray(holdings: list[FundHolding]) -> XRayResult:
    """
    Run a full Portfolio X-Ray analysis.

    Parameters
    ----------
    holdings : List of FundHolding objects (user's portfolio).

    Returns
    -------
    XRayResult
    """
    if not holdings:
        return XRayResult(
            total_portfolio_value=0.0,
            sector_exposure={},
            market_cap_exposure={},
            category_distribution={},
            overlap_matrix={},
            concentration_alerts=["No holdings provided."],
            thematic_clusters=[],
            diversification_score=0.0,
            summary="Portfolio is empty.",
        )

    total_value = sum(h.current_value for h in holdings)

    # ── Weighted sector exposure ──
    aggregated_sectors: dict[str, float] = {}
    for h in holdings:
        weight = h.current_value / total_value
        for sector, pct in h.sector_allocation.items():
            aggregated_sectors[sector] = aggregated_sectors.get(sector, 0.0) + (pct * weight)

    # ── Weighted market cap exposure ──
    aggregated_mktcap: dict[str, float] = {}
    for h in holdings:
        weight = h.current_value / total_value
        for cap, pct in h.market_cap_allocation.items():
            aggregated_mktcap[cap] = aggregated_mktcap.get(cap, 0.0) + (pct * weight)

    # ── Category distribution ──
    category_dist: dict[str, float] = {}
    for h in holdings:
        cat = h.category
        category_dist[cat] = category_dist.get(cat, 0.0) + (h.current_value / total_value * 100)

    # ── Overlap matrix ──
    overlap_matrix: dict[str, float] = {}
    for i, ha in enumerate(holdings):
        for j, hb in enumerate(holdings):
            if j <= i:
                continue
            key = f"{ha.scheme_name[:20]}…  ↔  {hb.scheme_name[:20]}…"
            overlap_matrix[key] = compute_overlap_score(
                ha.sector_allocation, hb.sector_allocation
            )

    # ── Concentration alerts ──
    alerts: list[str] = []

    for sector, pct in aggregated_sectors.items():
        if pct > CONCENTRATION_THRESHOLD:
            alerts.append(
                f"⚠️ HIGH CONCENTRATION: {sector} makes up {pct:.1f}% of portfolio — "
                f"above the {CONCENTRATION_THRESHOLD}% alert threshold."
            )

    for pair, score in overlap_matrix.items():
        if score > OVERLAP_HIGH_THRESHOLD:
            alerts.append(
                f"🔁 HIGH OVERLAP ({score:.0f}%): {pair} — these funds hold similar stocks. "
                f"Consider removing one to reduce duplication."
            )

    if len(holdings) < 3:
        alerts.append(
            "⚠️ Under-diversified: portfolio has fewer than 3 funds. "
            "Consider adding funds across categories."
        )

    # ── Thematic clusters ──
    thematic_clusters: list[str] = []
    for theme, sectors in SECTOR_THEMES.items():
        theme_exposure = sum(
            aggregated_sectors.get(s, 0.0) for s in sectors
        )
        if theme_exposure > 25:
            thematic_clusters.append(
                f"📌 {theme}: {theme_exposure:.1f}% portfolio exposure"
            )

    # ── Diversification score ──
    # Based on: sector concentration (HHI), fund count, category mix
    sector_values = list(aggregated_sectors.values())
    if sector_values:
        # Herfindahl-Hirschman Index (HHI) — lower = more diversified
        hhi = sum((v / 100) ** 2 for v in sector_values)  # 0=fully diversified, 1=monopoly
        sector_score = max(0, 100 - hhi * 100)
    else:
        sector_score = 50

    fund_count_score = min(100, len(holdings) * 15)  # more funds = more diversified (up to ~7)
    category_count_score = min(100, len(category_dist) * 20)

    diversification_score = (sector_score * 0.5 + fund_count_score * 0.3 + category_count_score * 0.2)
    diversification_score = round(float(np.clip(diversification_score, 0, 100)), 1)

    # ── Summary ──
    top_sector = max(aggregated_sectors, key=aggregated_sectors.get) if aggregated_sectors else "N/A"
    summary = (
        f"Portfolio of {len(holdings)} funds worth ₹{total_value:,.0f}. "
        f"Largest sector exposure: {top_sector} ({aggregated_sectors.get(top_sector, 0):.1f}%). "
        f"Diversification Score: {diversification_score}/100. "
        f"{len(alerts)} alert(s) flagged."
    )

    return XRayResult(
        total_portfolio_value=total_value,
        sector_exposure=dict(sorted(aggregated_sectors.items(), key=lambda x: -x[1])),
        market_cap_exposure=dict(sorted(aggregated_mktcap.items(), key=lambda x: -x[1])),
        category_distribution=category_dist,
        overlap_matrix=overlap_matrix,
        concentration_alerts=alerts,
        thematic_clusters=thematic_clusters,
        diversification_score=diversification_score,
        summary=summary,
    )


def format_xray_report(result: XRayResult) -> str:
    """Format the X-Ray result as a readable report."""
    lines = [
        "# 🔬 Portfolio X-Ray Report",
        f"\n**Total Portfolio Value**: ₹{result.total_portfolio_value:,.0f}",
        f"**Diversification Score**: {result.diversification_score}/100\n",
        "## 📊 Sector Exposure (Top 10)",
    ]
    for sector, pct in list(result.sector_exposure.items())[:10]:
        bar = "█" * int(pct / 3)
        lines.append(f"  {sector:<25} {pct:5.1f}%  {bar}")

    lines.append("\n## 🏦 Market Cap Distribution")
    for cap, pct in result.market_cap_exposure.items():
        lines.append(f"  {cap:<15} {pct:.1f}%")

    lines.append("\n## 📂 Category Distribution")
    for cat, pct in result.category_distribution.items():
        lines.append(f"  {cat:<25} {pct:.1f}%")

    if result.thematic_clusters:
        lines.append("\n## 🎯 Thematic Clusters")
        for cluster in result.thematic_clusters:
            lines.append(f"  {cluster}")

    if result.concentration_alerts:
        lines.append("\n## ⚠️ Concentration Alerts")
        for alert in result.concentration_alerts:
            lines.append(f"  {alert}")

    if result.overlap_matrix:
        lines.append("\n## 🔁 Fund Overlap Matrix")
        for pair, score in result.overlap_matrix.items():
            flag = "⚠️ HIGH" if score > OVERLAP_HIGH_THRESHOLD else "✅ OK "
            lines.append(f"  {flag}  {pair:<45} {score:.0f}%")

    return "\n".join(lines)

