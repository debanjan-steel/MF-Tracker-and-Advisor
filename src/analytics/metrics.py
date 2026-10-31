"""
src/analytics/metrics.py
━━━━━━━━━━━━━━━━━━━━━━━━
Core performance metrics for mutual fund NAV series.

All functions accept a pandas Series or DataFrame with:
  - Index: datetime (nav_date)
  - Values: float NAV

Annualisation basis: 252 trading days (Indian markets).
Risk-free rate default: 6.5% p.a. (approx RBI repo rate proxy).
"""

from __future__ import annotations

import warnings
from typing import Optional

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252
DEFAULT_RISK_FREE_RATE = 0.065  # 6.5% p.a.


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _to_series(nav_input: pd.Series | pd.DataFrame) -> pd.Series:
    """Coerce input to a sorted NAV Series indexed by date."""
    if isinstance(nav_input, pd.DataFrame):
        nav_input = nav_input["nav"]
    series = nav_input.sort_index().dropna()
    if series.empty:
        raise ValueError("NAV series is empty after cleaning.")
    return series


def _daily_returns(nav: pd.Series) -> pd.Series:
    """Compute daily log returns."""
    return np.log(nav / nav.shift(1)).dropna()


# ─────────────────────────────────────────────────────────────────────────────
# Task 3.1 — Core Metrics
# ─────────────────────────────────────────────────────────────────────────────

def calculate_cagr(nav_input: pd.Series | pd.DataFrame, years: Optional[float] = None) -> float:
    """
    Compound Annual Growth Rate (CAGR).

    Parameters
    ----------
    nav_input : NAV series or DataFrame with 'nav' column.
    years     : Number of years to compute over. Defaults to full history.

    Returns
    -------
    float : CAGR as a decimal (e.g., 0.18 = 18%).
    """
    nav = _to_series(nav_input)
    if years is not None:
        cutoff = nav.index[-1] - pd.DateOffset(years=years)
        nav = nav[nav.index >= cutoff]
        if len(nav) < 2:
            return float("nan")

    start_nav = nav.iloc[0]
    end_nav = nav.iloc[-1]
    actual_years = (nav.index[-1] - nav.index[0]).days / 365.25

    if actual_years <= 0 or start_nav <= 0:
        return float("nan")

    return (end_nav / start_nav) ** (1 / actual_years) - 1


def calculate_rolling_returns(
    nav_input: pd.Series | pd.DataFrame,
    window_years: float = 1.0,
) -> pd.Series:
    """
    Rolling CAGR over a sliding window.

    Parameters
    ----------
    nav_input    : NAV series or DataFrame.
    window_years : Size of rolling window in years (e.g., 1, 3, 5).

    Returns
    -------
    pd.Series : Rolling CAGR indexed by end-date of each window.
    """
    nav = _to_series(nav_input)
    window_days = int(window_years * 365.25)

    results = {}
    for i in range(len(nav)):
        end_date = nav.index[i]
        start_cutoff = end_date - pd.Timedelta(days=window_days)
        window_nav = nav[nav.index >= start_cutoff].iloc[: i + 1]
        if len(window_nav) < 10:
            continue
        s = window_nav.iloc[0]
        e = window_nav.iloc[-1]
        n_years = (window_nav.index[-1] - window_nav.index[0]).days / 365.25
        if n_years > 0 and s > 0:
            results[end_date] = (e / s) ** (1 / n_years) - 1

    return pd.Series(results, name=f"rolling_cagr_{window_years}y")


def calculate_max_drawdown(nav_input: pd.Series | pd.DataFrame) -> float:
    """
    Maximum Drawdown (MDD): worst peak-to-trough decline in percentage.

    Returns
    -------
    float : MDD as a negative decimal (e.g., -0.35 = -35%).
    """
    nav = _to_series(nav_input)
    rolling_peak = nav.cummax()
    drawdown = (nav - rolling_peak) / rolling_peak
    return float(drawdown.min())


def calculate_drawdown_series(nav_input: pd.Series | pd.DataFrame) -> pd.Series:
    """Return the full drawdown time-series (useful for charting)."""
    nav = _to_series(nav_input)
    rolling_peak = nav.cummax()
    return (nav - rolling_peak) / rolling_peak


def calculate_sharpe_ratio(
    nav_input: pd.Series | pd.DataFrame,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
) -> float:
    """
    Annualised Sharpe Ratio.

    Parameters
    ----------
    nav_input       : NAV series or DataFrame.
    risk_free_rate  : Annual risk-free rate as decimal (default 6.5%).

    Returns
    -------
    float : Sharpe ratio (higher = better risk-adjusted return).
    """
    nav = _to_series(nav_input)
    daily_returns = _daily_returns(nav)
    if len(daily_returns) < 20:
        return float("nan")

    daily_rf = risk_free_rate / TRADING_DAYS_PER_YEAR
    excess = daily_returns - daily_rf
    std = excess.std()
    if std == 0:
        return float("nan")

    return float((excess.mean() / std) * np.sqrt(TRADING_DAYS_PER_YEAR))


def calculate_sortino_ratio(
    nav_input: pd.Series | pd.DataFrame,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
) -> float:
    """
    Annualised Sortino Ratio (downside deviation only).

    Returns
    -------
    float : Sortino ratio (penalises only downside volatility).
    """
    nav = _to_series(nav_input)
    daily_returns = _daily_returns(nav)
    if len(daily_returns) < 20:
        return float("nan")

    daily_rf = risk_free_rate / TRADING_DAYS_PER_YEAR
    excess = daily_returns - daily_rf
    downside = excess[excess < 0]
    if len(downside) == 0:
        return float("inf")

    downside_std = np.sqrt((downside**2).mean())
    if downside_std == 0:
        return float("nan")

    return float((excess.mean() / downside_std) * np.sqrt(TRADING_DAYS_PER_YEAR))


def calculate_calmar_ratio(nav_input: pd.Series | pd.DataFrame) -> float:
    """
    Calmar Ratio = CAGR / |Max Drawdown|.
    Higher is better. Useful for comparing momentum vs. crash-prone funds.
    """
    cagr = calculate_cagr(nav_input)
    mdd = calculate_max_drawdown(nav_input)
    if mdd == 0 or np.isnan(mdd) or np.isnan(cagr):
        return float("nan")
    return float(cagr / abs(mdd))


def calculate_volatility(
    nav_input: pd.Series | pd.DataFrame,
    annualised: bool = True,
) -> float:
    """
    Standard deviation of returns.

    Returns
    -------
    float : Annualised volatility as decimal (e.g., 0.18 = 18%).
    """
    nav = _to_series(nav_input)
    daily_returns = _daily_returns(nav)
    vol = daily_returns.std()
    if annualised:
        vol *= np.sqrt(TRADING_DAYS_PER_YEAR)
    return float(vol)


def calculate_beta(
    fund_nav: pd.Series | pd.DataFrame,
    benchmark_nav: pd.Series | pd.DataFrame,
) -> float:
    """
    Beta of the fund relative to a benchmark (e.g., Nifty 50 index fund NAV).

    Returns
    -------
    float : Beta (1.0 = market-neutral, >1.0 = aggressive, <1.0 = defensive).
    """
    fund = _to_series(fund_nav)
    bench = _to_series(benchmark_nav)

    # Align on common dates
    common_idx = fund.index.intersection(bench.index)
    if len(common_idx) < 30:
        return float("nan")

    fund_r = _daily_returns(fund.loc[common_idx])
    bench_r = _daily_returns(bench.loc[common_idx])

    # Align again after diff
    common_idx2 = fund_r.index.intersection(bench_r.index)
    fund_r = fund_r.loc[common_idx2]
    bench_r = bench_r.loc[common_idx2]

    cov = np.cov(fund_r, bench_r)
    bench_var = cov[1, 1]
    if bench_var == 0:
        return float("nan")

    return float(cov[0, 1] / bench_var)


def calculate_alpha(
    fund_nav: pd.Series | pd.DataFrame,
    benchmark_nav: pd.Series | pd.DataFrame,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
) -> float:
    """
    Jensen's Alpha = Fund Return − [Rf + Beta × (Benchmark Return − Rf)].
    Annualised.

    Returns
    -------
    float : Alpha as decimal (positive alpha = fund outperforms benchmark after risk-adj).
    """
    fund_cagr = calculate_cagr(fund_nav)
    bench_cagr = calculate_cagr(benchmark_nav)
    beta = calculate_beta(fund_nav, benchmark_nav)

    if any(np.isnan(v) for v in [fund_cagr, bench_cagr, beta]):
        return float("nan")

    return float(fund_cagr - (risk_free_rate + beta * (bench_cagr - risk_free_rate)))


def calculate_updown_capture(
    fund_nav: pd.Series | pd.DataFrame,
    benchmark_nav: pd.Series | pd.DataFrame,
) -> dict[str, float]:
    """
    Up-Capture and Down-Capture ratios vs benchmark.
    - Up-Capture > 100%: fund gains more than benchmark in up markets ✅
    - Down-Capture < 100%: fund loses less than benchmark in down markets ✅

    Returns
    -------
    dict : {'up_capture': float, 'down_capture': float}
    """
    fund = _to_series(fund_nav)
    bench = _to_series(benchmark_nav)

    common_idx = fund.index.intersection(bench.index)
    if len(common_idx) < 30:
        return {"up_capture": float("nan"), "down_capture": float("nan")}

    fund_r = _daily_returns(fund.loc[common_idx])
    bench_r = _daily_returns(bench.loc[common_idx])

    common_idx2 = fund_r.index.intersection(bench_r.index)
    fund_r = fund_r.loc[common_idx2]
    bench_r = bench_r.loc[common_idx2]

    up_days = bench_r[bench_r >= 0]
    down_days = bench_r[bench_r < 0]

    fund_up = fund_r.loc[up_days.index]
    fund_down = fund_r.loc[down_days.index]

    def _ratio(fund_ret: pd.Series, bench_ret: pd.Series) -> float:
        if bench_ret.empty or bench_ret.mean() == 0:
            return float("nan")
        return float(fund_ret.mean() / bench_ret.mean() * 100)

    return {
        "up_capture": _ratio(fund_up, up_days),
        "down_capture": _ratio(fund_down, down_days),
    }


def full_scorecard(
    fund_nav: pd.Series | pd.DataFrame,
    benchmark_nav: Optional[pd.Series | pd.DataFrame] = None,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
) -> dict:
    """
    One-stop scorecard: all key metrics in a single dict.

    Returns
    -------
    dict with keys: cagr_1y, cagr_3y, cagr_5y, cagr_all,
                    max_drawdown, sharpe, sortino, calmar,
                    volatility, beta, alpha, up_capture, down_capture
    """
    result: dict = {}

    for years, label in [(1, "1y"), (3, "3y"), (5, "5y")]:
        result[f"cagr_{label}"] = calculate_cagr(fund_nav, years=years)

    result["cagr_all"] = calculate_cagr(fund_nav)
    result["max_drawdown"] = calculate_max_drawdown(fund_nav)
    result["sharpe"] = calculate_sharpe_ratio(fund_nav, risk_free_rate)
    result["sortino"] = calculate_sortino_ratio(fund_nav, risk_free_rate)
    result["calmar"] = calculate_calmar_ratio(fund_nav)
    result["volatility"] = calculate_volatility(fund_nav)

    if benchmark_nav is not None:
        result["beta"] = calculate_beta(fund_nav, benchmark_nav)
        result["alpha"] = calculate_alpha(fund_nav, benchmark_nav, risk_free_rate)
        cap = calculate_updown_capture(fund_nav, benchmark_nav)
        result.update(cap)
    else:
        result["beta"] = None
        result["alpha"] = None
        result["up_capture"] = None
        result["down_capture"] = None

    # Human-friendly labels
    result["_pct"] = {k: f"{v*100:.2f}%" for k, v in result.items() if isinstance(v, float)}

    return result

