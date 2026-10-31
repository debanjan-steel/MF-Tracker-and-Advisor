"""
scripts/nightly_sync.py
━━━━━━━━━━━━━━━━━━━━━━━
Autonomous 24/7 Cloud Worker Script.

Runs nightly at 9:30 PM IST (via GitHub Actions cron):
  1. Syncs latest closing NAV for all tracked mutual fund schemes
  2. Pulls closing macro snapshot via yfinance (Brent, VIX, US 10Y, USD/INR, Gold)
  3. Reconciles past predictions in prediction_ledger whose target dates arrived
  4. Computes latest Market Timing Score & Macro Downturn Probability
  5. Logs today's model predictions to prediction_ledger
  6. Evaluates active alerts and dispatches WhatsApp messages if conditions trigger

Zero laptop dependency: Runs standalone on GitHub Actions runners.
"""

from __future__ import annotations

import warnings
warnings.filterwarnings("ignore")

import asyncio
import logging
import os
import sys
from datetime import date
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.storage import (
    init_db,
    get_all_scheme_codes_from_db,
    incremental_sync,
    bulk_insert_macro,
    get_nav_history_df,
)
from src.data.data_manager import data_manager
from src.data.macro_client import (
    fetch_latest_macro_snapshot,
    get_macro_records_for_storage,
    detect_shock_alerts,
)
from src.analytics.timing_model import compute_timing_score
from src.analytics.macro_engine import compute_downturn_probability
from src.analytics.ledger import log_prediction, evaluate_predictions
from src.notifications.whatsapp_bot import (
    send_whatsapp_message,
    format_opportunity_alert,
    format_macro_shock_alert,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("nightly_sync")


async def run_nightly_sync() -> None:
    logger.info("🚀 Starting 24/7 Nightly Cloud Sync...")
    init_db()

    # ── Step 1: Sync Tracked Schemes NAV ──
    tracked_codes = get_all_scheme_codes_from_db()
    if not tracked_codes:
        # Default seed scheme (Parag Parikh Flexi Cap Regular & Direct) if none tracked
        tracked_codes = [122640, 122639]
        logger.info("No tracked schemes found in DB, using default seed: %s", tracked_codes)

    logger.info("Syncing NAV data for %d scheme(s)...", len(tracked_codes))
    nav_histories: dict[int, any] = {}

    for code in tracked_codes:
        try:
            history = data_manager.get_nav_history(code)
            records = history.get("data", []) if isinstance(history, dict) else history
            if records:
                inserted = incremental_sync(code, records)
                logger.info("Scheme %d: %d new records stored.", code, inserted)
            df = get_nav_history_df(code)
            if not df.empty:
                nav_histories[code] = df["nav"]
        except Exception as e:
            logger.error("Failed to sync scheme %d: %s", code, e)

    # ── Step 2: Macro Ingestion ──
    logger.info("Ingesting closing macro signals (Crude, VIX, US10Y, USDINR, Gold)...")
    try:
        macro_snapshot = fetch_latest_macro_snapshot()
        macro_dict = get_macro_records_for_storage()
        for ticker, records in macro_dict.items():
            if records:
                bulk_insert_macro(ticker, records)
        logger.info("Macro snapshot stored successfully.")
    except Exception as e:
        logger.error("Macro ingestion error: %s", e)
        macro_snapshot = {}

    # ── Step 3: Reconcile Predictions (Learning Feedback Loop) ──
    logger.info("Reconciling past predictions in ledger...")
    try:
        reconcile_result = evaluate_predictions(nav_histories, horizon_days=30)
        logger.info(
            "Evaluated %d predictions. Correct: %d. Accuracy: %s",
            reconcile_result.get("evaluated", 0),
            reconcile_result.get("correct", 0),
            reconcile_result.get("accuracy"),
        )
    except Exception as e:
        logger.error("Reconciliation error: %s", e)

    # ── Step 3b: Walk-Forward Model Retraining & Calibration ──
    logger.info("Executing walk-forward retrainer to re-calibrate timing weights...")
    try:
        from src.analytics.retrainer import retrain_weights
        calibration = retrain_weights(min_samples=5)
        logger.info("Retrainer completed: %s", calibration.improvement_note)
    except Exception as e:
        logger.error("Retrainer error: %s", e)

    # ── Step 4: Generate & Log Today's Predictions ──
    logger.info("Generating predictions and timing scores...")
    danger_info = compute_downturn_probability(macro_snapshot)
    danger_score = danger_info["danger_score"]

    alerts_to_send: list[str] = []

    for code, nav_series in nav_histories.items():
        try:
            timing_res = compute_timing_score(nav_series, macro_snapshot=macro_snapshot)
            score = timing_res["total_score"]
            current_nav = float(nav_series.iloc[-1])

            call = "HOLD"
            if score >= 75:
                call = "BUY"
            elif score <= 30 or danger_score >= 70:
                call = "REDUCE"

            log_prediction(
                scheme_code=code,
                prediction_date=date.today(),
                prediction=call,
                timing_score=score,
                danger_score=danger_score,
                nav_at_prediction=current_nav,
            )
            logger.info("Scheme %d: Timing Score=%.1f Call=%s", code, score, call)

            # Check if this qualifies for a Buy Alert
            if score >= 75:
                alerts_to_send.append(
                    format_opportunity_alert(
                        scheme_name=f"Scheme #{code}",
                        timing_score=score,
                        current_nav=current_nav,
                        recommended_action=timing_res["recommendation"],
                    )
                )
        except Exception as e:
            logger.error("Failed to generate prediction for %d: %s", code, e)

    # ── Step 5: Check Macro Shocks ──
    macro_shocks = detect_shock_alerts(macro_snapshot)
    for shock in macro_shocks:
        alerts_to_send.append(
            format_macro_shock_alert(
                shock_type=shock["metric"],
                detail=f"Triggered condition: {shock['message']}",
                downturn_prob=danger_score,
                dry_powder_recommendation=danger_info["summary"],
            )
        )

    # ── Step 6: Dispatch Alerts via WhatsApp ──
    user_phone = os.getenv("DEFAULT_WHATSAPP_TO")
    if user_phone and alerts_to_send:
        logger.info("Dispatching %d alert(s) to %s...", len(alerts_to_send), user_phone)
        for msg in alerts_to_send:
            send_whatsapp_message(user_phone, msg)
    else:
        logger.info("No active alerts triggered today or no phone number configured.")

    logger.info("✅ Nightly sync routine completed successfully.")


if __name__ == "__main__":
    asyncio.run(run_nightly_sync())
