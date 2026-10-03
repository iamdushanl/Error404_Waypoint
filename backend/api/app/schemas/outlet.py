"""Outlet Pydantic schemas."""
from __future__ import annotations

from pydantic import BaseModel


class OutletResponse(BaseModel):
    outlet_id: str
    brand: str
    district: str
    depot: str
    dock_type: str
    parking_constraint: str
    mall_window: str | None
    window_open_time: str
    window_close_time: str

    model_config = {"from_attributes": True}
