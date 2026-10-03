"""
Outlets routes — read-only reference data.

GET /api/v1/outlets                 → list outlets (all authenticated roles)
GET /api/v1/outlets/{outlet_id}     → single outlet
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user
from app.db.session import get_supabase
from app.repositories.outlet_repository import OutletRepository
from app.schemas.common import PagedResponse
from app.schemas.outlet import OutletResponse

router = APIRouter(prefix="/api/v1/outlets", tags=["outlets"])


def _get_repo() -> OutletRepository:
    return OutletRepository(get_supabase())


@router.get(
    "",
    response_model=PagedResponse[OutletResponse],
    summary="List outlets",
    description=(
        "Returns all outlets with optional filters. "
        "All authenticated roles can read outlets."
    ),
)
async def list_outlets(
    brand: str | None = Query(None, description="Filter by brand: Fresh, Style, Tech"),
    district: str | None = Query(None, description="Partial match on district name"),
    depot: str | None = Query(None, description="Filter by depot: Peliyagoda or Kandy"),
    parking_constraint: str | None = Query(None, description="normal | van_only | mall_dock"),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: Any = Depends(get_current_user),   # auth required
    repo: OutletRepository = Depends(_get_repo),
) -> PagedResponse[OutletResponse]:
    rows, total = repo.list(
        brand=brand,
        district=district,
        depot=depot,
        parking_constraint=parking_constraint,
        limit=limit,
        offset=offset,
    )
    return PagedResponse(
        data=[OutletResponse(**r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{outlet_id}",
    response_model=OutletResponse,
    summary="Get outlet by ID",
)
async def get_outlet(
    outlet_id: str,
    _: Any = Depends(get_current_user),
    repo: OutletRepository = Depends(_get_repo),
) -> OutletResponse:
    outlet = repo.get(outlet_id)
    if not outlet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Outlet '{outlet_id}' not found.",
        )
    return OutletResponse(**outlet)
