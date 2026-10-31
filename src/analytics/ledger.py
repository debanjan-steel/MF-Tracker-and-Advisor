"""
src/analytics/ledger.py
━━━━━━━━━━━━━━━━━━━━━━━
ML Prediction Ledger — logs, evaluates, and enables retraining of
the market timing model's predictions.

The self-improving loop:
  1. Each night, the timing model makes a prediction (BUY / HOLD / REDUCE)
  2. The ledger records the prediction with timestamp + model inputs
  3. 30 / 90 days later, the evaluator checks actual NAV movement
  4. Accuracy metrics feed back to retrain the model weights

SQLite table: prediction_ledger
  - id, scheme_code, prediction_date, prediction (BUY/HOLD/REDUCE),
    timing_score, danger_score, actual_outcome (after 30d), accuracy_flag,
    evaluated_date, nav_at_prediction, nav_30d_later, return_30d
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

DB_PATH = Path(__file__).parent.parent.parent / "data" / "mf_platform.db"

# ─────────────────────────────────────────────────────────────────────────────
# Ledger Write
# ─────────────────────────────────────────────────────────────────────────────

def log_prediction(
    scheme_code: int,
    prediction_date: date,
    prediction: str,                  # "BUY" | "HOLD" | "REDUCE"
    timing_score: float,
    danger_score: float,
    nav_at_prediction: float,
    db_path: Path = DB_PATH,
) -> None:
    """
    Log a new timing model prediction to the prediction ledger.

    Maps to existing schema columns:
      date_generated  = prediction_date
      directional_call = prediction (BUY/HOLD/REDUCE)
      feature_snapshot = JSON of timing/danger scores
      target_date      = 30 days from prediction_date
      predicted_nav_low = nav_at_prediction (proxy)
    """
    import json
    import uuid
    from datetime import timedelta
    target_dt = (prediction_date + timedelta(days=30)).isoformat()
    feature_json = json.dumps({
        "timing_score": round(timing_score, 2),
        "danger_score": round(danger_score, 2),
    })
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            INSERT OR IGNORE INTO prediction_ledger
                (prediction_id, scheme_code, date_generated, target_date,
                 horizon_days, directional_call, predicted_nav_low,
                 feature_snapshot, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
        """, (
            str(uuid.uuid4()),
            scheme_code,
            prediction_date.isoformat(),
            target_dt,
            30,
            prediction,
            round(nav_at_prediction, 4),
            feature_json,
        ))


def get_unevaluated_predictions(
    horizon_days: int = 30,
    db_path: Path = DB_PATH,
) -> pd.DataFrame:
    """
    Fetch PENDING predictions that are old enough to evaluate.

    Returns
    -------
    pd.DataFrame
    """
    cutoff = (date.today() - timedelta(days=horizon_days)).isoformat()
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query("""
            SELECT * FROM prediction_ledger
            WHERE date_generated <= ?
              AND status = 'PENDING'
        """, conn, params=(cutoff,))
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Prediction Evaluator
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_predictions(
    nav_histories: dict[int, pd.Series],
    horizon_days: int = 30,
    db_path: Path = DB_PATH,
) -> dict:
    """
    Evaluate pending predictions against actual NAV movements.
    """
    pending = get_unevaluated_predictions(horizon_days, db_path)
    if pending.empty:
        return {"evaluated": 0, "correct": 0, "accuracy": float("nan")}

    evaluated = 0
    correct = 0

    with sqlite3.connect(db_path) as conn:
        for _, row in pending.iterrows():
            scheme_code = row["scheme_code"]
            pred_date = pd.to_datetime(row["date_generated"]).date()
            nav_at_pred = row["predicted_nav_low"]
            prediction = row["directional_call"]

            nav = nav_histories.get(scheme_code)
            if nav is None:
                continue

            target_date = pred_date + timedelta(days=horizon_days)
            future_navs = nav[nav.index.date >= target_date]  # type: ignore[attr-defined]

            if future_navs.empty:
                continue

            nav_future = float(future_navs.iloc[0])
            return_30d = (nav_future - nav_at_pred) / nav_at_pred if nav_at_pred > 0 else 0.0

            if return_30d > 0.01:
                actual_outcome = "BUY"
            elif return_30d < -0.01:
                actual_outcome = "REDUCE"
            else:
                actual_outcome = "HOLD"

            is_correct = (prediction == actual_outcome)

            conn.execute("""
                UPDATE prediction_ledger
                SET status = 'RESOLVED',
                    directional_correct = ?,
                    resolved_at = ?,
                    actual_nav = ?,
                    actual_return_pct = ?
                WHERE prediction_id = ?
            """, (
                1 if is_correct else 0,
                date.today().isoformat(),
                round(nav_future, 4),
                round(float(return_30d) * 100, 4),
                row["prediction_id"],
            ))

            evaluated += 1
            if is_correct:
                correct += 1

    accuracy = correct / evaluated if evaluated > 0 else float("nan")
    return {"evaluated": evaluated, "correct": correct, "accuracy": accuracy}


# ─────────────────────────────────────────────────────────────────────────────
# Accuracy Dashboard
# ─────────────────────────────────────────────────────────────────────────────

def get_model_accuracy_stats(db_path: Path = DB_PATH) -> dict:
    """
    Compute model accuracy statistics from evaluated predictions.

    Returns
    -------
    dict with keys: total_predictions, total_evaluated, overall_accuracy,
                    accuracy_by_type (BUY/HOLD/REDUCE), recent_30d_accuracy
    """
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query("""
            SELECT directional_call as prediction, directional_correct as accuracy_flag,
                   date_generated as prediction_date, actual_return_pct as return_30d
            FROM prediction_ledger
            WHERE status = 'RESOLVED'
        """, conn)
        total_count = conn.execute("SELECT COUNT(*) FROM prediction_ledger").fetchone()[0]

    if df.empty:
        return {
            "total_predictions": total_count,
            "total_evaluated": 0,
            "overall_accuracy": float("nan"),
            "accuracy_by_type": {},
            "recent_30d_accuracy": float("nan"),
            "avg_return_on_buy_signal": float("nan"),
        }

    overall = df["accuracy_flag"].mean()

    accuracy_by_type = {}
    for pred_type in ["BUY", "HOLD", "REDUCE"]:
        subset = df[df["prediction"] == pred_type]
        accuracy_by_type[pred_type] = subset["accuracy_flag"].mean() if not subset.empty else float("nan")

    # Recent 30 days
    recent_cutoff = (date.today() - timedelta(days=30)).isoformat()
    recent = df[df["prediction_date"] >= recent_cutoff]
    recent_accuracy = recent["accuracy_flag"].mean() if not recent.empty else float("nan")

    buy_signals = df[df["prediction"] == "BUY"]["return_30d"]
    avg_return_on_buy = float(buy_signals.mean()) if not buy_signals.empty else float("nan")

    return {
        "total_predictions": total_count,
        "total_evaluated": int(df["accuracy_flag"].notna().sum()),
        "overall_accuracy": float(overall),
        "accuracy_by_type": accuracy_by_type,
        "recent_30d_accuracy": float(recent_accuracy),
        "avg_return_on_buy_signal": avg_return_on_buy,
    }
