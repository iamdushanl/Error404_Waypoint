"""
Vehicles routes — read-only reference data.

GET /api/v1/vehicles                → list vehicles (dispatcher, loader, driver)
GET /api/v1/vehicles/{vehicle_id}   → single vehicle
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import require_role
from app.db.session import get_supabase
from app.repositories.vehicle_repository import VehicleRepository
from app.schemas.common import PagedResponse
from app.schemas.vehicle import VehicleResponse

router = APIRouter(prefix="/api/v1/vehicles", tags=["vehicles"])


def _get_repo() -> VehicleRepository:
    return VehicleRepository(get_supabase())


@router.get(
    "",
    response_model=PagedResponse[VehicleResponse],
    summary="List vehicles",
    description="Returns all vehicles with optional filters. Accessible to dispatcher, loader, and driver.",
)
async def list_vehicles(
    depot: str | None = Query(None, description="Peliyagoda or Kandy"),
    type: str | None = Query(None, description="truck or van"),
    temp: str | None = Query(None, description="reefer or ambient"),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: Any = Depends(require_role("dispatcher", "loader", "driver")),
    repo: VehicleRepository = Depends(_get_repo),
) -> PagedResponse[VehicleResponse]:
    rows, total = repo.list(depot=depot, type=type, temp=temp, limit=limit, offset=offset)
    return PagedResponse(
        data=[VehicleResponse(**r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{vehicle_id}",
    response_model=VehicleResponse,
    summary="Get vehicle by ID",
)
async def get_vehicle(
    vehicle_id: str,
    _: Any = Depends(require_role("dispatcher", "loader", "driver")),
    repo: VehicleRepository = Depends(_get_repo),
) -> VehicleResponse:
    vehicle = repo.get(vehicle_id)
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle '{vehicle_id}' not found.",
        )
    return VehicleResponse(**vehicle)
