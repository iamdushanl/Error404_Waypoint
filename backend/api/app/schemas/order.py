"""Order Pydantic schemas — request and response models."""
from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

OrderStatus = Literal[
    "draft", "submitted", "closed", "allocated",
    "deferred", "in_transit", "delivered", "confirmed"
]
TempRequirement = Literal["chilled", "ambient"]
Brand = Literal["Fresh", "Style", "Tech"]


# ── Order Item ────────────────────────────────────────────────────────────────

class OrderItemCreate(BaseModel):
    sku: str = Field(..., min_length=1, max_length=50)
    description: str = Field(..., min_length=1, max_length=200)
    quantity: int = Field(..., gt=0)
    weight_kg: float = Field(..., gt=0)
    volume_m3: float = Field(..., gt=0)
    temp_requirement: TempRequirement


class OrderItemResponse(BaseModel):
    id: str
    order_id: str
    sku: str
    description: str
    quantity: int
    weight_kg: float
    volume_m3: float
    temp_requirement: str
    created_at: datetime.datetime


# ── Order ─────────────────────────────────────────────────────────────────────

class OrderCreate(BaseModel):
    """POST /api/v1/orders — store manager creates a new order."""
    outlet_id: str = Field(..., min_length=1)
    brand: Brand
    requested_date: datetime.date
    temp_requirement: TempRequirement
    notes: str | None = None
    items: list[OrderItemCreate] = Field(..., min_length=1)

    @field_validator("requested_date")
    @classmethod
    def requested_date_must_be_future(cls, v: datetime.date) -> datetime.date:
        if v < datetime.date.today():
            raise ValueError("requested_date must be today or in the future")
        return v


class OrderResponse(BaseModel):
    """Single order in API responses."""
    id: str
    outlet_id: str
    brand: str
    requested_date: datetime.date
    status: str
    temp_requirement: str
    total_weight_kg: float
    total_volume_m3: float
    notes: str | None
    created_by: str | None
    submitted_at: datetime.datetime | None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class OrderWithItemsResponse(OrderResponse):
    """Order + its line items (used in detail view)."""
    items: list[OrderItemResponse] = []


class OrderStatusUpdate(BaseModel):
    """PATCH /api/v1/orders/{id}/status — dispatcher updates order status."""
    status: OrderStatus
    notes: str | None = None
