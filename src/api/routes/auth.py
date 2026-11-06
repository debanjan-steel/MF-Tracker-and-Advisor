"""
src/api/routes/auth.py
━━━━━━━━━━━━━━━━━━━━━━
Authentication routes: signup, login, logout, delete account.
"""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr

from src.auth.supabase_client import (
    sign_up,
    sign_in,
    sign_out,
    delete_account,
    get_current_user,
    request_password_reset,
    change_password,
)

router = APIRouter()


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str


class SignInRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.post("/signup", summary="Create a new account")
def signup(body: SignUpRequest):
    """Register with email + password. No PAN or phone required."""
    return sign_up(body.email, body.password)


@router.post("/login", summary="Log in")
def login(body: SignInRequest):
    """Authenticate and receive a JWT access token."""
    return sign_in(body.email, body.password)


@router.post("/logout", summary="Log out")
def logout(user: dict = Depends(get_current_user)):
    """Invalidate the current session."""
    sign_out("")  # Supabase client-side signout
    return {"message": "Logged out successfully."}


@router.delete(
    "/delete-account",
    summary="Permanently delete account",
    description=(
        "INSTANT hard delete. No confirmation email. No recovery period. "
        "All your data is removed immediately from our servers. "
        "You will need to create a new account if you want to use the app again."
    ),
)
def delete_my_account(
    user: dict = Depends(get_current_user),
):
    """One-tap instant account deletion."""
    return delete_account("", user_id=user["user_id"])


@router.post("/forgot-password", summary="Send password reset instructions")
def forgot_password_route(body: ForgotPasswordRequest):
    """Send password reset instructions to the given email address."""
    return request_password_reset(body.email)


@router.post("/change-password", summary="Change account password")
def change_password_route(body: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    """Change current password after verifying old password."""
    return change_password(user, body.old_password, body.new_password)



@router.delete("/delete-account/confirm", summary="Confirm and execute account deletion")
def delete_account_confirm(
    body: Optional[dict] = None,
    user: dict = Depends(get_current_user),
):
    """
    Final account deletion step.
    Permanently deletes all user data and credentials.
    """
    return delete_account("", user_id=user["user_id"])


