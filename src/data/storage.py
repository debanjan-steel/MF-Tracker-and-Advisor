"""
storage.py — Local SQLite Caching Layer
Stores scheme metadata, full historical NAVs, and macro data locally.
Implements incremental sync (only downloads latest NAV delta each night).
"""

import logging
import sqlite3
import os
from datetime import datetime
from typing import Optional
from contextlib import contextmanager

import pandas as pd

from src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

DB_PATH = settings.db_path
os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else ".", exist_ok=True)

# ---------------------------------------------------------------------------
# DDL — Schema Definitions
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
-- Scheme master: one row per AMFI-registered mutual fund scheme
CREATE TABLE IF NOT EXISTS schemes (
    scheme_code     INTEGER PRIMARY KEY,
    scheme_name     TEXT NOT NULL,
    fund_house      TEXT,
    scheme_type     TEXT,
    scheme_category TEXT,
    isin_growth     TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

-- Daily NAV history: one row per scheme per business day
CREATE TABLE IF NOT EXISTS nav_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_code     INTEGER NOT NULL REFERENCES schemes(scheme_code),
    nav_date        TEXT NOT NULL,          -- ISO YYYY-MM-DD
    nav             REAL NOT NULL,
    nav_verified    INTEGER DEFAULT 0,      -- 1 if cross-verified against AMFI
    source          TEXT DEFAULT 'MFAPI',   -- 'MFAPI' | 'AMFI_FALLBACK'
    UNIQUE(scheme_code, nav_date)
);

-- Macro indicators: Crude, VIX, US10Y, DXY, USDINR, Gold, Nifty
CREATE TABLE IF NOT EXISTS macro_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker      TEXT NOT NULL,
    price_date  TEXT NOT NULL,             -- ISO YYYY-MM-DD
    close       REAL,
    open        REAL,
    high        REAL,
    low         REAL,
    volume      REAL,
    UNIQUE(ticker, price_date)
);

-- ML Prediction Ledger: formal forecast contracts
CREATE TABLE IF NOT EXISTS prediction_ledger (
    prediction_id       TEXT PRIMARY KEY,       -- UUID
    user_id             TEXT,                   -- Supabase auth user id (NULL = global)
    scheme_code         INTEGER,
    date_generated      TEXT NOT NULL,          -- ISO datetime
    target_date         TEXT NOT NULL,          -- ISO date (30/60/90 day horizon)
    horizon_days        INTEGER NOT NULL,
    predicted_return_pct REAL,                  -- e.g. +3.2
    predicted_nav_low   REAL,                   -- 80% confidence lower bound
    predicted_nav_high  REAL,                   -- 80% confidence upper bound
    directional_call    TEXT,                   -- 'UP' | 'DOWN'
    model_version       TEXT,
    feature_snapshot    TEXT,                   -- JSON blob of input features
    status              TEXT DEFAULT 'PENDING', -- 'PENDING' | 'RESOLVED'
    actual_return_pct   REAL,                   -- filled on resolution
    actual_nav          REAL,
    mae                 REAL,
    directional_correct INTEGER,                -- 1=correct, 0=wrong
    resolved_at         TEXT
);

-- Sync tracking: last successful sync per scheme
CREATE TABLE IF NOT EXISTS sync_log (
    scheme_code     INTEGER PRIMARY KEY,
    last_synced_at  TEXT NOT NULL,             -- ISO datetime
    last_nav_date   TEXT NOT NULL,             -- latest NAV date in DB
    records_stored  INTEGER DEFAULT 0
);

-- Macro sync tracking
CREATE TABLE IF NOT EXISTS macro_sync_log (
    ticker          TEXT PRIMARY KEY,
    last_synced_at  TEXT NOT NULL,
    last_price_date TEXT NOT NULL
);

-- User portfolio holdings
CREATE TABLE IF NOT EXISTS user_holdings (
    id                  TEXT PRIMARY KEY,
    user_id             TEXT NOT NULL,
    scheme_code         INTEGER NOT NULL,
    scheme_name         TEXT NOT NULL,
    units               REAL NOT NULL,
    avg_nav             REAL NOT NULL,
    invested_amount     REAL NOT NULL,
    category            TEXT DEFAULT 'Equity',
    folio_number        TEXT,
    investment_type     TEXT DEFAULT 'LUMPSUM',
    investment_date     TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, scheme_code)
);

-- Index for fast time-series queries
CREATE INDEX IF NOT EXISTS idx_nav_scheme_date  ON nav_history(scheme_code, nav_date DESC);
CREATE INDEX IF NOT EXISTS idx_macro_ticker_date ON macro_history(ticker, price_date DESC);
CREATE INDEX IF NOT EXISTS idx_prediction_status ON prediction_ledger(status, target_date);
CREATE INDEX IF NOT EXISTS idx_user_holdings_user ON user_holdings(user_id);
"""


# ---------------------------------------------------------------------------
# Connection Management
# ---------------------------------------------------------------------------

@contextmanager
def get_db():
    """Context manager for SQLite connection with WAL mode for concurrency."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # Rows accessible as dicts
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create all tables and indexes if they don't already exist."""
    with get_db() as conn:
        conn.executescript(SCHEMA_SQL)
    logger.info(f"[Storage] Database initialised at '{DB_PATH}'.")


# ---------------------------------------------------------------------------
# Scheme Master
# ---------------------------------------------------------------------------

def upsert_schemes(schemes: list[dict]):
    """
    Insert or update scheme metadata records.
    schemes: list of dicts with keys: scheme_code, scheme_name,
             fund_house, scheme_type, scheme_category
    """
    sql = """
        INSERT INTO schemes (scheme_code, scheme_name, fund_house, scheme_type, scheme_category, updated_at)
        VALUES (:scheme_code, :scheme_name, :fund_house, :scheme_type, :scheme_category, datetime('now'))
        ON CONFLICT(scheme_code) DO UPDATE SET
            scheme_name     = excluded.scheme_name,
            fund_house      = excluded.fund_house,
            scheme_type     = excluded.scheme_type,
            scheme_category = excluded.scheme_category,
            updated_at      = excluded.updated_at
    """
    with get_db() as conn:
        conn.executemany(sql, schemes)
    logger.info(f"[Storage] Upserted {len(schemes)} scheme records.")


def get_scheme(scheme_code: int) -> Optional[dict]:
    """Retrieve scheme metadata by code."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM schemes WHERE scheme_code = ?", (scheme_code,)
        ).fetchone()
        return dict(row) if row else None


def get_all_scheme_codes_from_db() -> list[int]:
    """Return all scheme codes stored in the local DB."""
    with get_db() as conn:
        rows = conn.execute("SELECT scheme_code FROM schemes").fetchall()
        return [r["scheme_code"] for r in rows]


# ---------------------------------------------------------------------------
# NAV History — Insert & Incremental Sync
# ---------------------------------------------------------------------------

def get_last_nav_date(scheme_code: int) -> Optional[str]:
    """
    Return the most recent NAV date stored for a scheme (ISO format).
    Used by the incremental sync engine to determine how many new records to fetch.
    Returns None if no data exists yet for this scheme.
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT MAX(nav_date) as last_date FROM nav_history WHERE scheme_code = ?",
            (scheme_code,),
        ).fetchone()
        return row["last_date"] if row and row["last_date"] else None


def bulk_insert_nav_history(scheme_code: int, nav_records: list[dict], source: str = "MFAPI"):
    """
    Insert NAV records for a scheme. Skips duplicates (UNIQUE constraint).

    nav_records: [{"date": "YYYY-MM-DD", "nav": float, "nav_verified": bool}, ...]
    Returns the number of new rows actually inserted.
    """
    sql = """
        INSERT OR IGNORE INTO nav_history (scheme_code, nav_date, nav, nav_verified, source)
        VALUES (?, ?, ?, ?, ?)
    """
    rows = [
        (scheme_code, r["date"], r["nav"], int(r.get("nav_verified", False)), source)
        for r in nav_records
    ]
    with get_db() as conn:
        cursor = conn.executemany(sql, rows)
        inserted = cursor.rowcount
    if inserted > 0:
        _update_sync_log(scheme_code, nav_records[0]["date"] if nav_records else "")
    logger.info(f"[Storage] Scheme {scheme_code}: {inserted}/{len(rows)} new NAV records inserted.")
    return inserted


def get_nav_history_df(scheme_code: int, start_date: Optional[str] = None) -> pd.DataFrame:
    """
    Load NAV history for a scheme as a sorted Pandas DataFrame.

    Returns DataFrame with columns: [nav_date, nav, nav_verified, source]
    Sorted by nav_date ascending (oldest first — correct for time-series analysis).
    """
    query = "SELECT nav_date, nav, nav_verified, source FROM nav_history WHERE scheme_code = ?"
    params: list = [scheme_code]
    if start_date:
        query += " AND nav_date >= ?"
        params.append(start_date)
    query += " ORDER BY nav_date ASC"

    with get_db() as conn:
        df = pd.read_sql_query(query, conn, params=params)

    if df.empty:
        return df

    df["nav_date"] = pd.to_datetime(df["nav_date"])
    df.set_index("nav_date", inplace=True)
    return df


def incremental_sync(scheme_code: int, all_nav_records: list[dict]) -> int:
    """
    Efficient incremental sync: only inserts NAV records newer than the
    last stored date, avoiding redundant re-insertion of historical data.

    Returns number of new records inserted.
    """
    last_date = get_last_nav_date(scheme_code)
    if last_date is None:
        # First time — insert everything
        new_records = all_nav_records
    else:
        # Only insert records newer than what we already have
        new_records = [r for r in all_nav_records if r["date"] > last_date]

    if not new_records:
        logger.info(f"[Storage] Scheme {scheme_code}: already up to date (last: {last_date}).")
        return 0

    return bulk_insert_nav_history(scheme_code, new_records)


# ---------------------------------------------------------------------------
# Macro Data
# ---------------------------------------------------------------------------

def bulk_insert_macro(ticker: str, records: list[dict]):
    """
    Insert macro indicator records. Skips duplicates.
    records: [{"date": "YYYY-MM-DD", "close": float, "open": float, ...}, ...]
    """
    sql = """
        INSERT OR IGNORE INTO macro_history (ticker, price_date, close, open, high, low, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    rows = [
        (ticker, r["date"], r.get("close"), r.get("open"), r.get("high"), r.get("low"), r.get("volume"))
        for r in records
    ]
    with get_db() as conn:
        cursor = conn.executemany(sql, rows)
        inserted = cursor.rowcount
    logger.info(f"[Storage] Macro '{ticker}': {inserted} new records inserted.")
    # Update macro sync log
    if records:
        _update_macro_sync_log(ticker, records[0]["date"])
    return inserted


def get_macro_df(ticker: str, start_date: Optional[str] = None) -> pd.DataFrame:
    """Load macro history as a sorted DataFrame."""
    query = "SELECT price_date, close, open, high, low, volume FROM macro_history WHERE ticker = ?"
    params: list = [ticker]
    if start_date:
        query += " AND price_date >= ?"
        params.append(start_date)
    query += " ORDER BY price_date ASC"

    with get_db() as conn:
        df = pd.read_sql_query(query, conn, params=params)

    if not df.empty:
        df["price_date"] = pd.to_datetime(df["price_date"])
        df.set_index("price_date", inplace=True)
    return df


def get_last_macro_date(ticker: str) -> Optional[str]:
    """Return the most recent price date stored for a macro ticker."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT MAX(price_date) as last_date FROM macro_history WHERE ticker = ?",
            (ticker,),
        ).fetchone()
        return row["last_date"] if row and row["last_date"] else None


# ---------------------------------------------------------------------------
# Sync Log Helpers
# ---------------------------------------------------------------------------

def _update_sync_log(scheme_code: int, latest_nav_date: str):
    sql = """
        INSERT INTO sync_log (scheme_code, last_synced_at, last_nav_date, records_stored)
        VALUES (?, datetime('now'), ?, 1)
        ON CONFLICT(scheme_code) DO UPDATE SET
            last_synced_at = datetime('now'),
            last_nav_date  = excluded.last_nav_date
    """
    with get_db() as conn:
        conn.execute(sql, (scheme_code, latest_nav_date))


def _update_macro_sync_log(ticker: str, latest_date: str):
    sql = """
        INSERT INTO macro_sync_log (ticker, last_synced_at, last_price_date)
        VALUES (?, datetime('now'), ?)
        ON CONFLICT(ticker) DO UPDATE SET
            last_synced_at  = datetime('now'),
            last_price_date = excluded.last_price_date
    """
    with get_db() as conn:
        conn.execute(sql, (ticker, latest_date))

