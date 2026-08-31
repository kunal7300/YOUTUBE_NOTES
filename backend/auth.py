"""
auth.py — JWT authentication using Supabase Auth client.
Uses Supabase's own get_user() to verify tokens — no manual JWT decoding needed.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from db import get_supabase

_bearer = HTTPBearer()
_bearer_optional = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """
    Verify Supabase JWT by calling get_user() on the Supabase Auth API.
    Returns dict with user_id, email, and token. Raises 401 on failure.
    """
    token = credentials.credentials
    try:
        sb = get_supabase()
        response = sb.auth.get_user(token)
        user = response.user
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token. Please log in again.",
            )
        return {"user_id": str(user.id), "email": user.email or "", "token": token}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
        )


def optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_optional),
) -> dict | None:
    """
    Optional auth — returns user dict if valid token, else None.
    """
    if not credentials:
        return None
    try:
        return get_current_user(credentials)
    except HTTPException:
        return None
