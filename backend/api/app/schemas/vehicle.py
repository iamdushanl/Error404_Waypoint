"""Vehicle Pydantic schemas."""
from __future__ import annotations

from pydantic import BaseModel


class VehicleResponse(BaseModel):
    vehicle_id: str
    type: str
    temp: str
    weight_cap_kg: float
    volume_cap_m3: float
    fuel_type: str
    km_per_l: float
    weekly_fuel_quota_l: float
    depot: str

    model_config = {"from_attributes": True}
