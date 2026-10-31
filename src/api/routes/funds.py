"""
src/api/routes/funds.py
━━━━━━━━━━━━━━━━━━━━━━━
Fund data routes: search, NAV history, scheme metadata, AMFI cross-verify.
"""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status

from src.data.data_manager import data_manager
from src.data.storage import get_nav_history_df

router = APIRouter()


@router.get("/search", summary="Search mutual funds by name")
def search_funds(q: str = Query(..., min_length=2, description="Fund name or keyword")):
    """
    Search all Indian mutual funds by name.
    Uses MFAPI fast-search endpoint.
    """
    results = data_manager.search(q)
    return {"query": q, "results": results, "count": len(results)}


@router.get("/{scheme_code}", summary="Get scheme metadata")
def get_scheme(scheme_code: int):
    """Get metadata for a specific fund scheme code."""
    meta = data_manager.get_scheme_metadata(scheme_code)
    if not meta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheme not found.")
    return meta


@router.get("/{scheme_code}/nav", summary="Get NAV history")
def get_nav_history(
    scheme_code: int,
    years: Optional[float] = Query(None, description="Limit to last N years (e.g., 3.0)"),
):
    """
    Fetch full historical NAV series from local SQLite cache.
    Falls back to live fetch if not cached.
    """
    df = get_nav_history_df(scheme_code)
    if df.empty:
        # Try live fetch
        nav_data = data_manager.get_nav_history(scheme_code)
        if not nav_data or not nav_data.get("data"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NAV data not available.")
        return {"scheme_code": scheme_code, "nav_records": nav_data["data"][:50], "total": len(nav_data["data"])}

    if years:
        import pandas as pd
        cutoff = df.index[-1] - pd.DateOffset(years=years)
        df = df[df.index >= cutoff]

    records = [
        {"date": idx.strftime("%Y-%m-%d"), "nav": row["nav"]}
        for idx, row in df.iterrows()
    ]
    return {
        "scheme_code": scheme_code,
        "total_records": len(records),
        "from_date": records[0]["date"] if records else None,
        "to_date": records[-1]["date"] if records else None,
        "nav_history": records,
    }


@router.get("/{scheme_code}/latest-nav", summary="Get latest NAV")
def get_latest_nav(scheme_code: int):
    """Get the most recent NAV for a fund."""
    nav = data_manager.get_latest_nav(scheme_code)
    if nav is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NAV not found.")
    return {"scheme_code": scheme_code, "latest_nav": nav}
    return {"scheme_code": scheme_code, "latest_nav": nav}

