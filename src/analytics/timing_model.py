"""
src/analytics/timing_model.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Market Timing Score Engine (0–100).

Combines multiple valuation and momentum signals to produce a single
"Entry Attractiveness Score":
  - 100 = Screaming buy (deep value + strong momentum)
  - 50  = Neutral
  - 0   = Extremely overvalued / dangerous to invest

Signals used:
  1. 200-day EMA distance (price vs long-term trend)
  2. Nifty P/E vs 10-Year Rolling Median (valuation percentile)
  3. Bond-Equity Earnings Yield Ratio (BEER) — equity vs bonds
  4. RSI (momentum / overbought/oversold)
  5. 52-week high-low position (sentiment indicator)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# EMA / Moving Average Signals
# ─────────────────────────────────────────────────────────────────────────────

def ema_distance_score(nav: pd.Series, ema_period: int = 200) -> float:
    """
    Score based on how far NAV is above/below its 200-day EMA.

    Logic:
      - NAV < 200 EMA by >10%  →  100 (deep discount, excellent entry)
      - NAV ≈ 200 EMA (±2%)    →  60  (fair)
      - NAV > 200 EMA by >20%  →  10  (stretched, expensive)

    Returns
    -------
    float : 0–100 score.
    """
    nav = nav.sort_index().dropna()
    if len(nav) < ema_period:
        return 50.0  # Not enough data — neutral

    ema = nav.ewm(span=ema_period, adjust=False).mean()
    current_nav = nav.iloc[-1]
    current_ema = ema.iloc[-1]

    pct_above = (current_nav - current_ema) / current_ema  # can be negative

    # Map pct_above → score linearly:
    # -0.15 → 100, 0 → 65, +0.15 → 30, +0.25 → 10
    score = 65 - (pct_above * 233)  # slope calibrated
    return float(np.clip(score, 0, 100))


def rsi_score(nav: pd.Series, period: int = 14) -> float:
    """
    Score derived from RSI (Relative Strength Index).

    RSI < 30 (oversold) → score near 90 (good entry)
    RSI = 50            → score = 50 (neutral)
    RSI > 70 (overbought) → score near 10 (poor entry)

    Returns
    -------
    float : 0–100 score.
    """
    nav = nav.sort_index().dropna()
    if len(nav) < period + 5:
        return 50.0

    delta = nav.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    current_rsi = rsi.iloc[-1]

    # Invert: low RSI = high score
    score = 100 - current_rsi
    return float(np.clip(score, 0, 100))


def high_low_position_score(nav: pd.Series, window_days: int = 252) -> float:
    """
    Position of current NAV within 52-week (1Y) high-low range.

    At 52W low  → score 95 (buy the dip)
    At midpoint → score 50
    At 52W high → score 10 (buy near peak = risky)

    Returns
    -------
    float : 0–100 score.
    """
    nav = nav.sort_index().dropna()
    recent = nav.iloc[-window_days:] if len(nav) >= window_days else nav

    lo = recent.min()
    hi = recent.max()
    current = nav.iloc[-1]

    if hi == lo:
        return 50.0

    position = (current - lo) / (hi - lo)  # 0 = at low, 1 = at high
    score = 95 - position * 85  # 0→95, 1→10
    return float(np.clip(score, 0, 100))


# ─────────────────────────────────────────────────────────────────────────────
# Valuation Signals
# ─────────────────────────────────────────────────────────────────────────────

def pe_percentile_score(pe_series: pd.Series, lookback_years: int = 10) -> float:
    """
    Score based on where current Nifty P/E sits vs its historical distribution.

    Low percentile (P/E at historical bottom) → score near 100
    High percentile (P/E at historical peak)  → score near 0

    Parameters
    ----------
    pe_series     : pd.Series of Nifty P/E indexed by date.
    lookback_years: Years of history to use for percentile calculation.

    Returns
    -------
    float : 0–100 score.
    """
    pe = pe_series.sort_index().dropna()
    if len(pe) < 30:
        return 50.0

    cutoff = pe.index[-1] - pd.DateOffset(years=lookback_years)
    historical = pe[pe.index >= cutoff]

    current_pe = pe.iloc[-1]
    percentile = (historical < current_pe).mean() * 100  # 0-100

    # Invert: cheap (low percentile) = high score
    score = 100 - percentile
    return float(np.clip(score, 0, 100))


def beer_score(nifty_earnings_yield: float, ten_year_yield: float) -> float:
    """
    Bond-Equity Earnings Yield Ratio (BEER).

    earnings_yield = 1 / P/E (e.g., P/E=20 → EY=5%)
    BEER = earnings_yield / 10Y bond yield

    BEER > 1.5 → Equities cheap vs bonds → score near 85
    BEER ≈ 1.0 → Fair value                → score near 50
    BEER < 0.7 → Equities expensive vs bonds → score near 15

    Parameters
    ----------
    nifty_earnings_yield : float (e.g., 0.05 for 5%)
    ten_year_yield       : float (e.g., 0.072 for 7.2%)

    Returns
    -------
    float : 0–100 score.
    """
    if ten_year_yield <= 0:
        return 50.0

    beer = nifty_earnings_yield / ten_year_yield
    # Sigmoid-like mapping: beer=1→50, beer=2→85, beer=0.5→15
    score = 50 + 35 * np.tanh((beer - 1.0) * 2.0)
    return float(np.clip(score, 0, 100))


# ─────────────────────────────────────────────────────────────────────────────
# Macro Overlay
# ─────────────────────────────────────────────────────────────────────────────

def macro_overlay_score(macro_snapshot: dict) -> float:
    """
    Penalise timing score when macro environment is dangerous.

    Uses latest macro snapshot dict (from macro_client):
      - VIX, crude_change_pct, usd_inr_change_pct, us10y

    Returns
    -------
    float : 0–100 penalty-adjusted macro score.
              100 = Calm macro environment (full score)
              0   = Crisis mode (all indicators flashing red)
    """
    score = 100.0

    vix = macro_snapshot.get("vix")
    if vix is not None:
        if vix > 35:
            score -= 25
        elif vix > 25:
            score -= 12
        elif vix > 20:
            score -= 5

    crude_chg = macro_snapshot.get("crude_change_pct", 0.0) or 0.0
    if crude_chg > 6:
        score -= 20
    elif crude_chg > 4:
        score -= 10

    usdinr_chg = macro_snapshot.get("usdinr_change_pct", 0.0) or 0.0
    if usdinr_chg > 1.5:
        score -= 15
    elif usdinr_chg > 0.8:
        score -= 7

    us10y = macro_snapshot.get("us10y")
    if us10y is not None:
        if us10y > 5.0:
            score -= 15
        elif us10y > 4.5:
            score -= 7

    return float(np.clip(score, 0, 100))


# ─────────────────────────────────────────────────────────────────────────────
# Unified Market Timing Score
# ─────────────────────────────────────────────────────────────────────────────

# Signal weights (must sum to 1.0)
_WEIGHTS = {
    "ema_distance": 0.25,
    "pe_percentile": 0.25,
    "beer": 0.15,
    "rsi": 0.15,
    "high_low": 0.10,
    "macro": 0.10,
}


def compute_timing_score(
    nav: pd.Series,
    pe_series: pd.Series | None = None,
    macro_snapshot: dict | None = None,
    ten_year_yield: float | None = None,
    current_pe: float | None = None,
) -> dict:
    """
    Unified Market Entry Timing Score (0–100).

    Parameters
    ----------
    nav             : Fund / index NAV series.
    pe_series       : Nifty P/E time-series (optional — falls back to neutral).
    macro_snapshot  : Dict from macro_client.fetch_latest_macro_snapshot().
    ten_year_yield  : Current 10Y G-sec yield as decimal (optional).
    current_pe      : Latest Nifty P/E ratio (optional).

    Returns
    -------
    dict with keys:
      - total_score        : 0–100 overall timing score
      - interpretation     : str label
      - component_scores   : individual signal scores
      - recommendation     : actionable text
    """
    scores: dict[str, float] = {}

    # 1. EMA Distance
    scores["ema_distance"] = ema_distance_score(nav)

    # 2. P/E Percentile
    if pe_series is not None and len(pe_series) > 30:
        scores["pe_percentile"] = pe_percentile_score(pe_series)
    else:
        scores["pe_percentile"] = 50.0  # neutral

    # 3. BEER
    if current_pe and ten_year_yield and current_pe > 0:
        ey = 1.0 / current_pe
        scores["beer"] = beer_score(ey, ten_year_yield)
    else:
        scores["beer"] = 50.0

    # 4. RSI
    scores["rsi"] = rsi_score(nav)

    # 5. 52W High-Low Position
    scores["high_low"] = high_low_position_score(nav)

    # 6. Macro Overlay
    if macro_snapshot:
        scores["macro"] = macro_overlay_score(macro_snapshot)
    else:
        scores["macro"] = 75.0  # slightly positive default (assume calm)

    # Weighted average
    total = sum(_WEIGHTS[k] * scores[k] for k in _WEIGHTS)

    # Interpretation
    if total >= 75:
        interpretation = "🟢 STRONG BUY — Market timing is favourable"
        recommendation = "Excellent time to deploy capital or increase SIP amount. Consider lump sum."
    elif total >= 60:
        interpretation = "🟡 BUY — Conditions are supportive"
        recommendation = "Good time to invest. Stick to your SIP plan. Minor lump sum acceptable."
    elif total >= 45:
        interpretation = "⚪ NEUTRAL — Wait for better opportunity"
        recommendation = "Markets are fairly valued. Continue SIPs, avoid fresh lump sum deployment."
    elif total >= 30:
        interpretation = "🟠 CAUTION — Elevated risk"
        recommendation = "Markets may be overvalued or macro is stressed. Reduce lump sum, hold dry powder."
    else:
        interpretation = "🔴 AVOID LUMP SUM — Market conditions are unfavourable"
        recommendation = "High risk. Continue minimal SIPs only. Keep fresh capital as dry powder in liquid fund."

    return {
        "total_score": round(total, 1),
        "interpretation": interpretation,
        "recommendation": recommendation,
        "component_scores": {k: round(v, 1) for k, v in scores.items()},
        "weights": _WEIGHTS,
    }

