"""
src/analytics/underperformance_scanner.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Dud Fund Detector — identifies consistently underperforming funds
that should be switched out of.

A fund is flagged as a "dud" when:
  1. It trails its category average by >3% CAGR over 3 years, OR
  2. It trails its direct-plan twin by >1.5% CAGR (pure fee drag), OR
  3. Its 3Y rolling return percentile rank within category is bottom 25%, OR
  4. Manager tenure < 1 year + underperformance

Output includes:
  - Dud flag (True/False)
  - Severity (MILD / MODERATE / SEVERE)
  - Switch suggestion (if available)
  - Reinvestment recommendation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from .metrics import calculate_cagr, calculate_sharpe_ratio, calculate_max_drawdown


# ─────────────────────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FundProfile:
    """Input profile for a single fund."""
    scheme_code: int
    scheme_name: str
    nav_history: pd.Series          # DatetimeIndex → float NAV
    category: str                   # e.g. "Large Cap", "Flexi Cap"
    is_direct_plan: bool = False
    manager_name: str = ""
    manager_tenure_years: float = 0.0
    expense_ratio: float = 0.0      # as decimal (e.g., 0.012 = 1.2%)


@dataclass
class DudScanResult:
    """Result of the dud-fund scan for a single fund."""
    scheme_code: int
    scheme_name: str
    is_dud: bool
    severity: str                   # "CLEAN" | "MILD" | "MODERATE" | "SEVERE"
    reasons: list[str] = field(default_factory=list)
    cagr_3y: float = float("nan")
    category_avg_cagr_3y: float = float("nan")
    underperformance_vs_category: float = float("nan")
    sharpe_ratio: float = float("nan")
    max_drawdown: float = float("nan")
    switch_suggestion: str = ""
    reinvestment_note: str = ""
    score: float = 0.0              # 0 = clean, 100 = terrible


# ─────────────────────────────────────────────────────────────────────────────
# Core Scanner
# ─────────────────────────────────────────────────────────────────────────────

def scan_fund_for_dud(
    fund: FundProfile,
    category_avg_cagr_3y: Optional[float] = None,
    category_avg_sharpe: Optional[float] = None,
    direct_twin_cagr_3y: Optional[float] = None,
    benchmark_suggestions: Optional[list[str]] = None,
) -> DudScanResult:
    """
    Evaluate a single fund for underperformance (dud detection).

    Parameters
    ----------
    fund                  : FundProfile with NAV history and metadata.
    category_avg_cagr_3y  : Category average 3Y CAGR (optional).
    category_avg_sharpe   : Category average Sharpe ratio (optional).
    direct_twin_cagr_3y   : Direct plan equivalent 3Y CAGR (optional).
    benchmark_suggestions : Better funds to switch into.

    Returns
    -------
    DudScanResult
    """
    reasons: list[str] = []
    penalty_score = 0.0

    # Compute fund's own metrics
    cagr_3y = calculate_cagr(fund.nav_history, years=3)
    sharpe = calculate_sharpe_ratio(fund.nav_history)
    mdd = calculate_max_drawdown(fund.nav_history)

    # ── Check 1: Category underperformance ──
    underperf_vs_cat = float("nan")
    if category_avg_cagr_3y is not None and not np.isnan(cagr_3y):
        underperf_vs_cat = cagr_3y - category_avg_cagr_3y
        if underperf_vs_cat < -0.05:  # >5% lag
            reasons.append(
                f"Severely trails category by {abs(underperf_vs_cat)*100:.1f}% CAGR over 3Y."
            )
            penalty_score += 45
        elif underperf_vs_cat < -0.03:  # >3% lag
            reasons.append(
                f"Underperforms category by {abs(underperf_vs_cat)*100:.1f}% CAGR over 3Y."
            )
            penalty_score += 30
        elif underperf_vs_cat < -0.015:  # >1.5% lag
            reasons.append(
                f"Lags category by {abs(underperf_vs_cat)*100:.1f}% CAGR — marginal underperformance."
            )
            penalty_score += 10

    # ── Check 2: Regular vs Direct plan drag ──
    if direct_twin_cagr_3y is not None and not np.isnan(cagr_3y) and not fund.is_direct_plan:
        fee_drag = direct_twin_cagr_3y - cagr_3y
        if fee_drag > 0.015:  # >1.5% drag from fee alone
            reasons.append(
                f"⚠️ Expense ratio drag: regular plan lags direct by {fee_drag*100:.1f}%. "
                f"Switch to direct plan immediately."
            )
            penalty_score += 20

    # ── Check 3: Weak Sharpe ratio ──
    if not np.isnan(sharpe) and category_avg_sharpe is not None:
        if sharpe < category_avg_sharpe - 0.3:
            reasons.append(
                f"Poor risk-adjusted return: Sharpe {sharpe:.2f} vs category avg {category_avg_sharpe:.2f}."
            )
            penalty_score += 15

    # ── Check 4: Manager tenure risk ──
    if fund.manager_tenure_years < 1.0 and fund.manager_tenure_years > 0:
        reasons.append(
            f"⚠️ Fund manager changed recently (tenure: {fund.manager_tenure_years:.1f}Y). "
            f"Track record reset — monitor for 6–12 more months before new judgement."
        )
        penalty_score += 10

    # ── Check 5: High expense ratio for category ──
    if fund.expense_ratio > 0.02 and not fund.is_direct_plan:  # >2% for regular
        reasons.append(
            f"High expense ratio: {fund.expense_ratio*100:.2f}% p.a. Consider direct plan."
        )
        penalty_score += 10
    elif fund.expense_ratio > 0.01 and fund.is_direct_plan:  # >1% for direct (rare)
        reasons.append(
            f"Unusually high expense ratio for direct plan: {fund.expense_ratio*100:.2f}%."
        )
        penalty_score += 5

    # ── Check 6: Excessive drawdown ──
    if not np.isnan(mdd) and mdd < -0.45:  # >45% drawdown
        reasons.append(
            f"Extreme max drawdown of {mdd*100:.1f}% — higher volatility than peers."
        )
        penalty_score += 10

    # Determine severity
    is_dud = penalty_score >= 30
    if penalty_score >= 60:
        severity = "SEVERE"
        reinvestment_note = (
            "🚨 EXIT RECOMMENDED. Redeem and redeploy into a top-performing peer in the same category. "
            "Reinvest in a phased manner over 2–3 months to manage capital gains tax impact."
        )
    elif penalty_score >= 40:
        severity = "MODERATE"
        reinvestment_note = (
            "⚠️ SWITCH CANDIDATE. Stop fresh SIPs immediately. Evaluate switch after next quarter's NAV data."
        )
    elif penalty_score >= 20:
        severity = "MILD"
        reinvestment_note = (
            "🟡 WATCH LIST. Keep monitoring. Halt any lump-sum additions. Reassess in 6 months."
        )
    else:
        severity = "CLEAN"
        reinvestment_note = "✅ Fund is performing within acceptable range. Continue SIPs."

    switch_text = ""
    if is_dud and benchmark_suggestions:
        switch_text = (
            f"Consider switching to: {', '.join(benchmark_suggestions[:3])} — "
            f"top performers in the {fund.category} category."
        )

    return DudScanResult(
        scheme_code=fund.scheme_code,
        scheme_name=fund.scheme_name,
        is_dud=is_dud,
        severity=severity,
        reasons=reasons,
        cagr_3y=cagr_3y,
        category_avg_cagr_3y=category_avg_cagr_3y or float("nan"),
        underperformance_vs_category=underperf_vs_cat,
        sharpe_ratio=sharpe,
        max_drawdown=mdd,
        switch_suggestion=switch_text,
        reinvestment_note=reinvestment_note,
        score=round(penalty_score, 1),
    )


def scan_portfolio(
    funds: list[FundProfile],
    category_stats: dict[str, dict] | None = None,
) -> list[DudScanResult]:
    """
    Scan an entire portfolio of funds for duds.

    Parameters
    ----------
    funds          : List of FundProfile objects (user's holdings).
    category_stats : Dict mapping category name → {'avg_cagr_3y': float, 'avg_sharpe': float}.

    Returns
    -------
    list[DudScanResult] sorted by severity (worst first).
    """
    results = []
    for fund in funds:
        cat_avg_cagr = None
        cat_avg_sharpe = None
        if category_stats and fund.category in category_stats:
            cat_avg_cagr = category_stats[fund.category].get("avg_cagr_3y")
            cat_avg_sharpe = category_stats[fund.category].get("avg_sharpe")

        result = scan_fund_for_dud(
            fund=fund,
            category_avg_cagr_3y=cat_avg_cagr,
            category_avg_sharpe=cat_avg_sharpe,
        )
        results.append(result)

    # Sort: SEVERE first
    severity_order = {"SEVERE": 0, "MODERATE": 1, "MILD": 2, "CLEAN": 3}
    results.sort(key=lambda r: severity_order.get(r.severity, 99))
    return results


def format_dud_report(results: list[DudScanResult]) -> str:
    """Generate a human-readable dud scan report."""
    lines = ["# 🔍 Dud Fund Scanner Report\n"]
    for r in results:
        emoji = {"SEVERE": "🔴", "MODERATE": "🟠", "MILD": "🟡", "CLEAN": "✅"}.get(r.severity, "⚪")
        lines.append(f"## {emoji} {r.scheme_name} (Code: {r.scheme_code})")
        lines.append(f"**Severity**: {r.severity}  |  **Score**: {r.score:.0f}/100")
        if not np.isnan(r.cagr_3y):
            lines.append(f"**3Y CAGR**: {r.cagr_3y*100:.2f}%  |  **Sharpe**: {r.sharpe_ratio:.2f}  |  **Max DD**: {r.max_drawdown*100:.1f}%")
        for reason in r.reasons:
            lines.append(f"  - {reason}")
        lines.append(f"\n**Verdict**: {r.reinvestment_note}")
        if r.switch_suggestion:
            lines.append(f"**Switch To**: {r.switch_suggestion}")
        lines.append("")

    return "\n".join(lines)

