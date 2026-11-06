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
    raw_results = data_manager.search(q)
    results = []
    for r in raw_results:
        code = r.get("schemeCode") or r.get("scheme_code")
        name = r.get("schemeName") or r.get("scheme_name")
        results.append({
            "scheme_code": code,
            "schemeCode": code,
            "scheme_name": name,
            "schemeName": name,
            "fund_house": r.get("fund_house", ""),
            "scheme_category": r.get("scheme_category", ""),
        })
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
    Falls back to live fetch if not cached and caches it.
    """
    df = get_nav_history_df(scheme_code)
    if df.empty:
        # Try live fetch
        nav_data = data_manager.get_nav_history(scheme_code)
        if not nav_data or not nav_data.get("data"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NAV data not available.")
        try:
            from src.data.storage import upsert_schemes, bulk_insert_nav_history
            meta = nav_data.get("meta", {})
            upsert_schemes([{
                "scheme_code": scheme_code,
                "scheme_name": meta.get("scheme_name", f"Scheme {scheme_code}"),
                "fund_house": meta.get("fund_house", ""),
                "scheme_type": meta.get("scheme_type", ""),
                "scheme_category": meta.get("scheme_category", ""),
            }])
            bulk_insert_nav_history(scheme_code, nav_data["data"])
            df = get_nav_history_df(scheme_code)
        except Exception:
            pass

    if df.empty and nav_data and nav_data.get("data"):
        raw_list = sorted(nav_data["data"], key=lambda x: x["date"])
        return {
            "scheme_code": scheme_code,
            "total_records": len(raw_list),
            "from_date": raw_list[0]["date"] if raw_list else None,
            "to_date": raw_list[-1]["date"] if raw_list else None,
            "nav_history": raw_list,
        }

    if df.empty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NAV data not available.")

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
    nav_info = data_manager.get_latest_nav(scheme_code)
    if nav_info is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NAV not found.")
    
    nav_val = nav_info.get("nav") if isinstance(nav_info, dict) else nav_info
    date_val = nav_info.get("date") if isinstance(nav_info, dict) else ""
    return {
        "scheme_code": scheme_code,
        "nav": nav_val,
        "latest_nav": nav_val,
        "date": date_val,
    }


@router.get("/{scheme_code}/nav-on-date", summary="Get historical NAV on or before a specific date")
def get_nav_on_date(
    scheme_code: int,
    date: str = Query(..., description="Target date in YYYY-MM-DD format"),
):
    """
    Find the historical NAV of a fund on or immediately before a given date.
    Useful for calculating units and growth for historical investments.
    """
    clean_date = date.strip()
    try:
        nav_data = data_manager.get_nav_history(scheme_code)
        history = nav_data.get("data", [])
        if not history:
            raise HTTPException(status_code=404, detail="No historical NAV available.")

        matched = None
        for r in history:
            if r.get("date") <= clean_date:
                matched = r
                break

        if not matched:
            matched = history[-1]

        latest_val = float(history[0]["nav"]) if history else float(matched["nav"])
        matched_nav = float(matched["nav"])

        return {
            "scheme_code": scheme_code,
            "requested_date": clean_date,
            "matched_date": matched["date"],
            "nav": matched_nav,
            "latest_nav": latest_val,
            "latest_date": history[0]["date"] if history else matched["date"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch NAV for date {clean_date}: {str(e)}")

