"""
macro_client.py — Stream 1: Live Macro Market Shock Proxies
Fetches real-time/daily macro indicators via yfinance (100% free).

Tracked indicators:
    BZ=F       — Brent Crude Oil Futures (India imports 85% crude)
    ^INDIAVIX  — India Volatility Index (market fear gauge)
    ^TNX       — US 10-Year Treasury Yield (FII flow driver)
    DX-Y.NYB   — US Dollar Index DXY (capital flight indicator)
    USDINR=X   — USD/INR Exchange Rate (currency risk)
    GC=F       — Gold Futures (safe-haven demand)
    ^NSEI      — Nifty 50 Index
    ^NSMIDCP   — Nifty Midcap 150 Index
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf

from src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

MACRO_TICKERS = settings.macro_tickers

# Labels for human-readable display
TICKER_LABELS: dict[str, str] = {
    "BZ=F":      "Brent Crude Oil (USD/barrel)",
    "^INDIAVIX": "India VIX (Fear Index)",
    "^TNX":      "US 10-Year Treasury Yield (%)",
    "DX-Y.NYB":  "US Dollar Index (DXY)",
    "USDINR=X":  "USD/INR Exchange Rate",
    "GC=F":      "Gold Futures (USD/oz)",
    "^NSEI":     "Nifty 50 Index",
    "^NSMIDCP":  "Nifty Midcap 150 Index",
}

# Shock alert thresholds (1-day % change that triggers an alert)
SHOCK_THRESHOLDS: dict[str, float] = {
    "BZ=F":      4.0,   # Crude oil > +4% in 24h → macro disruption
    "^INDIAVIX": 20.0,  # VIX level (absolute) > 20 → fear elevated
    "USDINR=X":  0.8,   # Rupee depreciates > 0.8% in 24h → currency stress
    "^TNX":      5.0,   # US 10Y yield level > 5% → capital flow risk
}


def fetch_macro_history(
    tickers: Optional[list[str]] = None,
    period: str = "5y",
    interval: str = "1d",
) -> dict[str, pd.DataFrame]:
    """
    Fetch historical daily data for all macro tickers via yfinance.

    Args:
        tickers: list of ticker symbols (defaults to all configured tickers)
        period:  yfinance period string — "1mo", "1y", "5y", "10y", "max"
        interval: "1d" (daily) recommended for macro analysis

    Returns:
        {ticker: DataFrame(columns=[open, high, low, close, volume], index=date)}
    """
    tickers = tickers or MACRO_TICKERS
    logger.info(f"[MacroClient] Fetching {len(tickers)} macro tickers | period={period}")

    try:
        raw = yf.download(
            tickers=tickers,
            period=period,
            interval=interval,
            group_by="ticker",
            auto_adjust=True,
            progress=False,
        )
    except Exception as e:
        logger.error(f"[MacroClient] yfinance download failed: {e}")
        raise

    results: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        try:
            if len(tickers) == 1:
                df = raw.copy()
            else:
                df = raw[ticker].copy()

            df.dropna(how="all", inplace=True)
            df.index = pd.to_datetime(df.index)
            df.columns = [c.lower() for c in df.columns]
            results[ticker] = df
            logger.info(f"[MacroClient] {ticker}: {len(df)} records fetched.")
        except Exception as e:
            logger.warning(f"[MacroClient] Failed to process ticker '{ticker}': {e}")
            continue

    return results


def fetch_latest_macro_snapshot(tickers: Optional[list[str]] = None) -> dict[str, dict]:
    """
    Fetch only the latest closing value for each macro ticker.
    Fast single-record pull — used for real-time dashboard display.

    Returns:
        {
            "BZ=F": {"close": 74.20, "date": "2026-10-31", "label": "Brent Crude Oil"},
            ...
        }
    """
    tickers = tickers or MACRO_TICKERS
    # Fetch last 5 business days to ensure at least 1 trading day is available
    history = fetch_macro_history(tickers=tickers, period="5d")

    snapshot: dict[str, dict] = {}
    for ticker, df in history.items():
        if df.empty:
            continue
        latest_row = df.iloc[-1]
        latest_date = df.index[-1].strftime("%Y-%m-%d")
        snapshot[ticker] = {
            "ticker": ticker,
            "label": TICKER_LABELS.get(ticker, ticker),
            "close": round(float(latest_row.get("close", latest_row.iloc[0])), 4),
            "date": latest_date,
        }

    # Calculate 1-day % change for shock detection
    if len(history.get("BZ=F", pd.DataFrame())) >= 2:
        for ticker, df in history.items():
            if ticker in snapshot and len(df) >= 2:
                prev_close = float(df.iloc[-2].get("close", df.iloc[-2].iloc[0]))
                curr_close = snapshot[ticker]["close"]
                pct_change = (curr_close - prev_close) / prev_close * 100 if prev_close else 0
                snapshot[ticker]["pct_change_1d"] = round(pct_change, 3)

    logger.info(f"[MacroClient] Latest snapshot fetched for {len(snapshot)} tickers.")
    return snapshot


def detect_shock_alerts(snapshot: Optional[dict] = None) -> list[dict]:
    """
    Evaluate current macro snapshot against shock thresholds.
    Returns a list of active alerts (empty list if no shocks detected).

    Each alert dict:
        {ticker, label, current_value, threshold, alert_type, message}

    Alert types:
        "LEVEL"  — absolute level exceeded (e.g. VIX > 20)
        "MOVE"   — single-day % move exceeded (e.g. Crude > +4%)
    """
    if snapshot is None:
        snapshot = fetch_latest_macro_snapshot()

    alerts = []

    # --- Brent Crude: 1-day surge ---
    crude = snapshot.get("BZ=F", {})
    crude_move = crude.get("pct_change_1d", 0)
    if abs(crude_move) >= SHOCK_THRESHOLDS["BZ=F"]:
        direction = "surged" if crude_move > 0 else "plunged"
        alerts.append({
            "ticker": "BZ=F",
            "label": "Brent Crude Oil",
            "current_value": crude["close"],
            "change_pct": crude_move,
            "threshold": SHOCK_THRESHOLDS["BZ=F"],
            "alert_type": "MOVE",
            "severity": "HIGH",
            "message": (
                f"⚠️ Crude Oil {direction} {crude_move:+.1f}% in 24 hours "
                f"(${crude['close']:.2f}/barrel). "
                f"This typically impacts India's inflation, CAD, and equity markets."
            ),
        })

    # --- India VIX: absolute level ---
    vix = snapshot.get("^INDIAVIX", {})
    vix_level = vix.get("close", 0)
    if vix_level >= SHOCK_THRESHOLDS["^INDIAVIX"]:
        severity = "HIGH" if vix_level >= 25 else "MEDIUM"
        alerts.append({
            "ticker": "^INDIAVIX",
            "label": "India VIX",
            "current_value": vix_level,
            "threshold": SHOCK_THRESHOLDS["^INDIAVIX"],
            "alert_type": "LEVEL",
            "severity": severity,
            "message": (
                f"⚠️ India VIX at {vix_level:.1f} — fear gauge elevated. "
                f"Historically, VIX > 20 correlates with short-term market turbulence."
            ),
        })

    # --- USD/INR: Rupee depreciation ---
    usdinr = snapshot.get("USDINR=X", {})
    rupee_move = usdinr.get("pct_change_1d", 0)
    if rupee_move >= SHOCK_THRESHOLDS["USDINR=X"]:
        alerts.append({
            "ticker": "USDINR=X",
            "label": "USD/INR",
            "current_value": usdinr["close"],
            "change_pct": rupee_move,
            "threshold": SHOCK_THRESHOLDS["USDINR=X"],
            "alert_type": "MOVE",
            "severity": "MEDIUM",
            "message": (
                f"⚠️ Rupee depreciated {rupee_move:+.2f}% to ₹{usdinr['close']:.2f}/USD today. "
                f"Sustained depreciation drives FII outflows and inflation."
            ),
        })

    # --- US 10Y Yield: Capital flight risk ---
    us10y = snapshot.get("^TNX", {})
    yield_level = us10y.get("close", 0)
    if yield_level >= SHOCK_THRESHOLDS["^TNX"]:
        alerts.append({
            "ticker": "^TNX",
            "label": "US 10Y Treasury Yield",
            "current_value": yield_level,
            "threshold": SHOCK_THRESHOLDS["^TNX"],
            "alert_type": "LEVEL",
            "severity": "MEDIUM",
            "message": (
                f"⚠️ US 10-Year yield at {yield_level:.2f}% — above 5% threshold. "
                f"FIIs typically reduce EM equity exposure when US yields are this attractive."
            ),
        })

    if alerts:
        logger.warning(f"[MacroClient] {len(alerts)} shock alert(s) detected.")
    else:
        logger.info("[MacroClient] No macro shock alerts. Market conditions normal.")

    return alerts


def get_macro_records_for_storage(tickers: Optional[list[str]] = None, period: str = "5y") -> dict[str, list[dict]]:
    """
    Fetch macro history and format it for bulk insertion into the local SQLite database.

    Returns:
        {ticker: [{"date": "YYYY-MM-DD", "close": float, "open": float, ...}, ...]}
    """
    history = fetch_macro_history(tickers=tickers, period=period)
    storage_records: dict[str, list[dict]] = {}

    for ticker, df in history.items():
        records = []
        for date, row in df.iterrows():
            records.append({
                "date": date.strftime("%Y-%m-%d"),
                "close": float(row.get("close", 0)) if pd.notna(row.get("close")) else None,
                "open":  float(row.get("open", 0))  if pd.notna(row.get("open"))  else None,
                "high":  float(row.get("high", 0))  if pd.notna(row.get("high"))  else None,
                "low":   float(row.get("low", 0))   if pd.notna(row.get("low"))   else None,
                "volume": float(row.get("volume", 0)) if pd.notna(row.get("volume")) else None,
            })
        storage_records[ticker] = records

    return storage_records

