"""Trip and TripStop Pydantic schemas."""
from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel

TripStatus = Literal["planned", "loading", "departed", "in_transit", "completed"]
StopStatus = Literal["planned", "loaded", "shortfall", "delivered", "attempted", "refused"]


class TripStopResponse(BaseModel):
    id: str
    trip_id: str
    order_id: str
    outlet_id: str
    sequence_number: int
    load_position: int
    planned_arrival_time: str | None
    actual_arrival_time: str | None = None
    status: str


class TripResponse(BaseModel):
    id: str
    plan_id: str
    vehicle_id: str
    trip_number: int
    brand: str
    district: str
    depot: str
    status: str
    planned_departure_time: str | None
    total_weight_kg: float
    total_volume_m3: float
    total_distance_km: float
    fuel_used_l: float
    estimated_duration_min: int
    loader_acknowledged: bool
    driver_acknowledged: bool
    departed_at: datetime.datetime | None
    completed_at: datetime.datetime | None
    created_at: datetime.datetime


class TripWithStopsResponse(TripResponse):
    """Trip + its stops (used in detail view)."""
    stops: list[TripStopResponse] = []


class TripAcknowledge(BaseModel):
    """PATCH /api/v1/trips/{id}/acknowledge — loader or driver acknowledges."""
    role: Literal["loader", "driver"]
