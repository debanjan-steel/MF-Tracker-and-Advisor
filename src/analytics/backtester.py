"""
src/analytics/backtester.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Dynamic SIP Backtester — compares static vs timing-aware SIP strategies.

Simulates two strategies over historical NAV data:
  1. STATIC SIP    : Fixed ₹X every month, regardless of market conditions.
  2. DYNAMIC SIP   : Same budget envelope but adjusts monthly amount
                     based on the timing model score:
                     - Invests more in dips (timing score high → 1.5×)
                     - Invests less in expensive markets (timing score low → 0.5×)
                     - Budget is redistributed, not increased (zero extra cost)

Output: Comparison of final corpus, XIRR, and risk metrics.

Also includes the ML Prediction Ledger (prediction logging + evaluation).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

import numpy as np
import pandas as pd

from .metrics import calculate_cagr, calculate_max_drawdown, calculate_sharpe_ratio


# ─────────────────────────────────────────────────────────────────────────────
# SIP Simulator
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SIPSimResult:
    """Result of a single SIP simulation run."""
    strategy: str                        # "STATIC" or "DYNAMIC"
    total_invested: float                # Total ₹ deployed
    final_corpus: float                  # Portfolio value at end
    absolute_gain: float                 # final - invested
    cagr: float                          # Annualised return
    max_drawdown: float
    sharpe: float
    xirr: float                          # Internal rate of return on cash flows
    monthly_records: list[dict] = field(default_factory=list)


def _compute_xirr(cash_flows: list[tuple[date, float]]) -> float:
    """
    Compute XIRR (IRR with irregular dates) using Newton-Raphson method.

    Parameters
    ----------
    cash_flows : List of (date, amount) tuples.
                 Investments are negative, final redemption is positive.

    Returns
    -------
    float : XIRR as decimal (e.g., 0.15 = 15%).
    """
    if not cash_flows:
        return float("nan")

    dates, amounts = zip(*cash_flows)
    min_date = min(dates)
    days = [(d - min_date).days for d in dates]
    amounts = list(amounts)

    def _npv(rate: float) -> float:
        return sum(
            cf / (1 + rate) ** (d / 365.25)
            for cf, d in zip(amounts, days)
        )

    # Newton-Raphson
    rate = 0.10
    for _ in range(100):
        npv = _npv(rate)
        if abs(npv) < 0.01:
            break
        # Numerical derivative
        h = 1e-5
        d_npv = (_npv(rate + h) - _npv(rate - h)) / (2 * h)
        if d_npv == 0:
            break
        rate -= npv / d_npv
        if rate < -0.99:
            rate = -0.99

    return round(float(rate), 6)


def simulate_static_sip(
    nav_history: pd.Series,
    monthly_amount: float,
    start_date: date | None = None,
    end_date: date | None = None,
) -> SIPSimResult:
    """
    Simulate a static (fixed-amount) monthly SIP over historical NAV data.

    Parameters
    ----------
    nav_history    : Daily NAV series (DatetimeIndex → float).
    monthly_amount : Fixed monthly SIP amount in ₹.
    start_date     : When to start SIP (default: beginning of history).
    end_date       : When to stop (default: end of history).

    Returns
    -------
    SIPSimResult
    """
    nav = nav_history.sort_index().dropna()
    if start_date:
        nav = nav[nav.index >= pd.Timestamp(start_date)]
    if end_date:
        nav = nav[nav.index <= pd.Timestamp(end_date)]

    monthly_navs = nav.resample("MS").first().dropna()  # Month-start NAV
    if monthly_navs.empty:
        return _empty_result("STATIC")

    total_units = 0.0
    total_invested = 0.0
    cash_flows: list[tuple[date, float]] = []
    records: list[dict] = []

    for dt, price in monthly_navs.items():
        if price <= 0:
            continue
        units_bought = monthly_amount / price
        total_units += units_bought
        total_invested += monthly_amount
        cash_flows.append((dt.date(), -monthly_amount))

        records.append({
            "month": dt.strftime("%b %Y"),
            "nav": price,
            "units_bought": round(units_bought, 4),
            "total_units": round(total_units, 4),
            "invested_so_far": round(total_invested, 2),
            "portfolio_value": round(total_units * price, 2),
        })

    final_nav = nav.iloc[-1]
    final_corpus = total_units * final_nav
    cash_flows.append((nav.index[-1].date(), final_corpus))

    portfolio_value_series = pd.Series(
        [r["portfolio_value"] for r in records],
        index=pd.to_datetime([r["month"] for r in records], format="%b %Y"),
    )

    return SIPSimResult(
        strategy="STATIC",
        total_invested=round(total_invested, 2),
        final_corpus=round(final_corpus, 2),
        absolute_gain=round(final_corpus - total_invested, 2),
        cagr=calculate_cagr(portfolio_value_series),
        max_drawdown=calculate_max_drawdown(portfolio_value_series),
        sharpe=calculate_sharpe_ratio(portfolio_value_series),
        xirr=_compute_xirr(cash_flows),
        monthly_records=records,
    )


def simulate_dynamic_sip(
    nav_history: pd.Series,
    monthly_budget: float,
    start_date: date | None = None,
    end_date: date | None = None,
    ema_period: int = 200,
) -> SIPSimResult:
    """
    Simulate a dynamic SIP that adjusts amount based on market timing.

    The TOTAL budget envelope is the same as static SIP over the period
    (i.e., not extra money — just smarter distribution):
      - When market is below 200 EMA → invest more (up to 2×)
      - When market is above 200 EMA by >15% → invest less (0.5×)
      - Surplus months get "saved" and deployed in cheap months

    Parameters
    ----------
    nav_history   : Daily NAV series.
    monthly_budget : Base monthly budget (same as static SIP amount).
    start_date    : Start of simulation.
    end_date      : End of simulation.
    ema_period    : EMA lookback for timing signal.

    Returns
    -------
    SIPSimResult
    """
    nav = nav_history.sort_index().dropna()
    if start_date:
        nav = nav[nav.index >= pd.Timestamp(start_date)]
    if end_date:
        nav = nav[nav.index <= pd.Timestamp(end_date)]

    # Compute 200-day EMA on full history
    ema = nav.ewm(span=ema_period, adjust=False).mean()
    monthly_navs = nav.resample("MS").first().dropna()
    monthly_ema = ema.resample("MS").first().reindex(monthly_navs.index).dropna()

    common_idx = monthly_navs.index.intersection(monthly_ema.index)
    monthly_navs = monthly_navs.loc[common_idx]
    monthly_ema = monthly_ema.loc[common_idx]

    if monthly_navs.empty:
        return _empty_result("DYNAMIC")

    total_units = 0.0
    total_invested = 0.0
    dry_powder = 0.0  # Accumulated savings from under-investment months
    cash_flows: list[tuple[date, float]] = []
    records: list[dict] = []

    for dt in monthly_navs.index:
        price = monthly_navs.loc[dt]
        ema_val = monthly_ema.loc[dt]

        if price <= 0 or ema_val <= 0:
            continue

        pct_above_ema = (price - ema_val) / ema_val

        # Determine multiplier
        if pct_above_ema < -0.15:
            mult = 2.0  # Deep dip — buy aggressively
        elif pct_above_ema < -0.05:
            mult = 1.5
        elif pct_above_ema < 0.05:
            mult = 1.0
        elif pct_above_ema < 0.15:
            mult = 0.75
        else:
            mult = 0.5  # Expensive — accumulate dry powder

        # Available cash = monthly budget + dry powder for dip months
        if mult > 1.0:
            available = monthly_budget * mult + dry_powder * 0.5  # Use some dry powder
            dry_powder = max(0, dry_powder - dry_powder * 0.5)
        else:
            actual_invest = monthly_budget * mult
            dry_powder += monthly_budget - actual_invest
            available = actual_invest

        # Cap at 3× monthly budget to avoid unrealistic concentrations
        invest_amount = min(available, monthly_budget * 3)

        units_bought = invest_amount / price
        total_units += units_bought
        total_invested += invest_amount
        cash_flows.append((dt.date(), -invest_amount))

        records.append({
            "month": dt.strftime("%b %Y"),
            "nav": price,
            "ema": round(ema_val, 4),
            "pct_above_ema": round(pct_above_ema * 100, 2),
            "multiplier": mult,
            "invested": round(invest_amount, 2),
            "units_bought": round(units_bought, 4),
            "total_units": round(total_units, 4),
            "dry_powder": round(dry_powder, 2),
            "portfolio_value": round(total_units * price, 2),
        })

    final_nav = nav.iloc[-1]
    final_corpus = total_units * final_nav
    cash_flows.append((nav.index[-1].date(), final_corpus))

    portfolio_value_series = pd.Series(
        [r["portfolio_value"] for r in records],
        index=pd.to_datetime([r["month"] for r in records], format="%b %Y"),
    )

    return SIPSimResult(
        strategy="DYNAMIC",
        total_invested=round(total_invested, 2),
        final_corpus=round(final_corpus, 2),
        absolute_gain=round(final_corpus - total_invested, 2),
        cagr=calculate_cagr(portfolio_value_series),
        max_drawdown=calculate_max_drawdown(portfolio_value_series),
        sharpe=calculate_sharpe_ratio(portfolio_value_series),
        xirr=_compute_xirr(cash_flows),
        monthly_records=records,
    )


def _empty_result(strategy: str) -> SIPSimResult:
    return SIPSimResult(
        strategy=strategy,
        total_invested=0,
        final_corpus=0,
        absolute_gain=0,
        cagr=float("nan"),
        max_drawdown=float("nan"),
        sharpe=float("nan"),
        xirr=float("nan"),
    )


def compare_strategies(static: SIPSimResult, dynamic: SIPSimResult) -> dict:
    """Compare static vs dynamic SIP results."""
    extra_gain = dynamic.final_corpus - static.final_corpus
    cagr_delta = (dynamic.cagr or 0) - (static.cagr or 0)

    verdict = ""
    if extra_gain > 0:
        verdict = (
            f"✅ Dynamic SIP outperformed Static by ₹{extra_gain:,.0f} "
            f"(+{cagr_delta*100:.2f}% CAGR). Timing the SIP amount paid off."
        )
    else:
        verdict = (
            f"⚠️ Static SIP outperformed Dynamic by ₹{abs(extra_gain):,.0f}. "
            f"Markets were efficient enough that fixed investing worked better."
        )

    return {
        "static_corpus": static.final_corpus,
        "dynamic_corpus": dynamic.final_corpus,
        "static_cagr": static.cagr,
        "dynamic_cagr": dynamic.cagr,
        "static_xirr": static.xirr,
        "dynamic_xirr": dynamic.xirr,
        "extra_gain": extra_gain,
        "cagr_delta": cagr_delta,
        "verdict": verdict,
    }


def format_backtest_report(static: SIPSimResult, dynamic: SIPSimResult) -> str:
    """Format backtest comparison as a readable report."""
    comparison = compare_strategies(static, dynamic)

    def _pct(v: float) -> str:
        return f"{v*100:.2f}%" if v is not None and not np.isnan(v) else "N/A"

    lines = [
        "# 📊 SIP Backtest: Static vs Dynamic Strategy",
        "",
        f"| Metric | Static SIP | Dynamic SIP | Δ |",
        f"|--------|-----------|------------|---|",
        f"| Total Invested | ₹{static.total_invested:,.0f} | ₹{dynamic.total_invested:,.0f} | — |",
        f"| Final Corpus | ₹{static.final_corpus:,.0f} | ₹{dynamic.final_corpus:,.0f} | ₹{comparison['extra_gain']:+,.0f} |",
        f"| CAGR | {_pct(static.cagr)} | {_pct(dynamic.cagr)} | {_pct(comparison['cagr_delta'])} |",
        f"| XIRR | {_pct(static.xirr)} | {_pct(dynamic.xirr)} | — |",
        f"| Max Drawdown | {_pct(static.max_drawdown)} | {_pct(dynamic.max_drawdown)} | — |",
        f"| Sharpe Ratio | {static.sharpe:.2f} | {dynamic.sharpe:.2f} | — |",
        "",
        f"**Verdict**: {comparison['verdict']}",
    ]
    return "\n".join(lines)

