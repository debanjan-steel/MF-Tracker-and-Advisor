"""
src/api/routes/user.py
━━━━━━━━━━━━━━━━━━━━━━
User state, universal cloud sync, and schema auto-migration endpoints.

Endpoints:
  GET  /user/state             — Fetches complete migrated state (holdings, watchlist, plans, goals, preferences)
  POST /user/sync              — Pushes/restores client-side snapshot to both local DB and Supabase Cloud
  GET  /user/watchlist         — Fetches user watchlist from cloud
  POST /user/watchlist         — Saves & synchronizes user watchlist to cloud
  GET  /user/alert-preferences — Fetches alert preferences
  POST /user/alert-preferences — Updates alert preferences
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.auth.supabase_client import get_current_user
from src.data.cloud_sync import (
    get_universal_user_state,
    restore_and_sync_universal_state,
    get_user_watchlist_from_cloud,
    save_user_watchlist_to_cloud,
    ensure_user_alert_preferences_hydrated,
    save_user_alert_preferences_to_cloud,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class SyncStateRequest(BaseModel):
    holdings: Optional[List[Dict[str, Any]]] = None
    watchlist: Optional[List[Any]] = None
    saved_goals: Optional[List[Dict[str, Any]]] = None
    saved_investment_plan: Optional[Dict[str, Any]] = None
    alert_preferences: Optional[Dict[str, Any]] = None


class WatchlistRequest(BaseModel):
    watchlist: List[Any]


class AlertPreferencesRequest(BaseModel):
    entry_alert: Optional[bool] = True
    macro_alert: Optional[bool] = True
    sip_reminder: Optional[bool] = True
    dud_alert: Optional[bool] = True


@router.get("/state", summary="Retrieve universal migrated user state")
def get_user_state(user: dict = Depends(get_current_user)):
    """
    Returns complete migrated state (holdings, watchlist, plans, goals, preferences)
    guaranteed to match the latest schema version.
    """
    try:
        user_id = user["user_id"]
        return get_universal_user_state(user_id)
    except Exception as e:
        logger.error("[UserState] Error getting state: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user state: {str(e)}",
        )


@router.post("/sync", summary="Synchronize & migrate universal user state")
def sync_user_state(body: SyncStateRequest, user: dict = Depends(get_current_user)):
    """
    Accepts client-side state snapshot, transforms all legacy formats to latest schema,
    and persists across SQLite and Supabase Cloud.
    """
    try:
        user_id = user["user_id"]
        state_dict = body.model_dump(exclude_unset=True)
        result = restore_and_sync_universal_state(user_id, state_dict)
        return result
    except Exception as e:
        logger.error("[UserState] Error syncing state: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync user state: {str(e)}",
        )


@router.get("/watchlist", summary="Get user watchlist from cloud")
def get_watchlist(user: dict = Depends(get_current_user)):
    """Fetch user's watchlist from cloud with auto-migration."""
    try:
        user_id = user["user_id"]
        watchlist = get_user_watchlist_from_cloud(user_id)
        return {"watchlist": watchlist}
    except Exception as e:
        logger.error("[UserState] Error getting watchlist: %s", e)
        return {"watchlist": []}


@router.post("/watchlist", summary="Save user watchlist to cloud")
def save_watchlist(body: WatchlistRequest, user: dict = Depends(get_current_user)):
    """Persist and sync user watchlist to cloud."""
    try:
        user_id = user["user_id"]
        success = save_user_watchlist_to_cloud(user_id, body.watchlist)
        return {"success": success, "watchlist": get_user_watchlist_from_cloud(user_id)}
    except Exception as e:
        logger.error("[UserState] Error saving watchlist: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save watchlist: {str(e)}",
        )


@router.get("/alert-preferences", summary="Get user alert preferences")
def get_alert_preferences(user: dict = Depends(get_current_user)):
    """Fetch user alert preferences."""
    try:
        user_id = user["user_id"]
        prefs = ensure_user_alert_preferences_hydrated(user_id)
        return {"preferences": prefs}
    except Exception as e:
        logger.error("[UserState] Error getting alert preferences: %s", e)
        return {"preferences": {}}


@router.post("/alert-preferences", summary="Save user alert preferences")
def save_alert_preferences(body: AlertPreferencesRequest, user: dict = Depends(get_current_user)):
    """Save alert preferences to cloud and local DB."""
    try:
        user_id = user["user_id"]
        prefs_dict = body.model_dump()
        success = save_user_alert_preferences_to_cloud(user_id, prefs_dict)
        return {"success": success, "preferences": prefs_dict}
    except Exception as e:
        logger.error("[UserState] Error saving alert preferences: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save alert preferences: {str(e)}",
        )
