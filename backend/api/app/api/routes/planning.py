"""
Planning routes — Phase 5 delivery planning API.

Role access:
  dispatcher : generate plans, list plans, confirm plans

Endpoints:
  POST  /api/v1/planning/generate     ← primary production planning endpoint
  GET   /api/v1/planning/plans        ← list delivery plans
  GET   /api/v1/planning/plans/{id}   ← get plan detail with trips
  PATCH /api/v1/planning/plans/{id}/confirm  ← dispatcher confirms plan

Design note:
  POST /generate is the replacement for the old single-order allocate concept.
  It runs the full AllocationEngine for a depot on a given date and returns
  the complete AllocationResult including served trips and deferred orders.

  The old /planning/allocate(order_id, route_id) pattern is intentionally
  NOT reproduced — it is architecturally insufficient for this challenge.
"""
from __future__ import annotations

import datetime
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, require_role
from app.db.session import get_supabase
from app.schemas.common import PagedResponse
from app.schemas.planning import (
    DeliveryPlanResponse,
    PlanGenerateRequest,
    PlanGenerateResponse,
)
from app.services.planning_service import PlanningService

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/planning", tags=["planning"])


def _get_service(current_user: dict[str, Any]) -> PlanningService:
    """Dependency: build a PlanningService scoped to the current dispatcher."""
    return PlanningService(
        db=get_supabase(),
        dispatcher_id=current_user.get("id"),
    )


# ── POST /api/v1/planning/generate ───────────────────────────────────────────

@router.post(
    "/generate",
    response_model=PlanGenerateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate delivery plan",
    description=(
        "Run the constraint-aware allocation engine for the given depot and date.\\n\\n"
        "The engine:\\n"
        "1. Loads all **submitted** orders for the date+depot.\\n"
        "2. Loads all available vehicles.\\n"
        "3. Scores and sorts orders by priority policy.\\n"
        "4. Greedily assigns orders to trips, enforcing all hard constraints.\\n"
        "5. Records deferred orders with explicit machine-readable reason codes.\\n"
        "6. Validates the complete plan against all hard constraints.\\n"
        "7. Persists to `delivery_plans`, `trips`, `trip_stops`, `deferred_orders`.\\n\\n"
        "Set `dry_run=true` to preview without persisting.\\n\\n"
        "**Dispatcher only.**"
    ),
)
async def generate_plan(
    body: PlanGenerateRequest,
    current_user: dict[str, Any] = Depends(require_role("dispatcher")),
) -> PlanGenerateResponse:
    service = _get_service(current_user)

    try:
        result = service.generate_plan(
            plan_date=body.plan_date,
            depot=body.depot,
            dry_run=body.dry_run,
        )
    except ValueError as exc:
        # Validation failure — plan was not persisted
        log.error("Plan generation failed validation: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except Exception as exc:
        log.exception("Unexpected error during plan generation")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Plan generation failed due to an internal error.",
        )

    log.info(
        "Plan generated",
        extra={
            "plan_id": result.get("plan_id"),
            "depot": body.depot,
            "plan_date": str(body.plan_date),
            "served": result["metrics"]["served_orders"],
            "deferred": result["metrics"]["deferred_orders"],
            "dry_run": body.dry_run,
        },
    )
    return PlanGenerateResponse(**result)


# ── GET /api/v1/planning/plans ────────────────────────────────────────────────

@router.get(
    "/plans",
    response_model=list[DeliveryPlanResponse],
    summary="List delivery plans",
    description="Returns all delivery plans. Optionally filter by depot or status. **Dispatcher only.**",
)
async def list_plans(
    depot: str | None = None,
    plan_status: str | None = None,
    current_user: dict[str, Any] = Depends(require_role("dispatcher")),
) -> list[DeliveryPlanResponse]:
    db = get_supabase()
    q = db.table("delivery_plans").select("*")

    if depot:
        q = q.eq("depot", depot)
    if plan_status:
        q = q.eq("status", plan_status)

    q = q.order("plan_date", desc=True)
    resp = q.execute()
    return [DeliveryPlanResponse(**row) for row in (resp.data or [])]


@router.get(
    "/capacity-outlook",
    summary="Get forward capacity outlook",
    description="Aggregates backend orders and fleet capacity for the next planning days. Dispatcher only.",
)
async def capacity_outlook(
    start_date: datetime.date,
    days: int = 5,
    current_user: dict[str, Any] = Depends(require_role("dispatcher")),
) -> list[dict[str, Any]]:
    if days < 1 or days > 14:
        raise HTTPException(status_code=422, detail="days must be between 1 and 14.")
    db = get_supabase()
    end_date = start_date + datetime.timedelta(days=days)
    vehicles = db.table("vehicles").select("vehicle_id,temp,weight_cap_kg").execute().data or []
    rows: list[dict[str, Any]] = []
    for offset in range(days):
        plan_date = start_date + datetime.timedelta(days=offset)
        orders = (
            db.table("orders")
            .select("total_weight_kg,temp_requirement")
            .eq("requested_date", str(plan_date))
            .in_("status", ["submitted", "closed", "allocated", "deferred"])
            .execute()
            .data
            or []
        )
        demand_kg = sum(float(order.get("total_weight_kg") or 0) for order in orders)
        rows.append({
            "date": str(plan_date),
            "order_count": len(orders),
            "demand_weight_kg": round(demand_kg, 2),
            "vehicle_count": len(vehicles),
            "vehicle_capacity_kg": round(sum(float(vehicle.get("weight_cap_kg") or 0) for vehicle in vehicles), 2),
            "reefer_count": sum(1 for vehicle in vehicles if vehicle.get("temp") == "reefer"),
            "capacity_gap_kg": round(max(0, demand_kg - sum(float(vehicle.get("weight_cap_kg") or 0) for vehicle in vehicles)), 2),
        })
    return rows


# ── GET /api/v1/planning/plans/{id} ──────────────────────────────────────────

@router.get(
    "/plans/{plan_id}",
    summary="Get plan detail",
    description="Returns a delivery plan with all its trips and stops. **Dispatcher only.**",
)
async def get_plan(
    plan_id: str,
    current_user: dict[str, Any] = Depends(require_role("dispatcher")),
) -> dict:
    db = get_supabase()

    # Plan
    plan_resp = (
        db.table("delivery_plans")
        .select("*")
        .eq("id", plan_id)
        .maybe_single()
        .execute()
    )
    if not plan_resp.data:
        raise HTTPException(status_code=404, detail="Plan not found.")

    # Trips with stops
    trips_resp = (
        db.table("trips")
        .select("*, trip_stops(*)")
        .eq("plan_id", plan_id)
        .order("vehicle_id")
        .execute()
    )

    # Deferred orders
    deferred_resp = (
        db.table("deferred_orders")
        .select("*")
        .eq("plan_id", plan_id)
        .execute()
    )

    plan = plan_resp.data
    plan["trips"] = trips_resp.data or []
    plan["deferred_orders"] = deferred_resp.data or []
    return plan


# ── PATCH /api/v1/planning/plans/{id}/confirm ────────────────────────────────

@router.patch(
    "/plans/{plan_id}/confirm",
    summary="Confirm delivery plan",
    description=(
        "Dispatcher confirms the plan — loaders and drivers can now see it.\\n\\n"
        "Plan must be in 'draft' status. **Dispatcher only.**"
    ),
)
async def confirm_plan(
    plan_id: str,
    current_user: dict[str, Any] = Depends(require_role("dispatcher")),
) -> dict:
    db = get_supabase()

    plan_resp = (
        db.table("delivery_plans")
        .select("id, status")
        .eq("id", plan_id)
        .maybe_single()
        .execute()
    )
    if not plan_resp.data:
        raise HTTPException(status_code=404, detail="Plan not found.")

    plan = plan_resp.data
    if plan["status"] != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Plan is already '{plan['status']}' — only draft plans can be confirmed.",
        )

    updated = (
        db.table("delivery_plans")
        .update({
            "status": "confirmed",
            "confirmed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })
        .eq("id", plan_id)
        .execute()
    )

    log.info("Plan %s confirmed by %s", plan_id, current_user["email"])
    return updated.data[0]

