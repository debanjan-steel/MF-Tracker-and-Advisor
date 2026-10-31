"""
src/analytics/manager_tracker.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fund Manager Track Record Analyser.

Evaluates fund manager performance across all funds they manage/have managed:
  - Alpha generated per manager over rolling windows
  - Consistency: % of years they outperformed benchmark
  - Tenure analysis and performance cliff (did alpha drop after they joined?)
  - Multi-fund track: do they run one good fund or are all their funds good?
  - "Star manager risk": alert if fund is over-reliant on one person

Usage context:
  - Shown in the Portfolio tab under each holding's fund card
  - Triggered during dud-fund scan to distinguish fund-level vs manager-level issues
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from .metrics import calculate_cagr, calculate_alpha, calculate_sharpe_ratio, _daily_returns


# ─────────────────────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ManagerFundRecord:
    """A fund managed (or previously managed) by a manager."""
    scheme_code: int
    scheme_name: str
    category: str
    nav_history: pd.Series              # DatetimeIndex → NAV float
    benchmark_nav: Optional[pd.Series]  # Benchmark NAV for alpha calc (None = skip)
    start_date: Optional[str] = None   # When manager started (YYYY-MM-DD)
    end_date: Optional[str] = None     # None = still managing


@dataclass
class ManagerTrackRecord:
    """Aggregated track record for a single fund manager."""
    manager_name: str
    total_funds_managed: int
    active_funds: int
    funds_analysed: list[str] = field(default_factory=list)

    # Performance summary
    avg_cagr_1y: float = float("nan")
    avg_cagr_3y: float = float("nan")
    avg_cagr_5y: float = float("nan")
    avg_alpha: float = float("nan")
    avg_sharpe: float = float("nan")

    # Consistency
    outperformance_pct: float = float("nan")   # % of calendar years beating category
    best_fund: str = ""
    worst_fund: str = ""

    # Risk flags
    star_manager_risk: bool = False
    manager_risk_note: str = ""

    # Rating
    rating: str = ""       # "⭐⭐⭐⭐⭐" to "⭐"
    verdict: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Per-Fund Analysis
# ─────────────────────────────────────────────────────────────────────────────

def _analyse_fund_under_manager(
    record: ManagerFundRecord,
    benchmark_nav: Optional[pd.Series] = None,
) -> dict:
    """
    Compute performance stats for a single fund under the manager's tenure.

    Returns
    -------
    dict with cagr_1y, cagr_3y, cagr_5y, alpha, sharpe, and consistency.
    """
    nav = record.nav_history.sort_index().dropna()

    # Clip to manager's tenure window
    if record.start_date:
        try:
            start_dt = pd.to_datetime(record.start_date)
            nav = nav[nav.index >= start_dt]
        except Exception:
            pass

    if record.end_date:
        try:
            end_dt = pd.to_datetime(record.end_date)
            nav = nav[nav.index <= end_dt]
        except Exception:
            pass

    result = {
        "scheme_name": record.scheme_name,
        "cagr_1y": calculate_cagr(nav, years=1) if len(nav) >= 50 else float("nan"),
        "cagr_3y": calculate_cagr(nav, years=3) if len(nav) >= 200 else float("nan"),
        "cagr_5y": calculate_cagr(nav, years=5) if len(nav) >= 500 else float("nan"),
        "sharpe": calculate_sharpe_ratio(nav) if len(nav) >= 50 else float("nan"),
        "alpha": float("nan"),
        "outperformance_years_pct": float("nan"),
    }

    bench = benchmark_nav or record.benchmark_nav
    if bench is not None and len(nav) >= 50:
        result["alpha"] = calculate_alpha(nav, bench)

    # Consistency: % of calendar years with positive return > benchmark
    if bench is not None and len(nav) >= 252:
        fund_annual = _annual_returns(nav)
        bench_annual = _annual_returns(bench)
        common_years = set(fund_annual.index) & set(bench_annual.index)
        if common_years:
            beats = sum(
                fund_annual.loc[yr] > bench_annual.loc[yr]
                for yr in common_years
                if not np.isnan(fund_annual.loc[yr]) and not np.isnan(bench_annual.loc[yr])
            )
            result["outperformance_years_pct"] = beats / len(common_years) * 100

    return result


def _annual_returns(nav: pd.Series) -> pd.Series:
    """Convert NAV series to annual returns indexed by year."""
    nav = nav.sort_index().dropna()
    annual = {}
    for year, group in nav.groupby(nav.index.year):
        if len(group) >= 10:
            annual[year] = group.iloc[-1] / group.iloc[0] - 1
    return pd.Series(annual)


# ─────────────────────────────────────────────────────────────────────────────
# Manager Aggregation
# ─────────────────────────────────────────────────────────────────────────────

def build_manager_track_record(
    manager_name: str,
    fund_records: list[ManagerFundRecord],
    benchmark_nav: Optional[pd.Series] = None,
) -> ManagerTrackRecord:
    """
    Build a full manager track record from their fund history.

    Parameters
    ----------
    manager_name   : Name of the fund manager.
    fund_records   : All funds this manager has managed (past + current).
    benchmark_nav  : Global benchmark NAV for alpha calc (used if fund has no benchmark).

    Returns
    -------
    ManagerTrackRecord
    """
    fund_stats = []
    for record in fund_records:
        stats = _analyse_fund_under_manager(record, benchmark_nav)
        fund_stats.append(stats)

    def _nanmean(key: str) -> float:
        vals = [s[key] for s in fund_stats if not np.isnan(s.get(key, float("nan")))]
        return float(np.mean(vals)) if vals else float("nan")

    avg_cagr_1y = _nanmean("cagr_1y")
    avg_cagr_3y = _nanmean("cagr_3y")
    avg_cagr_5y = _nanmean("cagr_5y")
    avg_alpha = _nanmean("alpha")
    avg_sharpe = _nanmean("sharpe")
    outperformance_pct = _nanmean("outperformance_years_pct")

    # Best / worst fund by 3Y CAGR
    valid_3y = [(s["scheme_name"], s["cagr_3y"]) for s in fund_stats if not np.isnan(s.get("cagr_3y", float("nan")))]
    best_fund = max(valid_3y, key=lambda x: x[1])[0] if valid_3y else "N/A"
    worst_fund = min(valid_3y, key=lambda x: x[1])[0] if valid_3y else "N/A"

    active_funds = sum(1 for r in fund_records if r.end_date is None)

    # Star manager risk: if manager runs only 1 fund
    star_risk = len(fund_records) == 1
    star_note = ""
    if star_risk:
        star_note = (
            f"⚠️ STAR MANAGER RISK: {manager_name} manages only one fund. "
            "If they leave, the fund's track record may not continue."
        )

    # Rating (based on 3Y alpha + outperformance consistency)
    rating, verdict = _rate_manager(avg_cagr_3y, avg_alpha, outperformance_pct)

    return ManagerTrackRecord(
        manager_name=manager_name,
        total_funds_managed=len(fund_records),
        active_funds=active_funds,
        funds_analysed=[s["scheme_name"] for s in fund_stats],
        avg_cagr_1y=avg_cagr_1y,
        avg_cagr_3y=avg_cagr_3y,
        avg_cagr_5y=avg_cagr_5y,
        avg_alpha=avg_alpha,
        avg_sharpe=avg_sharpe,
        outperformance_pct=outperformance_pct,
        best_fund=best_fund,
        worst_fund=worst_fund,
        star_manager_risk=star_risk,
        manager_risk_note=star_note,
        rating=rating,
        verdict=verdict,
    )


def _rate_manager(
    avg_cagr_3y: float,
    avg_alpha: float,
    outperformance_pct: float,
) -> tuple[str, str]:
    """Assign a 1–5 star rating to a manager."""
    score = 0

    if not np.isnan(avg_cagr_3y):
        if avg_cagr_3y > 0.18:
            score += 3
        elif avg_cagr_3y > 0.14:
            score += 2
        elif avg_cagr_3y > 0.10:
            score += 1

    if not np.isnan(avg_alpha):
        if avg_alpha > 0.03:
            score += 3
        elif avg_alpha > 0.01:
            score += 2
        elif avg_alpha > 0:
            score += 1

    if not np.isnan(outperformance_pct):
        if outperformance_pct >= 70:
            score += 4
        elif outperformance_pct >= 55:
            score += 3
        elif outperformance_pct >= 45:
            score += 2
        elif outperformance_pct >= 35:
            score += 1

    # Map 0–10 score to stars
    if score >= 8:
        return "⭐⭐⭐⭐⭐", "Elite manager — consistent alpha generator. High confidence in fund."
    elif score >= 6:
        return "⭐⭐⭐⭐", "Strong manager with above-average track record. Good conviction."
    elif score >= 4:
        return "⭐⭐⭐", "Decent manager with mixed results. Monitor for improvement."
    elif score >= 2:
        return "⭐⭐", "Below-average track record. Consider reviewing your investment."
    else:
        return "⭐", "Weak manager track record. High risk of continued underperformance."


def format_manager_report(record: ManagerTrackRecord) -> str:
    """Format manager track record as human-readable text."""
    def _pct(v: float) -> str:
        return f"{v*100:.2f}%" if not np.isnan(v) else "N/A"

    lines = [
        f"# 👔 Fund Manager: {record.manager_name}",
        f"**Rating**: {record.rating}",
        f"**Verdict**: {record.verdict}",
        "",
        f"**Funds Managed**: {record.total_funds_managed} total ({record.active_funds} active)",
        f"**Avg 1Y CAGR**: {_pct(record.avg_cagr_1y)}",
        f"**Avg 3Y CAGR**: {_pct(record.avg_cagr_3y)}",
        f"**Avg 5Y CAGR**: {_pct(record.avg_cagr_5y)}",
        f"**Avg Alpha**: {_pct(record.avg_alpha)}",
        f"**Avg Sharpe**: {record.avg_sharpe:.2f}" if not np.isnan(record.avg_sharpe) else "**Avg Sharpe**: N/A",
        f"**Beat Benchmark**: {record.outperformance_pct:.0f}% of calendar years" if not np.isnan(record.outperformance_pct) else "**Beat Benchmark**: N/A",
        f"**Best Fund**: {record.best_fund}",
        f"**Weakest Fund**: {record.worst_fund}",
    ]

    if record.star_manager_risk:
        lines.append(f"\n{record.manager_risk_note}")

    return "\n".join(lines)

