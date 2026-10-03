"""
Orders routes — the core business object of Waypoint.

Role access matrix:
  store_manager : create, submit, read own outlet's orders, confirm receipt
  dispatcher    : read all, update status (close/allocate/defer)
  driver        : read own allocated orders
  loader        : read orders in their trips (via trip_stops)

Endpoints:
  POST   /api/v1/orders                    ← store_manager creates
  GET    /api/v1/orders                    ← filtered list
  GET    /api/v1/orders/{id}               ← detail with items
  POST   /api/v1/orders/{id}/submit        ← store_manager submits
  PATCH  /api/v1/orders/{id}/status        ← dispatcher updates status
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user, require_role
from app.core.exceptions import AuthorizationError
from app.db.session import get_supabase
from app.repositories.order_repository import OrderRepository
from app.schemas.common import PagedResponse
from app.schemas.order import (
    OrderCreate,
    OrderResponse,
    OrderStatusUpdate,
    OrderWithItemsResponse,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


def _get_repo() -> OrderRepository:
    return OrderRepository(get_supabase())


# ── POST /api/v1/orders ───────────────────────────────────────────────────────

@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create order",
    description=(
        "Store manager creates a new order for their outlet. "
        "The outlet_id must match the store manager's assigned outlet. "
        "Order starts in 'draft' status."
    ),
)
async def create_order(
    body: OrderCreate,
    current_user: dict[str, Any] = Depends(require_role("store_manager")),
    repo: OrderRepository = Depends(_get_repo),
) -> OrderResponse:
    # Enforce store manager can only order for their own outlet
    if current_user.get("outlet_id") != body.outlet_id:
        raise AuthorizationError(
            "You can only create orders for your assigned outlet "
            f"({current_user.get('outlet_id')})."
        )

    # Compute totals from items
    total_weight = sum(i.weight_kg * i.quantity for i in body.items)
    total_volume = sum(i.volume_m3 * i.quantity for i in body.items)

    # Create the order
    order_payload = {
        "outlet_id": body.outlet_id,
        "brand": body.brand,
        "requested_date": str(body.requested_date),
        "status": "draft",
        "temp_requirement": body.temp_requirement,
        "total_weight_kg": round(total_weight, 3),
        "total_volume_m3": round(total_volume, 4),
        "notes": body.notes,
        "created_by": current_user["id"],
    }
    order = repo.create(order_payload)

    # Create line items
    item_payloads = [
        {
            "order_id": order["id"],
            "sku": i.sku,
            "description": i.description,
            "quantity": i.quantity,
            "weight_kg": i.weight_kg,
            "volume_m3": i.volume_m3,
            "temp_requirement": i.temp_requirement,
        }
        for i in body.items
    ]
    repo.create_items(item_payloads)

    log.info("Order created: %s by %s", order["id"], current_user["email"])
    return OrderResponse(**order)


# ── GET /api/v1/orders ────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=PagedResponse[OrderResponse],
    summary="List orders",
    description=(
        "Returns orders filtered by role:\n"
        "- **store_manager**: only their outlet's orders\n"
        "- **dispatcher**: all orders\n"
        "- **driver**: orders on their assigned trips\n"
        "- **loader**: orders in their depot's trips"
    ),
)
async def list_orders(
    brand: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    requested_date: str | None = Query(None, description="YYYY-MM-DD"),
    outlet_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: dict[str, Any] = Depends(get_current_user),
    repo: OrderRepository = Depends(_get_repo),
) -> PagedResponse[OrderResponse]:
    role = current_user["role"]

    # Store manager: can only see their own outlet's orders
    if role == "store_manager":
        rows, total = repo.list_for_outlet(
            current_user["outlet_id"],
            status=status_filter,
            limit=limit,
            offset=offset,
        )
    else:
        # Dispatcher / loader / driver: broader access with filters
        effective_outlet = outlet_id
        effective_depot = current_user.get("depot") if role in ("loader",) else None

        rows, total = repo.list(
            outlet_id=effective_outlet,
            brand=brand,
            status=status_filter,
            depot=effective_depot,
            limit=limit,
            offset=offset,
        )

    return PagedResponse(
        data=[OrderResponse(**r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


# ── GET /api/v1/orders/{id} ───────────────────────────────────────────────────

@router.get(
    "/{order_id}",
    response_model=OrderWithItemsResponse,
    summary="Get order details",
    description="Returns a single order with all its line items.",
)
async def get_order(
    order_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    repo: OrderRepository = Depends(_get_repo),
) -> OrderWithItemsResponse:
    order = repo.get_with_items(order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{order_id}' not found.",
        )

    # Store manager may only see their own outlet's orders
    if (
        current_user["role"] == "store_manager"
        and order["outlet_id"] != current_user.get("outlet_id")
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

    return OrderWithItemsResponse(**order)


# ── POST /api/v1/orders/{id}/submit ──────────────────────────────────────────

@router.post(
    "/{order_id}/submit",
    response_model=OrderResponse,
    summary="Submit order",
    description=(
        "Store manager submits a draft order for dispatcher review. "
        "Order must be in 'draft' status."
    ),
)
async def submit_order(
    order_id: str,
    current_user: dict[str, Any] = Depends(require_role("store_manager")),
    repo: OrderRepository = Depends(_get_repo),
) -> OrderResponse:
    order = repo.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    if order["outlet_id"] != current_user.get("outlet_id"):
        raise HTTPException(status_code=404, detail="Order not found.")

    if order["status"] != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Order is already '{order['status']}' — only draft orders can be submitted.",
        )

    updated = repo.submit(order_id)
    log.info("Order submitted: %s by %s", order_id, current_user["email"])
    return OrderResponse(**updated)


# ── PATCH /api/v1/orders/{id}/status ─────────────────────────────────────────

@router.patch(
    "/{order_id}/status",
    response_model=OrderResponse,
    summary="Update order status",
    description=(
        "Dispatcher updates an order's status "
        "(e.g. 'submitted' → 'allocated' or 'deferred'). "
        "**Dispatcher only.**"
    ),
)
async def update_order_status(
    order_id: str,
    body: OrderStatusUpdate,
    current_user: dict[str, Any] = Depends(require_role("dispatcher")),
    repo: OrderRepository = Depends(_get_repo),
) -> OrderResponse:
    order = repo.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    updated = repo.update_status(
        order_id,
        body.status,
        extra={"notes": body.notes} if body.notes else None,
    )
    log.info(
        "Order %s status → '%s' by %s", order_id, body.status, current_user["email"]
    )
    return OrderResponse(**updated)
