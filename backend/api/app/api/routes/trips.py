"""
Trips routes — route execution for loader and driver.

Role access:
  dispatcher : read all trips
  loader     : read trips at their depot, acknowledge loading
  driver     : read their own vehicle's trips, update status, mark departed

Endpoints:
  GET    /api/v1/trips                       ← list (role-filtered)
  GET    /api/v1/trips/{id}                  ← detail with stops
  GET    /api/v1/trips/{id}/stops            ← ordered stop list
  PATCH  /api/v1/trips/{id}/acknowledge      ← loader/driver acknowledge
  PATCH  /api/v1/trips/{id}/depart           ← driver marks vehicle departed
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user, require_role
from app.db.session import get_supabase
from app.repositories.trip_repository import TripRepository
from app.schemas.common import PagedResponse
from app.schemas.trip import (
    TripAcknowledge,
    TripResponse,
    TripStopResponse,
    TripWithStopsResponse,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/trips", tags=["trips"])


def _get_repo() -> TripRepository:
    return TripRepository(get_supabase())


# ── GET /api/v1/trips ─────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=PagedResponse[TripResponse],
    summary="List trips",
    description=(
        "Returns trips filtered by role:\n"
        "- **dispatcher**: all trips, supports plan_id / depot filters\n"
        "- **loader**: trips at their depot only\n"
        "- **driver**: trips assigned to their vehicle only"
    ),
)
async def list_trips(
    plan_id: str | None = Query(None),
    depot: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    brand: str | None = Query(None),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: dict[str, Any] = Depends(get_current_user),
    repo: TripRepository = Depends(_get_repo),
) -> PagedResponse[TripResponse]:
    role = current_user["role"]

    # Scope filters by role
    effective_depot = depot
    effective_vehicle = None

    if role == "loader":
        effective_depot = current_user.get("depot")  # always scoped to own depot
    elif role == "driver":
        effective_vehicle = current_user.get("vehicle_id")

    rows, total = repo.list(
        plan_id=plan_id,
        vehicle_id=effective_vehicle,
        depot=effective_depot,
        status=status_filter,
        brand=brand,
        limit=limit,
        offset=offset,
    )
    return PagedResponse(
        data=[TripResponse(**r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


# ── GET /api/v1/trips/{id} ────────────────────────────────────────────────────

@router.get(
    "/{trip_id}",
    response_model=TripWithStopsResponse,
    summary="Get trip with stops",
    description="Returns a single trip with all its stops in delivery sequence order.",
)
async def get_trip(
    trip_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    repo: TripRepository = Depends(_get_repo),
) -> TripWithStopsResponse:
    trip = repo.get_with_stops(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail=f"Trip '{trip_id}' not found.")

    # Scope check for loader/driver
    role = current_user["role"]
    if role == "loader" and trip["depot"] != current_user.get("depot"):
        raise HTTPException(status_code=404, detail="Trip not found.")
    if role == "driver" and trip["vehicle_id"] != current_user.get("vehicle_id"):
        raise HTTPException(status_code=404, detail="Trip not found.")

    return TripWithStopsResponse(**trip)


# ── GET /api/v1/trips/{id}/stops ──────────────────────────────────────────────

@router.get(
    "/{trip_id}/stops",
    response_model=list[TripStopResponse],
    summary="List trip stops",
    description="Returns all stops for a trip ordered by sequence_number (delivery order).",
)
async def get_trip_stops(
    trip_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    repo: TripRepository = Depends(_get_repo),
) -> list[TripStopResponse]:
    trip = repo.get(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found.")

    # Scope check
    role = current_user["role"]
    if role == "loader" and trip["depot"] != current_user.get("depot"):
        raise HTTPException(status_code=404, detail="Trip not found.")
    if role == "driver" and trip["vehicle_id"] != current_user.get("vehicle_id"):
        raise HTTPException(status_code=404, detail="Trip not found.")

    stops = repo.get_stops(trip_id)
    return [TripStopResponse(**s) for s in stops]


# ── PATCH /api/v1/trips/{id}/acknowledge ─────────────────────────────────────

@router.patch(
    "/{trip_id}/acknowledge",
    response_model=TripResponse,
    summary="Acknowledge trip",
    description=(
        "Loader or driver acknowledges they have reviewed the trip manifest.\n\n"
        "- **Loader** acknowledge: confirms load list reviewed before loading.\n"
        "- **Driver** acknowledge: confirms route reviewed before departure.\n\n"
        "**Loader or Driver only.**"
    ),
)
async def acknowledge_trip(
    trip_id: str,
    body: TripAcknowledge,
    current_user: dict[str, Any] = Depends(require_role("loader", "driver")),
    repo: TripRepository = Depends(_get_repo),
) -> TripResponse:
    role = current_user["role"]

    # Validate role matches body
    if body.role != role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role mismatch: you are '{role}' but body says '{body.role}'.",
        )

    trip = repo.get(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found.")

    # Scope check
    if role == "loader" and trip["depot"] != current_user.get("depot"):
        raise HTTPException(status_code=404, detail="Trip not found.")
    if role == "driver" and trip["vehicle_id"] != current_user.get("vehicle_id"):
        raise HTTPException(status_code=404, detail="Trip not found.")

    updated = repo.acknowledge(trip_id, role=role)
    log.info("Trip %s acknowledged by %s (%s)", trip_id, current_user["email"], role)
    return TripResponse(**updated)


# ── PATCH /api/v1/trips/{id}/depart ──────────────────────────────────────────

@router.patch(
    "/{trip_id}/depart",
    response_model=TripResponse,
    summary="Mark trip departed",
    description=(
        "Driver marks the vehicle as departed from the depot. "
        "Trip must be in 'loading' or 'planned' status and driver must have acknowledged. "
        "**Driver only.**"
    ),
)
async def depart_trip(
    trip_id: str,
    current_user: dict[str, Any] = Depends(require_role("driver")),
    repo: TripRepository = Depends(_get_repo),
) -> TripResponse:
    import datetime

    trip = repo.get(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found.")

    if trip["vehicle_id"] != current_user.get("vehicle_id"):
        raise HTTPException(status_code=404, detail="Trip not found.")

    if trip["status"] not in ("planned", "loading"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot depart: trip is '{trip['status']}'.",
        )

    if not trip.get("driver_acknowledged"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Driver must acknowledge the trip before departing.",
        )

    updated = repo.update_status(
        trip_id,
        "departed",
        extra={"departed_at": datetime.datetime.utcnow().isoformat()},
    )
    log.info("Trip %s departed by driver %s", trip_id, current_user["email"])
    return TripResponse(**updated)


# ── PATCH /api/v1/trips/{id}/complete ──────────────────────────────────────────

@router.patch(
    "/{trip_id}/complete",
    response_model=TripResponse,
    summary="Mark trip completed",
    description=(
        "Driver marks the trip as completed after returning to the depot.\n\n"
        "Requirements:\n"
        "- Trip must be in **'in_transit'** or **'departed'** status.\n"
        "- All stops should have a delivery record (warning only, not enforced).\n\n"
        "**Driver only.**"
    ),
)
async def complete_trip(
    trip_id: str,
    current_user: dict[str, Any] = Depends(require_role("driver")),
    repo: TripRepository = Depends(_get_repo),
) -> TripResponse:
    import datetime

    trip = repo.get(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found.")

    if trip["vehicle_id"] != current_user.get("vehicle_id"):
        raise HTTPException(status_code=404, detail="Trip not found.")

    if trip["status"] not in ("departed", "in_transit"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot complete: trip is '{trip['status']}'. Must be departed or in_transit.",
        )

    updated = repo.update_status(
        trip_id,
        "completed",
        extra={"completed_at": datetime.datetime.utcnow().isoformat()},
    )
    log.info("Trip %s completed by driver %s", trip_id, current_user["email"])
    return TripResponse(**updated)
