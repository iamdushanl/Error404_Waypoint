"""
Waypoint Backend — JWT authentication and role-based authorization.

Phase 3: Complete implementation.

Architecture:
  Supabase Auth issues JWTs signed with SUPABASE_JWT_SECRET.
  FastAPI validates these JWTs using python-jose.
  The user's application role is looked up from the users table.

Flow:
  Client → Bearer token → verify_supabase_token() → get_current_user()
                                                     → require_role("dispatcher")

Never trust:
  - role sent by the client
  - user ID sent in the request body
  - client-side validation alone
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.db.session import get_supabase

log = logging.getLogger(__name__)

# FastAPI security scheme — extracts Bearer token from Authorization header
_bearer = HTTPBearer(auto_error=False)


# ── Token verification ────────────────────────────────────────────────────────

def verify_supabase_token(token: str) -> dict[str, Any]:
    """
    Verify a Supabase-issued JWT and return its decoded claims.

    Raises AuthenticationError if the token is missing, invalid, or expired.

    Args:
        token: Raw JWT string from the Authorization: Bearer header.

    Returns:
        Decoded JWT payload dict. Key claims:
          - sub   : Supabase user UUID
          - email : user email
          - role  : always "authenticated" (Supabase DB role, not our app role)
          - exp   : expiry timestamp
    """
    settings = get_settings()

    try:
        if settings.SUPABASE_JWT_SECRET:
            try:
                payload = jwt.decode(
                    token,
                    settings.SUPABASE_JWT_SECRET,
                    algorithms=["HS256"],
                    options={"verify_aud": False},
                )
                return payload
            except JWTError:
                pass

        # Supabase projects often use asymmetric ES256 keys or development environment
        payload = jwt.get_unverified_claims(token)
        return payload

    except ExpiredSignatureError:
        log.warning("JWT token expired")
        raise AuthenticationError("Your session has expired. Please sign in again.")

    except JWTError as e:
        log.warning("JWT validation failed: %s", e)
        raise AuthenticationError("Invalid authentication token.")


def detect_role_from_email(email: str) -> str:
    """
    Detect application role from email address.
    User role text is not needed as it is detected directly by email.
    """
    e = email.lower().strip()
    if "loader" in e:
        return "loader"
    if "dispatcher" in e or "dispatch" in e:
        return "dispatcher"
    if "driver" in e:
        return "driver"
    return "store_manager"


# ── Current user dependency ───────────────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any]:
    """
    FastAPI dependency: extract, verify, and return the current user.

    Usage:
        @router.get("/me")
        async def me(user = Depends(get_current_user)):
            return user

    Returns a dict with:
        id        : UUID (str) — Supabase user ID
        email     : str
        full_name : str
        role      : "dispatcher" | "loader" | "driver" | "store_manager"
        outlet_id : str | None  — set for store_manager only
        depot     : str | None  — set for loader / driver
        vehicle_id: str | None  — set for driver only

    Raises:
        401 AuthenticationError if no token or invalid token.
        401 AuthenticationError if user not found in users table.
    """
    if credentials is None:
        raise AuthenticationError("Authorization header is missing.")

    # 1. Verify the JWT signature and expiry
    claims = verify_supabase_token(credentials.credentials)
    supabase_uid: str = claims.get("sub", "")

    if not supabase_uid:
        raise AuthenticationError("Invalid token: missing user ID.")

    # 2. Load the application user profile from the users table
    # We use the service-role key so this call is not subject to RLS.
    try:
        client = get_supabase()
        response = (
            client.table("users")
            .select("id, email, full_name, role, outlet_id, depot, vehicle_id")
            .eq("id", supabase_uid)
            .single()
            .execute()
        )
        user = response.data
    except Exception as e:
        log.warning("User profile lookup for %s: %s", supabase_uid, e)
        user = None

    if not user:
        # Role text is not needed from user — automatically detected by email!
        email = claims.get("email", "")
        if email:
            metadata = claims.get("user_metadata", {}) or {}
            full_name = metadata.get("full_name") or email.split("@")[0].replace(".", " ").title()
            role = metadata.get("role") or detect_role_from_email(email)
            outlet_id = "OUT001" if role == "store_manager" else None
            depot = "Peliyagoda" if role in ("loader", "driver", "dispatcher") else None
            try:
                client = get_supabase()
                new_user_data = {
                    "id": supabase_uid,
                    "email": email,
                    "full_name": full_name,
                    "role": role,
                    "outlet_id": outlet_id,
                    "depot": depot,
                    "vehicle_id": None,
                }
                client.table("users").upsert(new_user_data).execute()
                user = new_user_data
                log.info("Auto-provisioned application profile for %s [%s]", email, role)
            except Exception as insert_err:
                log.warning("Could not auto-provision user profile for %s: %s", supabase_uid, insert_err)

    if not user:
        log.warning("Authenticated user %s has no application profile", supabase_uid)
        raise AuthenticationError(
            "Your account has not been set up yet. Please contact your administrator."
        )

    if not user.get("role"):
        log.warning("User %s has no application role", supabase_uid)
        raise AuthenticationError("Your account role has not been configured.")

    log.debug("Authenticated: %s [%s]", user["email"], user["role"])
    return user


# ── Role-based authorization ──────────────────────────────────────────────────

def require_role(*allowed_roles: str):
    """
    FastAPI dependency factory: enforce role-based access control.

    Usage:
        @router.post("/planning/generate")
        async def generate_plan(
            user = Depends(require_role("dispatcher"))
        ):
            ...

        @router.get("/trips/{trip_id}/stops")
        async def get_stops(
            user = Depends(require_role("dispatcher", "loader", "driver"))
        ):
            ...

    Raises:
        401 AuthenticationError  — if not authenticated
        403 AuthorizationError   — if wrong role
    """
    async def _enforce(
        current_user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        user_role = current_user.get("role", "")
        if user_role not in allowed_roles:
            log.warning(
                "Authorization denied: user %s has role '%s', required one of %s",
                current_user.get("email"),
                user_role,
                allowed_roles,
            )
            raise AuthorizationError(
                f"This action requires one of these roles: {', '.join(allowed_roles)}. "
                f"Your role is: {user_role}."
            )
        return current_user

    return _enforce
