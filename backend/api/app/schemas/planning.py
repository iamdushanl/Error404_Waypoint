"""
Planning Pydantic schemas — request and response models for the planning API.
"""
from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ── Request ───────────────────────────────────────────────────────────────────

class PlanGenerateRequest(BaseModel):
    """POST /api/v1/planning/generate"""
    plan_date: datetime.date = Field(
        ..., description="The delivery date to plan for (YYYY-MM-DD)."
    )
    depot: Literal["Peliyagoda", "Kandy"] = Field(
        ..., description="Depot for which to generate the plan."
    )
    dry_run: bool = Field(
        False,
        description=(
            "If true, compute the plan and validate it but do NOT persist "
            "to the database. Useful for previewing before committing."
        ),
    )


# ── Response building blocks ──────────────────────────────────────────────────

class StopSchema(BaseModel):
    order_id: str
    outlet_id: str
    sequence_number: int
    load_position: int
    planned_arrival_time: str | None


class TripSchema(BaseModel):
    vehicle_id: str
    trip_number: int
    brand: str
    district: str
    depot: str
    orders: list[str]
    total_weight_kg: float
    total_volume_m3: float
    estimated_duration_min: float
    estimated_distance_km: float
    estimated_fuel_l: float
    planned_departure_time: str | None
    stops: list[StopSchema]


class DeferredOrderSchema(BaseModel):
    order_id: str
    reason_code: str
    reason_detail: str


class AllocationMetricsSchema(BaseModel):
    total_orders: int
    served_orders: int
    deferred_orders: int
    vehicles_used: int
    trips_created: int
    reefer_trips: int
    van_trips: int
    fresh_trips: int
    style_trips: int
    tech_trips: int
    total_weight_allocated_kg: float
    total_volume_allocated_m3: float
    deferred_reason_counts: dict[str, int]


class ValidationSummarySchema(BaseModel):
    valid: bool
    violation_count: int


class PlanGenerateResponse(BaseModel):
    """Response from POST /api/v1/planning/generate"""
    plan_id: str | None = Field(None, description="UUID of the persisted plan; null on dry_run.")
    plan_date: str
    depot: str
    status: str
    validation: ValidationSummarySchema
    trips: list[TripSchema]
    deferred_orders: list[DeferredOrderSchema]
    metrics: AllocationMetricsSchema


# ── Plan list response ─────────────────────────────────────────────────────────

class DeliveryPlanResponse(BaseModel):
    """A single delivery_plan row."""
    id: str
    plan_date: datetime.date
    depot: str
    status: str
    created_by: str | None
    confirmed_at: datetime.datetime | None
    created_at: datetime.datetime
