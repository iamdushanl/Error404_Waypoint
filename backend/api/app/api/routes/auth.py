"""
Waypoint Backend — auth routes.

GET /api/v1/auth/me
    Returns the authenticated user's profile and application role.
    Used by the frontend immediately after sign-in to:
      1. Confirm the session is valid.
      2. Determine which role-based UI to show.
      3. Get user details (name, outlet, depot, vehicle).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class UserMeResponse(BaseModel):
    """Response shape for GET /auth/me."""
    id: str
    email: str
    full_name: str
    role: str               # dispatcher | loader | driver | store_manager
    outlet_id: str | None   # store_manager only
    depot: str | None       # loader / driver
    vehicle_id: str | None  # driver only


@router.get(
    "/me",
    response_model=UserMeResponse,
    summary="Get current user",
    description=(
        "Returns the authenticated user's profile and application role. "
        "The frontend calls this after sign-in to determine which UI to show.\n\n"
        "**Requires:** Valid Supabase JWT in `Authorization: Bearer <token>` header."
    ),
)
async def get_me(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> UserMeResponse:
    """Return the current user's profile."""
    return UserMeResponse(
        id=current_user["id"],
        email=current_user["email"],
        full_name=current_user["full_name"],
        role=current_user["role"],
        outlet_id=current_user.get("outlet_id"),
        depot=current_user.get("depot"),
        vehicle_id=current_user.get("vehicle_id"),
    )
