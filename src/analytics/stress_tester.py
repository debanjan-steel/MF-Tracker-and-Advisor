"""
src/analytics/stress_tester.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"What-If" Scenario Stress Tester & Black Swan Simulator.

Answers: "What would happen to my portfolio if a severe macroeconomic anomaly occurs?"

Built-in scenarios:
  1. COVID-19 Crash (Feb–Mar 2020): Nifty -38% in 40 days
  2. 2008 GFC: Nifty -60% over 12 months
  3. Crude Oil Spike (>$120): Historical impact on Indian MFs (-12%)
  4. US Fed Rate Hike & FII Outflow Cycle (-18%)
  5. Rupee Collapse (>₹90/$): Macro currency stress (-10%)
  6. Indian Election / Hung Coalition Uncertainty (-8%)
  7. Taiwan Strait / Geopolitical Tech Supply Shock (-24%)
  8. Custom: User-defined drawdown % and duration

Output:
  - Projected portfolio value after shock
  - Exact loss in ₹ and %
  - Category-by-category breakdown with relative vulnerability
  - Recovery time estimate (months and estimated date)
  - Institutional action playbook & SIP opportunity analysis
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, Dict, Any, List

import numpy as np
import pandas as pd

from .metrics import calculate_cagr
from src.config import get_settings

logger = logging.getLogger(__name__)

MAX_ACTIVE_EVENTS = 7

# ─────────────────────────────────────────────────────────────────────────────
# Default Modern Tracked Macro Event Seed Data (Rolling Queue)
# ─────────────────────────────────────────────────────────────────────────────

INITIAL_DYNAMIC_EVENTS = [
    {
        "key": "mideast_hormuz_oil_2026",
        "name": "Middle East Conflict & Hormuz Strait Blockade (2025–2026)",
        "event_year": 2026,
        "peak_to_trough_pct": -16.0,
        "duration_days": 60,
        "recovery_months": 5,
        "category_tag": "Geopolitical & Maritime Oil Chokepoint",
        "description": "Active conflict in the Persian Gulf / Red Sea threatening 20% of global seaborne oil flows, spiking container freight, and inflating Indian CAD.",
        "category_impacts": {
            "Large Cap": -14.0,
            "Mid Cap": -20.0,
            "Small Cap": -25.0,
            "Flexi Cap": -16.0,
            "Arbitrage": +2.5,
            "Liquid / Debt": +3.0,
            "Sectoral — Oil & Gas": +12.0,
        },
        "is_active": 1,
        "is_live_monitored": 1,
    },
    {
        "key": "us_universal_tariffs_2025",
        "name": "US Reciprocal Tariff Shock & Global Trade War 2.0 (2025–2026)",
        "event_year": 2025,
        "peak_to_trough_pct": -22.0,
        "duration_days": 120,
        "recovery_months": 9,
        "category_tag": "Global Trade Barriers & Export Squeeze",
        "description": "Universal 10%–25% import tariffs disrupting cross-border manufacturing, supply chains, and denting IT and pharmaceutical export earnings.",
        "category_impacts": {
            "Large Cap": -18.0,
            "Mid Cap": -26.0,
            "Small Cap": -32.0,
            "Flexi Cap": -22.0,
            "Arbitrage": +3.0,
            "Liquid / Debt": +4.0,
            "Sectoral — IT": -28.0,
            "Sectoral — Pharma": -12.0,
        },
        "is_active": 1,
        "is_live_monitored": 1,
    },
    {
        "key": "yen_carry_unwind_2024",
        "name": "Yen Carry Trade Liquidation & Flash De-leveraging (2024–2025)",
        "event_year": 2024,
        "peak_to_trough_pct": -14.0,
        "duration_days": 30,
        "recovery_months": 4,
        "category_tag": "Cross-Border Liquidity Shock",
        "description": "Bank of Japan rate normalization triggering multi-billion dollar leveraged carry trade liquidations and worldwide equity flash sell-offs.",
        "category_impacts": {
            "Large Cap": -12.0,
            "Mid Cap": -18.0,
            "Small Cap": -22.0,
            "Flexi Cap": -14.0,
            "Arbitrage": +2.0,
            "Liquid / Debt": +3.2,
        },
        "is_active": 1,
        "is_live_monitored": 0,
    },
    {
        "key": "sebi_smallcap_froth_2024",
        "name": "India Small & Mid-Cap Froth Correction (SEBI Mandate)",
        "event_year": 2024,
        "peak_to_trough_pct": -20.0,
        "duration_days": 90,
        "recovery_months": 7,
        "category_tag": "Domestic Valuation Overheating & Liquidity Stress",
        "description": "Regulatory liquidity stress tests and cautionary guidelines on froth in small/mid-caps triggering sharp sector de-rating and mutual fund cash buffers.",
        "category_impacts": {
            "Large Cap": -8.0,
            "Mid Cap": -24.0,
            "Small Cap": -35.0,
            "Flexi Cap": -16.0,
            "Arbitrage": +2.5,
            "Liquid / Debt": +3.5,
        },
        "is_active": 1,
        "is_live_monitored": 1,
    },
    {
        "key": "us10y_yield_spike_2024",
        "name": "US 10Y Treasury Spike (>4.8%) & FII Capital Outflow",
        "event_year": 2024,
        "peak_to_trough_pct": -18.0,
        "duration_days": 150,
        "recovery_months": 8,
        "category_tag": "Global Sovereign Debt & FII Flight",
        "description": "US fiscal deficit keeps long-term yields elevated, drawing institutional FII flows out of emerging markets into dollar cash assets.",
        "category_impacts": {
            "Large Cap": -15.0,
            "Mid Cap": -22.0,
            "Small Cap": -28.0,
            "Flexi Cap": -18.0,
            "Arbitrage": +4.0,
            "Liquid / Debt": +5.5,
            "Sectoral — IT": -26.0,
        },
        "is_active": 1,
        "is_live_monitored": 0,
    },
    {
        "key": "rupee_record_low_2025",
        "name": "Rupee All-Time Low (USD/INR > ₹86.5) & Import Inflation",
        "event_year": 2025,
        "peak_to_trough_pct": -11.0,
        "duration_days": 60,
        "recovery_months": 5,
        "category_tag": "Currency Depreciation Stress",
        "description": "Dollar index strength pushes USD/INR to historic lows, raising imported inflation and prompting RBI domestic liquidity tightening.",
        "category_impacts": {
            "Large Cap": -9.0,
            "Mid Cap": -13.0,
            "Small Cap": -16.0,
            "Flexi Cap": -11.0,
            "Arbitrage": +2.2,
            "Liquid / Debt": +3.0,
            "Sectoral — IT": +6.0,
            "Sectoral — Pharma": +5.0,
        },
        "is_active": 1,
        "is_live_monitored": 1,
    },
    {
        "key": "covid_crash_2020",
        "name": "COVID-19 Flash Crash (Feb–Mar 2020)",
        "event_year": 2020,
        "peak_to_trough_pct": -38.0,
        "duration_days": 40,
        "recovery_months": 6,
        "category_tag": "Global Pandemic & Liquidity Shock",
        "description": "Nifty 50 fell 38% in 40 days (Jan 14 → Mar 23, 2020), followed by unprecedented global stimulus and rapid 6-month recovery.",
        "category_impacts": {
            "Large Cap": -34.0,
            "Mid Cap": -42.0,
            "Small Cap": -50.0,
            "Flexi Cap": -38.0,
            "Arbitrage": +1.5,
            "Liquid / Debt": +3.0,
            "Sectoral — Healthcare": +10.0,
            "Sectoral — IT": -20.0,
        },
        "is_active": 1,
        "is_live_monitored": 0,
    },
    # ── Retired Historical Events (Aged out to make place for modern events) ──
    {
        "key": "gfc_2008",
        "name": "Global Financial Crisis (2008–09)",
        "event_year": 2008,
        "peak_to_trough_pct": -60.0,
        "duration_days": 365,
        "recovery_months": 24,
        "category_tag": "Retired Historical Benchmark",
        "description": "Aged out: 2008 GFC retired from active queue to make place for modern 2024–2026 tracked macro crises.",
        "category_impacts": {
            "Large Cap": -56.0,
            "Mid Cap": -68.0,
            "Small Cap": -75.0,
            "Flexi Cap": -60.0,
            "Arbitrage": +5.5,
            "Liquid / Debt": +8.8,
        },
        "is_active": 0,
        "is_live_monitored": 0,
    },
]

# Legacy backward-compatibility dictionary
BUILT_IN_SCENARIOS = {e["key"]: e for e in INITIAL_DYNAMIC_EVENTS}


# ─────────────────────────────────────────────────────────────────────────────
# SQLite Dynamic Scenarios Database & Rolling Event Management
# ─────────────────────────────────────────────────────────────────────────────

def _get_stress_db() -> sqlite3.Connection:
    settings = get_settings()
    os.makedirs(os.path.dirname(settings.db_path) if os.path.dirname(settings.db_path) else ".", exist_ok=True)
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dynamic_stress_scenarios (
            key                 TEXT PRIMARY KEY,
            name                TEXT NOT NULL,
            event_year          INTEGER NOT NULL,
            peak_to_trough_pct  REAL NOT NULL,
            duration_days       INTEGER NOT NULL,
            recovery_months     INTEGER NOT NULL,
            category_tag        TEXT NOT NULL,
            description         TEXT NOT NULL,
            category_impacts    TEXT NOT NULL,
            is_active           INTEGER DEFAULT 1,
            is_live_monitored   INTEGER DEFAULT 0,
            created_at          TEXT DEFAULT (datetime('now')),
            updated_at          TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()

    # Seed if empty
    cur = conn.execute("SELECT COUNT(*) FROM dynamic_stress_scenarios")
    if cur.fetchone()[0] == 0:
        for ev in INITIAL_DYNAMIC_EVENTS:
            conn.execute(
                """
                INSERT OR IGNORE INTO dynamic_stress_scenarios (
                    key, name, event_year, peak_to_trough_pct, duration_days,
                    recovery_months, category_tag, description, category_impacts,
                    is_active, is_live_monitored
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ev["key"],
                    ev["name"],
                    ev["event_year"],
                    ev["peak_to_trough_pct"],
                    ev["duration_days"],
                    ev["recovery_months"],
                    ev["category_tag"],
                    ev["description"],
                    json.dumps(ev.get("category_impacts", {})),
                    ev.get("is_active", 1),
                    ev.get("is_live_monitored", 0),
                ),
            )
        conn.commit()

    return conn


def get_active_stress_scenarios() -> Dict[str, Any]:
    """
    Retrieve currently active modern tracked macro scenarios.
    Returns active scenarios (sorted by year DESC) and metadata on the retired oldest event.
    """
    conn = _get_stress_db()
    try:
        cur = conn.execute(
            """
            SELECT * FROM dynamic_stress_scenarios
            WHERE is_active = 1
            ORDER BY event_year DESC, updated_at DESC
            LIMIT ?
            """,
            (MAX_ACTIVE_EVENTS,),
        )
        rows = cur.fetchall()

        scenarios = []
        for r in rows:
            try:
                impacts = json.loads(r["category_impacts"])
            except Exception:
                impacts = {}

            scenarios.append({
                "key": r["key"],
                "name": r["name"],
                "event_year": r["event_year"],
                "drawdown_pct": r["peak_to_trough_pct"],
                "recovery_months": r["recovery_months"],
                "category_tag": r["category_tag"],
                "description": r["description"],
                "category_impacts": impacts,
                "is_live_monitored": bool(r["is_live_monitored"]),
                "status": "LIVE_ACTIVE_RISK" if r["is_live_monitored"] else "MONITORED_CYCLE",
            })

        # Fetch retired event info for user transparency
        cur_retired = conn.execute(
            "SELECT name, event_year FROM dynamic_stress_scenarios WHERE is_active = 0 ORDER BY event_year ASC LIMIT 1"
        )
        retired_row = cur_retired.fetchone()
        retired_info = (
            f"{retired_row['name']} ({retired_row['event_year']})"
            if retired_row
            else "2008 Global Financial Crisis (Aged out)"
        )

        return {
            "scenarios": scenarios,
            "max_active": MAX_ACTIVE_EVENTS,
            "active_count": len(scenarios),
            "retired_oldest_event": retired_info,
            "rolling_strategy": "Rolling Modern Window: Automatically adds latest tracked macro crises and retires the oldest historical event to maintain contemporary relevance.",
            "last_synced": datetime.now().strftime("%d %b %Y, %H:%M"),
        }
    finally:
        conn.close()


def add_or_update_macro_event(event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add a new modern macro event to the tracker.
    Automatically removes (retires) the oldest active event if the active count exceeds MAX_ACTIVE_EVENTS.
    """
    conn = _get_stress_db()
    try:
        new_key = event_dict.get("key") or f"macro_event_{datetime.now().strftime('%Y%m%d%H%M')}"
        new_name = event_dict.get("name") or "New Macro Shock"
        new_year = int(event_dict.get("event_year") or datetime.now().year)
        drawdown = float(event_dict.get("peak_to_trough_pct") or event_dict.get("drawdown_pct") or -15.0)
        duration = int(event_dict.get("duration_days") or 60)
        rec_months = int(event_dict.get("recovery_months") or 6)
        tag = str(event_dict.get("category_tag") or "Modern Macro Risk")
        desc = str(event_dict.get("description") or "Dynamic macro event tracked by real-time market anomaly engine.")
        impacts = event_dict.get("category_impacts") or {
            "Large Cap": round(drawdown * 0.88, 1),
            "Mid Cap": round(drawdown * 1.15, 1),
            "Small Cap": round(drawdown * 1.35, 1),
            "Flexi Cap": drawdown,
            "Liquid / Debt": 3.0,
        }

        # Check count of currently active events
        cur = conn.execute("SELECT key, name, event_year FROM dynamic_stress_scenarios WHERE is_active = 1 ORDER BY event_year ASC, created_at ASC")
        active_list = cur.fetchall()

        retired_msg = None
        if len(active_list) >= MAX_ACTIVE_EVENTS:
            # Retire the oldest active event
            oldest = active_list[0]
            conn.execute(
                "UPDATE dynamic_stress_scenarios SET is_active = 0, updated_at = datetime('now') WHERE key = ?",
                (oldest["key"],),
            )
            retired_msg = f"Retired oldest event '{oldest['name']}' ({oldest['event_year']}) to make place for newest modern event."
            logger.info("[StressTester] %s", retired_msg)

        # Upsert the new event
        conn.execute(
            """
            INSERT INTO dynamic_stress_scenarios (
                key, name, event_year, peak_to_trough_pct, duration_days,
                recovery_months, category_tag, description, category_impacts,
                is_active, is_live_monitored, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, datetime('now'))
            ON CONFLICT(key) DO UPDATE SET
                name = excluded.name,
                event_year = excluded.event_year,
                peak_to_trough_pct = excluded.peak_to_trough_pct,
                duration_days = excluded.duration_days,
                recovery_months = excluded.recovery_months,
                category_tag = excluded.category_tag,
                description = excluded.description,
                category_impacts = excluded.category_impacts,
                is_active = 1,
                is_live_monitored = 1,
                updated_at = datetime('now')
            """,
            (
                new_key,
                new_name,
                new_year,
                drawdown,
                duration,
                rec_months,
                tag,
                desc,
                json.dumps(impacts),
            ),
        )
        conn.commit()

        return {
            "success": True,
            "action": "event_registered",
            "message": f"Successfully tracked modern event '{new_name}' ({new_year}).",
            "retired_event": retired_msg,
        }
    finally:
        conn.close()


def sync_dynamic_macro_events() -> Dict[str, Any]:
    """
    Self-Updating Engine: Inspects live macro indicators (Crude, VIX, USD/INR, US 10Y)
    and dynamically activates or fine-tunes modern crisis scenarios.
    """
    conn = _get_stress_db()
    try:
        # Check live indicators if available
        vix_val = None
        crude_val = None
        usdinr_val = None
        try:
            from src.data.macro_client import fetch_latest_macro_snapshot
            snap = fetch_latest_macro_snapshot()
            vix_val = snap.get("vix")
            crude_val = snap.get("crude")
            usdinr_val = snap.get("usdinr")
        except Exception:
            pass

        updates = []
        # Example dynamic checks:
        if crude_val and crude_val >= 82.0:
            conn.execute(
                """
                UPDATE dynamic_stress_scenarios
                SET is_live_monitored = 1,
                    description = 'Active Brent crude elevated at $' || ? || '/bbl, increasing imported inflation risk and CAD pressure.',
                    updated_at = datetime('now')
                WHERE key = 'mideast_hormuz_oil_2026'
                """,
                (round(crude_val, 1),),
            )
            updates.append(f"Updated Middle East / Hormuz shock: Brent at ${crude_val:.1f}")

        if usdinr_val and usdinr_val >= 85.0:
            conn.execute(
                """
                UPDATE dynamic_stress_scenarios
                SET is_live_monitored = 1,
                    description = 'USD/INR currently testing historic highs at ₹' || ? || ', prompting RBI intervention.',
                    updated_at = datetime('now')
                WHERE key = 'rupee_record_low_2025'
                """,
                (round(usdinr_val, 2),),
            )
            updates.append(f"Updated Rupee Pressure: USD/INR at ₹{usdinr_val:.2f}")

        conn.commit()
        active_deck = get_active_stress_scenarios()
        return {
            "success": True,
            "message": f"Macro Black Swan engine synchronized with live modern events. {len(updates)} live signals refreshed.",
            "updates": updates,
            "deck": active_deck,
        }
    finally:
        conn.close()


def get_scenario_by_key(scenario_key: str) -> Optional[Dict[str, Any]]:
    """Retrieve scenario details by key from SQLite or fallback dictionary."""
    conn = _get_stress_db()
    try:
        cur = conn.execute("SELECT * FROM dynamic_stress_scenarios WHERE key = ?", (scenario_key,))
        row = cur.fetchone()
        if row:
            try:
                impacts = json.loads(row["category_impacts"])
            except Exception:
                impacts = {}
            return {
                "name": row["name"],
                "peak_to_trough_pct": row["peak_to_trough_pct"],
                "duration_days": row["duration_days"],
                "recovery_months": row["recovery_months"],
                "category_tag": row["category_tag"],
                "description": row["description"],
                "category_impacts": impacts,
                "event_year": row["event_year"],
            }
    finally:
        conn.close()

    # Fallback to in-memory built-in dictionary
    return BUILT_IN_SCENARIOS.get(scenario_key)


# ─────────────────────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class StressTestResult:
    """Result of a single stress test scenario."""
    scenario_name: str
    scenario_description: str
    current_portfolio_value: float
    projected_trough_value: float
    projected_loss_amount: float
    projected_loss_pct: float
    recovery_months: int
    recovery_date_estimate: str
    category_breakdown: list[dict] = field(default_factory=list)
    worst_hit_category: str = ""
    most_resilient_category: str = ""
    recommended_action: str = ""
    silver_lining: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Stress Test Engine
# ─────────────────────────────────────────────────────────────────────────────

def run_stress_test(
    current_portfolio_value: float,
    scenario_key: str = "covid_crash_2020",
    holdings: Optional[list[dict]] = None,
    custom_drawdown_pct: Optional[float] = None,
    custom_recovery_months: Optional[int] = None,
    custom_macro_inputs: Optional[dict] = None,
) -> StressTestResult:
    """
    Run an institutional-grade stress test on user or simulated portfolio.
    """
    if scenario_key == "custom":
        drawdown_pct = custom_drawdown_pct if custom_drawdown_pct is not None else -20.0
        # If user passed custom macro inputs, compute dynamic drawdown
        if custom_macro_inputs:
            c_crude = float(custom_macro_inputs.get("crude") or 78)
            c_vix = float(custom_macro_inputs.get("vix") or 14)
            c_us10y = float(custom_macro_inputs.get("us10y") or 4.2)
            c_usdinr = float(custom_macro_inputs.get("usdinr") or 84)

            # Sensitivity coefficients
            crude_impact = max(0.0, (c_crude - 85.0) * 0.25)
            vix_impact = max(0.0, (c_vix - 16.0) * 0.9)
            yield_impact = max(0.0, (c_us10y - 4.2) * 5.0)
            inr_impact = max(0.0, (c_usdinr - 84.0) * 1.5)
            computed_drawdown = -(crude_impact + vix_impact + yield_impact + inr_impact)
            if computed_drawdown < -2.0:
                drawdown_pct = max(-65.0, round(computed_drawdown, 1))

        rec_months = custom_recovery_months or max(3, int(abs(drawdown_pct) * 0.5))
        scenario = {
            "name": f"Custom Macro Shock ({drawdown_pct:.1f}% Drawdown)",
            "peak_to_trough_pct": drawdown_pct,
            "duration_days": 90,
            "recovery_months": rec_months,
            "category_tag": "Custom Simulation",
            "description": "User-defined shock parameterized by custom market stress variables.",
            "category_impacts": {
                "Large Cap": round(drawdown_pct * 0.88, 1),
                "Mid Cap": round(drawdown_pct * 1.15, 1),
                "Small Cap": round(drawdown_pct * 1.35, 1),
                "Flexi Cap": round(drawdown_pct * 0.95, 1),
                "Arbitrage": +2.5,
                "Liquid / Debt": +3.5,
            },
        }
    else:
        scenario = get_scenario_by_key(scenario_key) or BUILT_IN_SCENARIOS.get(scenario_key, BUILT_IN_SCENARIOS["mideast_hormuz_oil_2026"])
        drawdown_pct = scenario["peak_to_trough_pct"]
        rec_months = scenario["recovery_months"]

    category_impacts = scenario.get("category_impacts", {})

    # Calculate portfolio-level trough
    # If explicit holdings are provided with categories, aggregate weighted loss
    category_breakdown = []
    if holdings and len(holdings) > 0:
        total_val = sum(float(h.get("value") or h.get("current_value") or 0.0) for h in holdings)
        if total_val <= 0:
            total_val = current_portfolio_value

        agg_trough = 0.0
        for h in holdings:
            cat = h.get("category") or h.get("scheme_category") or "Flexi Cap"
            # Normalize category string
            matched_impact = None
            for k, imp in category_impacts.items():
                if k.lower() in cat.lower() or cat.lower() in k.lower():
                    matched_impact = imp
                    break
            if matched_impact is None:
                matched_impact = drawdown_pct

            val = float(h.get("value") or h.get("current_value") or 0.0)
            trough_val = val * (1.0 + matched_impact / 100.0)
            loss_val = val - trough_val
            agg_trough += trough_val

            category_breakdown.append({
                "category": cat,
                "scheme_name": h.get("scheme_name") or cat,
                "current_value": round(val, 2),
                "scenario_impact_pct": round(matched_impact, 1),
                "projected_trough_value": round(trough_val, 2),
                "loss": round(loss_val, 2),
            })

        projected_trough = agg_trough
        loss_amount = total_val - projected_trough
        effective_drawdown_pct = round(-((loss_amount / total_val) * 100.0), 1) if total_val > 0 else drawdown_pct
    else:
        # Default synthesized portfolio split (Large 35%, Mid 30%, Small 25%, Debt 10%)
        effective_drawdown_pct = drawdown_pct
        projected_trough = current_portfolio_value * (1.0 + drawdown_pct / 100.0)
        loss_amount = current_portfolio_value - projected_trough

        synthesized_split = [
            ("Large Cap", 0.35, category_impacts.get("Large Cap", drawdown_pct * 0.9)),
            ("Mid Cap", 0.30, category_impacts.get("Mid Cap", drawdown_pct * 1.15)),
            ("Small Cap", 0.25, category_impacts.get("Small Cap", drawdown_pct * 1.35)),
            ("Liquid / Debt", 0.10, category_impacts.get("Liquid / Debt", +3.0)),
        ]
        for c_name, share, imp in synthesized_split:
            c_val = current_portfolio_value * share
            c_trough = c_val * (1.0 + imp / 100.0)
            category_breakdown.append({
                "category": c_name,
                "scheme_name": f"Hypothetical {c_name} Allocation",
                "current_value": round(c_val, 2),
                "scenario_impact_pct": round(imp, 1),
                "projected_trough_value": round(c_trough, 2),
                "loss": round(c_val - c_trough, 2),
            })

    # Find worst hit & most resilient
    sorted_by_impact = sorted(category_breakdown, key=lambda x: x["scenario_impact_pct"])
    worst_hit = sorted_by_impact[0]["category"] if sorted_by_impact else "Small Cap"
    most_resilient = sorted_by_impact[-1]["category"] if sorted_by_impact else "Liquid / Debt"

    # Recovery date estimate
    today = date.today()
    total_months = today.month + rec_months
    rec_year = today.year + (total_months - 1) // 12
    rec_month = (total_months - 1) % 12 + 1
    try:
        from datetime import date as dt_cls
        rec_date = dt_cls(rec_year, rec_month, 1)
        recovery_date_str = rec_date.strftime("%b %Y")
    except Exception:
        recovery_date_str = f"~{rec_months} months from now"

    # Recommended action playbook
    if effective_drawdown_pct >= -12.0:
        action = (
            "📋 MILD CORRECTION PLAYBOOK: Stay 100% invested. Continue regular monthly SIPs without interruption. "
            "Market drawdowns below 12% are standard noise. Do NOT redeem equity units."
        )
    elif effective_drawdown_pct >= -25.0:
        action = (
            "🛡️ ELEVATED CORRECTION PLAYBOOK: Maintain core equity SIPs. Double SIP amount on days when Nifty falls "
            ">2% in a single session. Avoid panic exits; historical recovery took under 10 months."
        )
    else:
        action = (
            "⚡ BLACK SWAN / CRISIS PLAYBOOK: Extreme market dislocation. Step 1: Zero panic selling. "
            "Step 2: Deploy accumulated liquid/arbitrage dry powder in 3 staggered tranches at 30-day intervals. "
            "Historically, every crash above -30% (2008, 2020) created massive 5-year multi-bagger returns."
        )

    # Silver lining: SIP unit accumulation boost
    units_benefit = (abs(effective_drawdown_pct) / (100.0 + effective_drawdown_pct)) * 100.0
    silver_lining = (
        f"📈 SIP DISPLACEMENT ADVANTAGE: At the projected market trough, every ₹10,000 SIP purchases "
        f"{units_benefit:+.1f}% more fund units than today. Systematic buyers profit most from crash recoveries."
    )

    return StressTestResult(
        scenario_name=scenario["name"],
        scenario_description=scenario["description"],
        current_portfolio_value=round(current_portfolio_value, 2),
        projected_trough_value=round(projected_trough, 2),
        projected_loss_amount=round(loss_amount, 2),
        projected_loss_pct=round(effective_drawdown_pct, 1),
        recovery_months=rec_months,
        recovery_date_estimate=recovery_date_str,
        category_breakdown=category_breakdown,
        worst_hit_category=worst_hit,
        most_resilient_category=most_resilient,
        recommended_action=action,
        silver_lining=silver_lining,
    )


def run_all_scenarios(
    current_portfolio_value: float,
    holdings: Optional[list[dict]] = None,
) -> list[StressTestResult]:
    """Run all built-in scenarios and return sorted by severity."""
    results = []
    for key in BUILT_IN_SCENARIOS:
        result = run_stress_test(current_portfolio_value, scenario_key=key, holdings=holdings)
        results.append(result)
    results.sort(key=lambda r: r.projected_loss_pct)
    return results
