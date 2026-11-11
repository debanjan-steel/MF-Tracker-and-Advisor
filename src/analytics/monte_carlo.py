"""
src/analytics/monte_carlo.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Probabilistic Time Series Forecasting & Monte Carlo Simulation Engine.

Instead of single-point linear predictions, this quant engine simulates
1,000 forward paths using Merton Jump Diffusion with Student-t fat-tail
distributions, dynamically scaled by India VIX and macro danger levels.

Generates probabilistic uncertainty cones:
  - p90: Upper bull run / optimistic ceiling
  - p75: Favorable accumulation path
  - p50: Median expected trajectory
  - p25: Conservative path
  - p10: Tail-risk / worst-case drawdown boundary

Key Risk Metrics:
  - 1-Month Value-at-Risk (VaR 95%)
  - Conditional VaR / Expected Shortfall (CVaR 95%)
  - Probability of Drawdown
  - Uncertainty Band Width (p90 - p10 spread)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class MonteCarloPoint:
    date: str
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float


@dataclass
class MonteCarloResult:
    scheme_code: Optional[int]
    scheme_name: str
    current_nav: float
    horizon_days: int
    num_simulations: int
    annualized_drift: float
    annualized_volatility: float
    vix_scale_factor: float
    var_95_pct: float             # e.g. -7.4%
    cvar_95_pct: float            # e.g. -11.8%
    prob_loss_pct: float          # Probability of negative return
    cone_spread_pct: float        # (p90 - p10) / current_nav * 100
    volatility_regime: str        # Normal | Elevated Volatility | Extreme Shock
    summary_insight: str
    dates: list[str] = field(default_factory=list)
    fan_series: list[dict] = field(default_factory=list)


def run_monte_carlo_nav_forecast(
    nav_series: pd.Series,
    horizon_days: int = 30,
    num_simulations: int = 1000,
    vix_level: Optional[float] = None,
    scheme_code: Optional[int] = None,
    scheme_name: str = "Mutual Fund",
) -> MonteCarloResult:
    """
    Run Merton Jump Diffusion Monte Carlo simulation on historical NAV data.

    Parameters:
    -----------
    nav_series       : Pandas Series of historical NAV with DatetimeIndex or float values.
    horizon_days     : Forecast horizon in calendar days (typically 30 or 90).
    num_simulations  : Number of Monte Carlo trajectories (default: 1000).
    vix_level        : Current India VIX reading (if available) to scale volatility.
    scheme_code      : Optional scheme identifier.
    scheme_name      : Human-readable fund name.
    """
    cleaned_nav = nav_series.dropna().astype(float)
    if len(cleaned_nav) < 30:
        # Fallback synthetic series if history is too brief
        base = float(cleaned_nav.iloc[-1]) if len(cleaned_nav) > 0 else 100.0
        cleaned_nav = pd.Series([base * (1 + 0.0004 * i) for i in range(60)])

    current_nav = float(cleaned_nav.iloc[-1])

    # 1. Compute historical daily log returns
    returns = np.log(cleaned_nav / cleaned_nav.shift(1)).dropna()
    mean_daily = float(returns.mean()) if len(returns) > 0 else 0.0005
    std_daily = float(returns.std()) if len(returns) > 0 else 0.01

    # Annualize
    ann_drift = mean_daily * 252.0
    ann_vol = std_daily * np.sqrt(252.0)

    # 2. Macro Volatility Scaling via India VIX
    # Baseline normal India VIX is ~14.0 - 15.0
    vix_scale = 1.0
    if vix_level and vix_level > 0:
        vix_scale = max(0.85, min(2.5, np.sqrt(vix_level / 14.5)))

    effective_vol = ann_vol * vix_scale
    effective_daily_vol = effective_vol / np.sqrt(252.0)

    # Volatility Regime Assessment
    if effective_vol >= 0.28 or (vix_level and vix_level >= 24.0):
        regime = "Extreme Uncertainty (Shock Regime)"
    elif effective_vol >= 0.18 or (vix_level and vix_level >= 18.0):
        regime = "Elevated Volatility"
    else:
        regime = "Normal Stability"

    # 3. Simulate Forward Paths with Fat Tails (Student-t) & Downside Jumps
    np.random.seed(42)  # Deterministic seed for repeatable user view
    dt = 1.0 / 252.0
    trading_days = max(5, int(horizon_days * (252.0 / 365.0)))

    # Student-t distribution (df=5) produces realistic financial kurtosis (fat tails)
    df_t = 5
    t_draws = np.random.standard_t(df=df_t, size=(num_simulations, trading_days))
    # Rescale t-distribution to variance 1
    t_draws = t_draws * np.sqrt((df_t - 2) / df_t)

    # Merton Poisson Jump Diffusion (rare asymmetric macro shocks)
    jump_intensity = 0.04 * vix_scale       # ~4% annual probability of macro jump shock per day
    jump_mean = -0.015                       # Negative skew for market downturns
    jump_std = 0.025
    poisson_jumps = np.random.poisson(jump_intensity * dt, size=(num_simulations, trading_days))
    jump_sizes = np.random.normal(jump_mean, jump_std, size=(num_simulations, trading_days))
    jumps = poisson_jumps * jump_sizes

    # Drift term
    drift_term = (ann_drift - 0.5 * (effective_vol ** 2)) * dt

    # Path generation: log returns matrix
    daily_shocks = drift_term + (effective_daily_vol * t_draws) + jumps

    # Cumulative paths
    cum_returns = np.cumsum(daily_shocks, axis=1)
    paths = current_nav * np.exp(cum_returns)

    # 4. Extract Quantiles at each step
    p10_series = np.percentile(paths, 10, axis=0)
    p25_series = np.percentile(paths, 25, axis=0)
    p50_series = np.percentile(paths, 50, axis=0)
    p75_series = np.percentile(paths, 75, axis=0)
    p90_series = np.percentile(paths, 90, axis=0)

    # Build calendar dates
    start_dt = datetime.now()
    dates_list: list[str] = []
    fan_series: list[dict] = []

    # Insert Day 0 (Current Anchor)
    fan_series.append({
        "day": 0,
        "date": start_dt.strftime("%d %b"),
        "p10": round(current_nav, 2),
        "p25": round(current_nav, 2),
        "p50": round(current_nav, 2),
        "p75": round(current_nav, 2),
        "p90": round(current_nav, 2),
    })

    cur_dt = start_dt
    for step in range(trading_days):
        cur_dt += timedelta(days=1)
        # Skip weekends for trading days representation
        while cur_dt.weekday() >= 5:
            cur_dt += timedelta(days=1)

        d_str = cur_dt.strftime("%d %b")
        dates_list.append(d_str)

        fan_series.append({
            "day": step + 1,
            "date": d_str,
            "p10": round(float(p10_series[step]), 2),
            "p25": round(float(p25_series[step]), 2),
            "p50": round(float(p50_series[step]), 2),
            "p75": round(float(p75_series[step]), 2),
            "p90": round(float(p90_series[step]), 2),
        })

    # 5. Compute Risk Metrics at Horizon End
    terminal_values = paths[:, -1]
    terminal_returns = (terminal_values - current_nav) / current_nav

    # Value-at-Risk 95% (worst 5th percentile return)
    var_95 = float(np.percentile(terminal_returns, 5))
    var_95_pct = round(var_95 * 100.0, 2)

    # Conditional VaR (Expected Shortfall): Mean of returns below 5th percentile
    tail_returns = terminal_returns[terminal_returns <= var_95]
    cvar_95 = float(tail_returns.mean()) if len(tail_returns) > 0 else var_95 * 1.2
    cvar_95_pct = round(cvar_95 * 100.0, 2)

    # Probability of loss
    prob_loss = float(np.mean(terminal_returns < 0.0))
    prob_loss_pct = round(prob_loss * 100.0, 1)

    # Cone width / spread %
    final_p90 = float(p90_series[-1])
    final_p10 = float(p10_series[-1])
    spread_pct = round(((final_p90 - final_p10) / current_nav) * 100.0, 1)

    # Insight summary
    if prob_loss_pct > 40:
        insight = (
            f"⚠️ WIDE UNCERTAINTY CONE: High probability of interim drawdown ({prob_loss_pct}%). "
            f"95% 1-Month VaR is {var_95_pct}%. Recommended strategy: Stagger entries into 2–3 tranches "
            f"or utilize liquid parking to buy the lower bound (₹{final_p10:,.2f})."
        )
    elif prob_loss_pct < 20:
        insight = (
            f"✅ STRONG UPWARD CONVEXITY: Tight uncertainty band with {100 - prob_loss_pct:.1f}% probability "
            f"of positive NAV expansion. Median forecast targets ₹{float(p50_series[-1]):,.2f} (+{((float(p50_series[-1])/current_nav)-1)*100:.1f}%)."
        )
    else:
        insight = (
            f"📊 BALANCED MOMENTUM: Expected return is +{((float(p50_series[-1])/current_nav)-1)*100:.1f}% with "
            f"worst-case 95% tail risk bounded at {var_95_pct}%. Ideal regime for systematic monthly SIP accumulation."
        )

    return MonteCarloResult(
        scheme_code=scheme_code,
        scheme_name=scheme_name,
        current_nav=round(current_nav, 2),
        horizon_days=horizon_days,
        num_simulations=num_simulations,
        annualized_drift=round(ann_drift * 100.0, 2),
        annualized_volatility=round(effective_vol * 100.0, 2),
        vix_scale_factor=round(vix_scale, 2),
        var_95_pct=var_95_pct,
        cvar_95_pct=cvar_95_pct,
        prob_loss_pct=prob_loss_pct,
        cone_spread_pct=spread_pct,
        volatility_regime=regime,
        summary_insight=insight,
        dates=dates_list,
        fan_series=fan_series,
    )

