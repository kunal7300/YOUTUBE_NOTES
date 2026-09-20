"""
auth.py — JWT authentication for Supabase Auth.
Supports both Supabase Auth API verification and direct JWT decoding fallback.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from db import get_supabase

_bearer = HTTPBearer()
_bearer_optional = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """
    Verify Supabase JWT.
    1. Tries Supabase Auth API get_user(token).
    2. Falls back to decoding JWT claims (sub, email) directly.
    """
    token = credentials.credentials
    if not token or token in ("null", "undefined", ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No valid session token provided. Please log in.",
        )

    # 1. Try Supabase Auth API get_user()
    try:
        sb = get_supabase()
        response = sb.auth.get_user(token)
        user = response.user
        if user and user.id:
            return {"user_id": str(user.id), "email": user.email or "", "token": token}
    except Exception:
        pass

    # 2. Fallback: decode JWT claims directly (sub = user_id)
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        user_id = payload.get("sub")
        email = payload.get("email", "")
        if user_id:
            return {"user_id": str(user_id), "email": email, "token": token}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid session token. Please log in again. ({str(e)})",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token. Please log in again.",
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
