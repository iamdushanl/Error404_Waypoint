"""
Delivery routes — Phase 6 delivery execution API.

Role access:
  driver        : complete deliveries, record POD
  loader        : record shortfalls, acknowledge trips
  store_manager : confirm receipt
  dispatcher    : read-only access to all delivery data

Endpoints (all under /api/v1):

  DELIVERY EXECUTION
  POST  /deliveries                        ← driver records stop outcome
  GET   /deliveries/{id}                   ← get delivery record
  GET   /deliveries/{id}/pod               ← get POD for a delivery
  POST  /deliveries/{id}/pod               ← driver records POD
  POST  /deliveries/{id}/confirm           ← store manager confirms receipt

  SHORTFALLS (on a trip stop)
  POST  /trips/{trip_id}/stops/{stop_id}/shortfalls  ← loader records shortfall
  GET   /trips/{trip_id}/stops/{stop_id}/shortfalls  ← list shortfalls for stop

  DELIVERY SUMMARY (trip-level)
  GET   /trips/{trip_id}/deliveries        ← all delivery records for a trip

Business rules enforced in this layer:
  - A stop can only have one delivery record (no double-completing a stop).
  - POD is only allowed when outcome == 'delivered'.
  - Receipt confirmation is only allowed when outcome == 'delivered'.
  - Shortfalls are only recordable while the trip status is 'loading'.
  - offline_operation_id is treated as an idempotency key:
    if the same ID is seen again, the existing record is returned (not re-inserted).
  - After a delivery is recorded, the trip_stop status is updated accordingly.
"""
from __future__ import annotations

import datetime
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import get_current_user, require_role
from app.db.session import get_supabase
from app.repositories.delivery_repository import DeliveryRepository
from app.schemas.delivery import (
    DeliveryCreate,
    DeliveryResponse,
    ProofOfDeliveryCreate,
    ProofOfDeliveryResponse,
    ReceiptConfirmationCreate,
    ReceiptConfirmationResponse,
    ShortfallCreate,
    ShortfallResponse,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["deliveries"])


def _delivery_repo() -> DeliveryRepository:
    return DeliveryRepository(get_supabase())


@router.get(
    "/outlets/{outlet_id}/deliveries",
    response_model=list[DeliveryResponse],
    summary="List deliveries for a store outlet",
    description="Store managers may list delivery records for their assigned outlet; dispatchers may read any outlet.",
)
async def list_outlet_deliveries(
    outlet_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[DeliveryResponse]:
    if current_user.get("role") == "store_manager" and current_user.get("outlet_id") != outlet_id:
        raise HTTPException(status_code=404, detail="Outlet not found.")

    db = get_supabase()
    orders = db.table("orders").select("id").eq("outlet_id", outlet_id).execute().data or []
    order_ids = [row["id"] for row in orders]
    if not order_ids:
        return []
    stops = db.table("trip_stops").select("id").in_("order_id", order_ids).execute().data or []
    stop_ids = [row["id"] for row in stops]
    if not stop_ids:
        return []
    deliveries = db.table("deliveries").select("*").in_("trip_stop_id", stop_ids).order("created_at", desc=True).execute().data or []
    return [DeliveryResponse(**delivery) for delivery in deliveries]


# ── POST /api/v1/deliveries — driver records stop outcome ────────────────────

@router.post(
    "/deliveries",
    response_model=DeliveryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record delivery outcome",
    description=(
        "Driver records the outcome of a trip stop: delivered, attempted, or refused.\\n\\n"
        "**Idempotent**: if `offline_operation_id` is supplied and the operation was "
        "already recorded (offline sync duplicate), the existing record is returned "
        "with HTTP 200 instead of re-inserting.\\n\\n"
        "After recording, the trip stop status is updated to match the outcome.\\n\\n"
        "**Driver only.**"
    ),
)
async def record_delivery(
    body: DeliveryCreate,
    response: Response,
    current_user: dict[str, Any] = Depends(require_role("driver")),
) -> DeliveryResponse:
    db = get_supabase()
    repo = DeliveryRepository(db)

    # ── Idempotency check ─────────────────────────────────────────────────────
    if body.offline_operation_id:
        existing = repo.get_delivery_by_operation_id(body.offline_operation_id)
        if existing:
            log.info(
                "Duplicate offline sync — returning existing delivery",
                extra={"operation_id": body.offline_operation_id},
            )
            response.status_code = status.HTTP_200_OK
            return DeliveryResponse(**existing)

    # ── Duplicate stop check ──────────────────────────────────────────────────
    existing_for_stop = repo.get_delivery_by_stop(body.trip_stop_id)
    if existing_for_stop:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Stop '{body.trip_stop_id}' already has a delivery record "
                f"(outcome: '{existing_for_stop['outcome']}'). "
                "A stop can only be completed once."
            ),
        )

    # ── Verify the stop exists and belongs to the driver's trip ───────────────
    stop_resp = (
        db.table("trip_stops")
        .select("id, trip_id, order_id, status, trips!inner(vehicle_id, status)")
        .eq("id", body.trip_stop_id)
        .maybe_single()
        .execute()
    )
    if not stop_resp.data:
        raise HTTPException(status_code=404, detail="Trip stop not found.")

    stop = stop_resp.data
    trip = stop.get("trips", {})

    # Stop must be in a departed/in_transit trip
    if trip.get("status") not in ("departed", "in_transit"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Trip is in status '{trip.get('status')}'. "
                "Deliveries can only be recorded after the trip has departed."
            ),
        )

    # ── Insert delivery ───────────────────────────────────────────────────────
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    payload = {
        "trip_stop_id": body.trip_stop_id,
        "driver_id": current_user["id"],
        "outcome": body.outcome,
        "recipient_name": body.recipient_name,
        "notes": body.notes,
        "delivered_at": (
            body.delivered_at.isoformat()
            if body.delivered_at
            else now_iso
        ),
        "offline_operation_id": body.offline_operation_id,
        "synced_at": now_iso if body.offline_operation_id else None,
    }

    delivery = repo.create_delivery(payload)

    # ── Update trip stop status ───────────────────────────────────────────────
    status_map = {
        "delivered": "delivered",
        "attempted": "attempted",
        "refused": "refused",
    }
    db.table("trip_stops").update({
        "status": status_map[body.outcome],
        "actual_arrival_time": payload["delivered_at"],
    }).eq("id", body.trip_stop_id).execute()

    # ── Update order status ───────────────────────────────────────────────────
    order_id = stop.get("order_id")
    if order_id:
        order_status = "delivered" if body.outcome == "delivered" else "attempted"
        db.table("orders").update({"status": order_status}).eq("id", order_id).execute()

    # ── Auto-update trip to in_transit if this is the first delivery ──────────
    if trip.get("status") == "departed":
        db.table("trips").update({"status": "in_transit"}).eq(
            "id", stop["trip_id"]
        ).execute()

    log.info(
        "Delivery recorded",
        extra={
            "delivery_id": delivery["id"],
            "stop_id": body.trip_stop_id,
            "outcome": body.outcome,
            "driver_id": current_user["id"],
        },
    )

    return DeliveryResponse(**delivery)


# ── GET /api/v1/deliveries/{id} ───────────────────────────────────────────────

@router.get(
    "/deliveries/{delivery_id}",
    response_model=DeliveryResponse,
    summary="Get delivery record",
)
async def get_delivery(
    delivery_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> DeliveryResponse:
    repo = _delivery_repo()
    delivery = repo.get_delivery(delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found.")
    return DeliveryResponse(**delivery)


# ── GET /api/v1/trips/{trip_id}/deliveries ────────────────────────────────────

@router.get(
    "/trips/{trip_id}/deliveries",
    response_model=list[DeliveryResponse],
    summary="List deliveries for a trip",
    description="Returns all delivery outcomes recorded for stops in this trip.",
)
async def list_trip_deliveries(
    trip_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[DeliveryResponse]:
    db = get_supabase()

    # Get all stops in this trip, then their deliveries
    stops_resp = (
        db.table("trip_stops")
        .select("id")
        .eq("trip_id", trip_id)
        .execute()
    )
    stop_ids = [s["id"] for s in (stops_resp.data or [])]

    if not stop_ids:
        return []

    deliveries_resp = (
        db.table("deliveries")
        .select("*")
        .in_("trip_stop_id", stop_ids)
        .order("created_at")
        .execute()
    )

    return [DeliveryResponse(**d) for d in (deliveries_resp.data or [])]


@router.get(
    "/outlets/{outlet_id}/deliveries",
    response_model=list[DeliveryResponse],
    summary="List deliveries for a store outlet",
)
async def list_outlet_deliveries(
    outlet_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[DeliveryResponse]:
    if current_user.get("role") == "store_manager" and current_user.get("outlet_id") != outlet_id:
        raise HTTPException(status_code=404, detail="Outlet not found.")
    db = get_supabase()
    stops_resp = (
        db.table("trip_stops")
        .select("id")
        .eq("outlet_id", outlet_id)
        .execute()
    )
    stop_ids = [stop["id"] for stop in (stops_resp.data or [])]
    if not stop_ids:
        return []
    deliveries = (
        db.table("deliveries")
        .select("*")
        .in_("trip_stop_id", stop_ids)
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )
    return [DeliveryResponse(**delivery) for delivery in deliveries]


# ── POST /api/v1/deliveries/{id}/pod — driver records Proof of Delivery ──────

@router.post(
    "/deliveries/{delivery_id}/pod",
    response_model=ProofOfDeliveryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record Proof of Delivery",
    description=(
        "Driver attaches proof to a completed delivery.\\n\\n"
        "- Delivery outcome must be **'delivered'** — POD is not applicable to "
        "  attempted or refused stops.\\n"
        "- Only one POD per delivery.\\n"
        "- Upload photo/signature to Supabase Storage first, then submit the URL here.\\n\\n"
        "**Driver only.**"
    ),
)
async def record_pod(
    delivery_id: str,
    body: ProofOfDeliveryCreate,
    current_user: dict[str, Any] = Depends(require_role("driver")),
) -> ProofOfDeliveryResponse:
    db = get_supabase()
    repo = DeliveryRepository(db)

    delivery = repo.get_delivery(delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found.")

    # POD only for delivered stops
    if delivery["outcome"] != "delivered":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Proof of Delivery can only be added to a 'delivered' stop. "
                f"This stop has outcome '{delivery['outcome']}'."
            ),
        )

    # One POD per delivery
    existing_pod = repo.get_pod(delivery_id)
    if existing_pod:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This delivery already has a Proof of Delivery record.",
        )

    payload = {
        "delivery_id": delivery_id,
        "recipient_name": body.recipient_name,
        "photo_url": body.photo_url,
        "recipient_signature_url": body.recipient_signature_url,
        "recorded_at": body.recorded_at.isoformat(),
    }

    pod = repo.create_pod(payload)

    log.info(
        "POD recorded",
        extra={"delivery_id": delivery_id, "driver_id": current_user["id"]},
    )

    return ProofOfDeliveryResponse(**pod)


# ── GET /api/v1/deliveries/{id}/pod ──────────────────────────────────────────

@router.get(
    "/deliveries/{delivery_id}/pod",
    response_model=ProofOfDeliveryResponse,
    summary="Get Proof of Delivery",
)
async def get_pod(
    delivery_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> ProofOfDeliveryResponse:
    repo = _delivery_repo()
    pod = repo.get_pod(delivery_id)
    if not pod:
        raise HTTPException(status_code=404, detail="No Proof of Delivery found for this delivery.")
    return ProofOfDeliveryResponse(**pod)


# ── POST /api/v1/deliveries/{id}/confirm — store manager receipt ──────────────

@router.post(
    "/deliveries/{delivery_id}/confirm",
    response_model=ReceiptConfirmationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Store manager confirms receipt",
    description=(
        "Store manager confirms what they actually received.\\n\\n"
        "- Delivery outcome must be **'delivered'**.\\n"
        "- Only one confirmation per delivery.\\n"
        "- `items_received` is a dict of `{sku: quantity}`.\\n\\n"
        "**Store manager only.**"
    ),
)
async def confirm_receipt(
    delivery_id: str,
    body: ReceiptConfirmationCreate,
    current_user: dict[str, Any] = Depends(require_role("store_manager")),
) -> ReceiptConfirmationResponse:
    db = get_supabase()
    repo = DeliveryRepository(db)

    delivery = repo.get_delivery(delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found.")

    if delivery["outcome"] != "delivered":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Receipt confirmation is only applicable to 'delivered' stops. "
                f"This stop has outcome '{delivery['outcome']}'."
            ),
        )

    existing = repo.get_receipt(delivery_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A receipt confirmation already exists for this delivery.",
        )

    # Get the order_id from the trip stop
    stop_resp = (
        db.table("trip_stops")
        .select("order_id")
        .eq("id", delivery["trip_stop_id"])
        .maybe_single()
        .execute()
    )
    if not stop_resp.data:
        raise HTTPException(status_code=404, detail="Associated trip stop not found.")

    order_id = stop_resp.data["order_id"]

    payload = {
        "delivery_id": delivery_id,
        "order_id": order_id,
        "confirmed_by": current_user["id"],
        "items_received": body.items_received,
        "issues_noted": body.issues_noted,
        "confirmed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    receipt = repo.create_receipt(payload)

    log.info(
        "Receipt confirmed",
        extra={
            "delivery_id": delivery_id,
            "order_id": order_id,
            "confirmed_by": current_user["id"],
        },
    )

    return ReceiptConfirmationResponse(**receipt)


# ── GET /api/v1/trips/{trip_id}/stops/{stop_id}/shortfalls ───────────────────

@router.get(
    "/trips/{trip_id}/stops/{stop_id}/shortfalls",
    response_model=list[ShortfallResponse],
    summary="List shortfalls for a stop",
)
async def list_shortfalls(
    trip_id: str,
    stop_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[ShortfallResponse]:
    repo = _delivery_repo()
    shortfalls = repo.list_shortfalls_for_stop(stop_id)
    return [ShortfallResponse(**s) for s in shortfalls]


# ── POST /api/v1/trips/{trip_id}/stops/{stop_id}/shortfalls ──────────────────

@router.post(
    "/trips/{trip_id}/stops/{stop_id}/shortfalls",
    response_model=ShortfallResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a shortfall",
    description=(
        "Loader records an item shortfall for a stop before the vehicle departs.\\n\\n"
        "- Trip must be in **'loading'** status — shortfalls cannot be added after departure.\\n"
        "- `actual_quantity` must be less than `expected_quantity`.\\n\\n"
        "After recording, the trip stop status is updated to 'shortfall'.\\n\\n"
        "**Loader only.**"
    ),
)
async def record_shortfall(
    trip_id: str,
    stop_id: str,
    body: ShortfallCreate,
    current_user: dict[str, Any] = Depends(require_role("loader")),
) -> ShortfallResponse:
    db = get_supabase()

    # Verify stop belongs to this trip
    stop_resp = (
        db.table("trip_stops")
        .select("id, trip_id, status, trips!inner(status)")
        .eq("id", stop_id)
        .eq("trip_id", trip_id)
        .maybe_single()
        .execute()
    )
    if not stop_resp.data:
        raise HTTPException(status_code=404, detail="Trip stop not found.")

    stop = stop_resp.data
    trip_status = stop.get("trips", {}).get("status")

    # Shortfalls only while loading
    if trip_status != "loading":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Trip is in status '{trip_status}'. "
                "Shortfalls can only be recorded while the trip is loading."
            ),
        )

    # actual_quantity must be less than expected
    if body.actual_quantity >= body.expected_quantity:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"actual_quantity ({body.actual_quantity}) must be less than "
                f"expected_quantity ({body.expected_quantity}) to constitute a shortfall."
            ),
        )

    payload = {
        "trip_stop_id": stop_id,
        "issue_type": body.issue_type,
        "sku": body.sku,
        "description": body.description,
        "expected_quantity": body.expected_quantity,
        "actual_quantity": body.actual_quantity,
        "photo_url": body.photo_url,
        "notes": body.notes,
        "recorded_by": current_user["id"],
    }

    repo = DeliveryRepository(db)
    shortfall = repo.create_shortfall(payload)

    # Update trip stop status to shortfall
    db.table("trip_stops").update({"status": "shortfall"}).eq("id", stop_id).execute()

    log.info(
        "Shortfall recorded",
        extra={
            "stop_id": stop_id,
            "trip_id": trip_id,
            "sku": body.sku,
            "issue_type": body.issue_type,
            "loader_id": current_user["id"],
        },
    )

    return ShortfallResponse(**shortfall)
