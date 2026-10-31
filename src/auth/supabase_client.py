"""
src/auth/supabase_client.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Supabase Auth integration.

Handles:
  - Email/password login & signup
  - JWT token validation (for API route protection)
  - Account deletion (instant hard delete — no confirmation required)
  - Session refresh

User rule: PAN number NEVER stored. Only used in-memory transiently.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# Lazy import — supabase only imported when client is created
_supabase = None


def _get_supabase():
    """Lazily create the Supabase client (avoids import at module load)."""
    global _supabase
    if _supabase is None:
        try:
            from supabase import create_client
            url = os.getenv("SUPABASE_URL", "")
            key = os.getenv("SUPABASE_ANON_KEY", "")
            if not url or not key:
                raise ValueError(
                    "SUPABASE_URL and SUPABASE_ANON_KEY must be set in .env"
                )
            _supabase = create_client(url, key)
        except ImportError:
            raise RuntimeError(
                "supabase package not installed. Run: pip install supabase"
            )
    return _supabase


# ─────────────────────────────────────────────────────────────────────────────
# Auth Operations
# ─────────────────────────────────────────────────────────────────────────────

def sign_up(email: str, password: str) -> dict:
    """
    Register a new user with email + password.

    Returns Supabase Auth response (contains user object + session).
    Raises HTTPException on failure.
    """
    client = _get_supabase()
    try:
        response = client.auth.sign_up({"email": email, "password": password})
        if response.user is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Signup failed. Check email/password requirements.",
            )
        return {
            "user_id": str(response.user.id),
            "email": response.user.email,
            "message": "Account created. Check email for verification (if enabled).",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Signup error: {str(e)}",
        )


def sign_in(email: str, password: str) -> dict:
    """
    Login with email + password.

    Returns access_token, refresh_token, user_id.
    """
    client = _get_supabase()
    try:
        response = client.auth.sign_in_with_password({"email": email, "password": password})
        if response.session is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )
        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "token_type": "bearer",
            "user_id": str(response.user.id),
            "email": response.user.email,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Login error: {str(e)}",
        )


def sign_out(access_token: str) -> None:
    """Sign out (invalidate current session)."""
    client = _get_supabase()
    try:
        client.auth.sign_out()
    except Exception:
        pass  # Best effort — client-side token can be discarded anyway


def delete_account(access_token: str) -> dict:
    """
    INSTANT hard delete of user account.
    No confirmation email. No recovery period. Immediate.

    Implementation:
      1. Verify the token is valid (get user ID).
      2. Call Supabase Admin API to delete user by ID.
      3. Return success.

    Requires SUPABASE_SERVICE_ROLE_KEY (admin key) in .env.
    """
    # First verify the token and get user ID
    client = _get_supabase()
    try:
        user_response = client.auth.get_user(access_token)
        if user_response.user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token. Please log in again.",
            )
        user_id = str(user_response.user.id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {str(e)}",
        )

    # Admin delete using service role key
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    supabase_url = os.getenv("SUPABASE_URL", "")

    if not service_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error: service key not set.",
        )

    try:
        from supabase import create_client
        admin_client = create_client(supabase_url, service_key)
        admin_client.auth.admin.delete_user(user_id)
        return {
            "message": "Account permanently deleted. All your data has been removed.",
            "user_id": user_id,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Account deletion failed: {str(e)}",
        )


def validate_token(token: str) -> dict:
    """
    Validate a JWT access token and return the user payload.

    Returns dict with user_id, email.
    Raises HTTPException 401 if invalid/expired.
    """
    client = _get_supabase()
    try:
        user_response = client.auth.get_user(token)
        if user_response.user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is invalid or expired. Please log in again.",
            )
        return {
            "user_id": str(user_response.user.id),
            "email": user_response.user.email,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed.",
        )


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI Dependency — Current User
# ─────────────────────────────────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    """
    FastAPI dependency that extracts and validates the Bearer token.

    Usage:
        @router.get("/protected")
        def my_endpoint(user: dict = Depends(get_current_user)):
            return {"user_id": user["user_id"]}
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return validate_token(credentials.credentials)

