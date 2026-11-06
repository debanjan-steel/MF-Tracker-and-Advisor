"""
src/api/routes/portfolio.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Portfolio routes: CAS upload, holdings management, portfolio X-ray.
"""
from __future__ import annotations
import logging
import os
import sqlite3
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status
from pydantic import BaseModel

from src.auth.supabase_client import get_current_user
from src.data.data_manager import data_manager

logger = logging.getLogger(__name__)

router = APIRouter()


class HoldingInput(BaseModel):
    scheme_code: int
    scheme_name: str
    units: Optional[float] = None
    avg_nav: Optional[float] = None
    invested_amount: Optional[float] = None
    current_value: Optional[float] = None
    current_nav: Optional[float] = None
    category: str = "Equity"
    folio_number: Optional[str] = None
    sip_amount: Optional[float] = None
    sip_date: Optional[int] = None
    investment_type: str = "LUMPSUM"       # "SIP" | "LUMPSUM"
    investment_date: Optional[str] = None  # YYYY-MM-DD


def _get_portfolio_db() -> sqlite3.Connection:
    from src.config import get_settings
    settings = get_settings()
    os.makedirs(os.path.dirname(settings.db_path) if os.path.dirname(settings.db_path) else ".", exist_ok=True)
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
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
        )
        """
    )
    conn.commit()
    return conn


def _resolve_historical_nav(scheme_code: int, target_date_iso: str) -> Optional[float]:
    """Find the historical NAV on or immediately before target_date_iso."""
    try:
        nav_data = data_manager.get_nav_history(scheme_code)
        history = nav_data.get("data", [])
        if not history:
            return None
        clean_date = target_date_iso.strip()
        for r in history:
            if r.get("date") <= clean_date:
                return float(r["nav"])
        return float(history[-1]["nav"])
    except Exception as e:
        logger.warning(f"Error resolving historical NAV for scheme {scheme_code}: {e}")
        return None


@router.post("/upload-cas", summary="Upload CAS PDF to auto-import holdings")
async def upload_cas(
    file: UploadFile = File(..., description="Consolidated Account Statement (CAS) PDF"),
    pan_last4: str = "",
    user: dict = Depends(get_current_user),
):
    """
    Parse a CAS PDF and automatically import all mutual fund holdings.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted."
        )

    contents = await file.read()

    try:
        from src.data.cas_parser import parse_cas_pdf
        statement = parse_cas_pdf(contents, pan_password=pan_last4)
        holdings = []
        conn = _get_portfolio_db()
        try:
            for s in statement.schemes:
                units = float(s.close_units or 0)
                if units <= 0:
                    continue
                scheme_code = int(s.amfi_code) if s.amfi_code else 0
                val = float(s.valuation or 0)
                avg_nav = (val / units) if (val > 0 and units > 0) else 10.0
                invested = val if val > 0 else (units * avg_nav)

                # Upsert into user_holdings
                cur = conn.execute(
                    "SELECT id, units, invested_amount FROM user_holdings WHERE user_id = ? AND scheme_code = ?",
                    (user["user_id"], scheme_code),
                )
                existing = cur.fetchone()
                if existing:
                    tot_units = existing["units"] + units
                    tot_inv = existing["invested_amount"] + invested
                    new_avg = tot_inv / tot_units if tot_units > 0 else avg_nav
                    conn.execute(
                        "UPDATE user_holdings SET units = ?, avg_nav = ?, invested_amount = ?, updated_at = datetime('now') WHERE id = ?",
                        (tot_units, new_avg, tot_inv, existing["id"]),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO user_holdings (id, user_id, scheme_code, scheme_name, units, avg_nav, invested_amount, category, folio_number)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (uuid.uuid4().hex, user["user_id"], scheme_code, s.scheme_name, units, avg_nav, invested, "Equity", s.folio_number),
                    )
                conn.commit()

                holdings.append({
                    "scheme_name": s.scheme_name,
                    "amfi_code": s.amfi_code,
                    "folio_number": s.folio_number,
                    "units": units,
                    "valuation": val,
                    "transactions_count": len(s.transactions),
                })
        finally:
            conn.close()

        return {
            "message": f"CAS parsed successfully. Imported {len(holdings)} fund holdings.",
            "investor_name": statement.investor_name,
            "statement_period": statement.statement_period,
            "total_valuation": statement.total_valuation,
            "holdings": holdings,
            "note": "PAN was used only in-memory to decrypt the PDF and has been discarded.",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"CAS parsing failed: {str(e)[:200]}. Ensure the file is a valid CAS PDF.",
        )


@router.get("/holdings", summary="Get user portfolio holdings")
def get_holdings(user: dict = Depends(get_current_user)):
    """
    Return the current user's portfolio holdings, automatically updated with live market NAV.
    """
    user_id = user["user_id"]
    conn = _get_portfolio_db()
    try:
        cur = conn.execute(
            "SELECT * FROM user_holdings WHERE user_id = ? ORDER BY invested_amount DESC",
            (user_id,),
        )
        rows = cur.fetchall()
        holdings = []
        for r in rows:
            scheme_code = r["scheme_code"]
            units = float(r["units"])
            avg_nav = float(r["avg_nav"])
            invested = float(r["invested_amount"])

            # Live NAV fetch from MFAPI
            live_nav = None
            try:
                nav_info = data_manager.get_latest_nav(scheme_code)
                if isinstance(nav_info, dict) and nav_info.get("nav"):
                    live_nav = float(nav_info["nav"])
            except Exception:
                pass

            if not live_nav or live_nav <= 0:
                live_nav = avg_nav

            current_val = units * live_nav
            gain_loss = current_val - invested
            gain_pct = (gain_loss / invested * 100.0) if invested > 0 else 0.0

            holdings.append({
                "scheme_code": scheme_code,
                "scheme_name": r["scheme_name"],
                "units": round(units, 4),
                "avg_nav": round(avg_nav, 2),
                "current_nav": round(live_nav, 2),
                "invested": round(invested, 2),
                "current_value": round(current_val, 2),
                "gain_loss": round(gain_loss, 2),
                "gain_loss_pct": round(gain_pct, 2),
                "xirr": round(gain_pct, 2),
                "investment_type": r["investment_type"] or "LUMPSUM",
                "investment_date": r["investment_date"] or "",
                "category": r["category"] or "Equity",
                "dud_severity": "CLEAN",
            })

        total_inv = sum(h["invested"] for h in holdings)
        total_val = sum(h["current_value"] for h in holdings)
        return {
            "user_id": user_id,
            "holdings": holdings,
            "count": len(holdings),
            "total_invested": round(total_inv, 2),
            "total_value": round(total_val, 2),
            "total_gain": round(total_val - total_inv, 2),
        }
    finally:
        conn.close()


@router.post("/holdings", summary="Add or accumulate a holding")
def add_holding(holding: HoldingInput, user: dict = Depends(get_current_user)):
    """
    Add a new mutual fund or automatically accumulate into an existing fund holding.
    Calculates units and gains automatically from historical NAV, today's value, or units.
    """
    user_id = user["user_id"]
    scheme_code = holding.scheme_code

    # 1. Fetch latest NAV for fallback
    latest_nav = 10.0
    try:
        latest_info = data_manager.get_latest_nav(scheme_code)
        if isinstance(latest_info, dict) and latest_info.get("nav"):
            latest_nav = float(latest_info["nav"])
    except Exception:
        pass

    # 2. Determine units and avg_nav
    invested = float(holding.invested_amount or 0)
    units = float(holding.units or 0)
    avg_nav = float(holding.avg_nav or 0)
    current_val = float(holding.current_value or 0)

    if invested > 0:
        if units > 0:
            avg_nav = invested / units
        elif avg_nav > 0:
            units = invested / avg_nav
        elif current_val > 0:
            units = current_val / latest_nav
            avg_nav = invested / units if units > 0 else latest_nav
        elif holding.investment_date:
            hist_nav = _resolve_historical_nav(scheme_code, holding.investment_date)
            avg_nav = hist_nav if (hist_nav and hist_nav > 0) else latest_nav
            units = invested / avg_nav
        else:
            avg_nav = latest_nav
            units = invested / avg_nav
    elif units > 0 and avg_nav > 0:
        invested = units * avg_nav
    elif current_val > 0:
        units = current_val / latest_nav
        avg_nav = latest_nav
        invested = current_val
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide an invested amount or number of units.",
        )

    if units <= 0 or invested <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invested amount and units must be greater than zero.",
        )

    conn = _get_portfolio_db()
    try:
        cur = conn.execute(
            "SELECT id, units, avg_nav, invested_amount FROM user_holdings WHERE user_id = ? AND scheme_code = ?",
            (user_id, scheme_code),
        )
        existing = cur.fetchone()
        if existing:
            # Automatic Accumulation into existing fund holding
            old_units = float(existing["units"])
            old_invested = float(existing["invested_amount"])
            tot_units = old_units + units
            tot_invested = old_invested + invested
            new_avg = tot_invested / tot_units if tot_units > 0 else avg_nav

            conn.execute(
                """
                UPDATE user_holdings
                SET units = ?, avg_nav = ?, invested_amount = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                (tot_units, new_avg, tot_invested, existing["id"]),
            )
            conn.commit()
            action = "accumulated"
            final_units = tot_units
            final_invested = tot_invested
            final_avg = new_avg
        else:
            # Brand new holding
            conn.execute(
                """
                INSERT INTO user_holdings (
                    id, user_id, scheme_code, scheme_name, units, avg_nav, invested_amount,
                    category, folio_number, investment_type, investment_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex, user_id, scheme_code, holding.scheme_name,
                    units, avg_nav, invested, holding.category,
                    holding.folio_number, holding.investment_type, holding.investment_date
                ),
            )
            conn.commit()
            action = "created"
            final_units = units
            final_invested = invested
            final_avg = avg_nav

        new_current_val = final_units * latest_nav
        return {
            "success": True,
            "action": action,
            "message": f"Fund {action} successfully.",
            "holding": {
                "scheme_code": scheme_code,
                "scheme_name": holding.scheme_name,
                "units": round(final_units, 4),
                "avg_nav": round(final_avg, 2),
                "invested": round(final_invested, 2),
                "current_nav": round(latest_nav, 2),
                "current_value": round(new_current_val, 2),
                "gain_loss": round(new_current_val - final_invested, 2),
            },
        }
    finally:
        conn.close()


@router.delete("/holdings/{scheme_code}", summary="Delete a fund holding from portfolio")
def delete_holding(scheme_code: int, user: dict = Depends(get_current_user)):
    """
    Remove a mutual fund holding from the user's portfolio.
    """
    user_id = user["user_id"]
    conn = _get_portfolio_db()
    try:
        cur = conn.execute(
            "DELETE FROM user_holdings WHERE user_id = ? AND scheme_code = ?",
            (user_id, scheme_code),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found.")
        return {"success": True, "message": f"Fund {scheme_code} removed from portfolio."}
    finally:
        conn.close()


@router.post("/xray", summary="Portfolio sector and thematic X-Ray")
def portfolio_xray(
    holdings: list[HoldingInput],
    user: dict = Depends(get_current_user),
):
    """
    Run a full Portfolio X-Ray:
    - Sector concentration heatmap
    - Thematic clusters (Financials, Tech, Healthcare, etc.)
    - Fund-to-fund overlap score
    - Market cap distribution (Large / Mid / Small)
    - Diversification score
    """
    from src.analytics.portfolio_xray import FundHolding, run_portfolio_xray

    fund_holdings = [
        FundHolding(
            scheme_code=h.scheme_code,
            scheme_name=h.scheme_name,
            current_value=(h.units * (h.current_nav or h.avg_nav)),
            category=h.category,
        )
        for h in holdings
    ]
    result = run_portfolio_xray(fund_holdings)
    return {
        "total_portfolio_value": result.total_portfolio_value,
        "diversification_score": result.diversification_score,
        "sector_exposure": result.sector_exposure,
        "market_cap_exposure": result.market_cap_exposure,
        "category_distribution": result.category_distribution,
        "overlap_matrix": result.overlap_matrix,
        "concentration_alerts": result.concentration_alerts,
        "thematic_clusters": result.thematic_clusters,
        "summary": result.summary,
    }

