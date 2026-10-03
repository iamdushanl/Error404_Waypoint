"""
Allocation engine — domain models.

These are pure Python dataclasses that the engine operates on.
No database imports. No FastAPI imports.
All can be constructed in unit tests without infrastructure.

Data flows:
  Repository layer  → builds OrderCandidate / VehicleCandidate / etc.
  AllocationEngine  → operates on these models, returns AllocationResult
  Planning service  → persists AllocationResult to Supabase
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# ── Shared types ──────────────────────────────────────────────────────────────

Brand = Literal["Fresh", "Style", "Tech"]
VehicleType = Literal["truck", "van"]
TempCapability = Literal["reefer", "ambient"]
TempRequirement = Literal["chilled", "ambient"]
ParkingConstraint = Literal["normal", "van_only", "mall_dock"]
DockType = Literal["rear_dock", "street", "mall_bay"]


# ── Input domain models ────────────────────────────────────────────────────────

@dataclass
class OutletInfo:
    """Outlet reference data required by the allocation engine."""
    outlet_id: str
    brand: Brand
    district: str
    depot: str
    dock_type: DockType
    parking_constraint: ParkingConstraint
    window_open_time: str   # "HH:MM"
    window_close_time: str  # "HH:MM"
    mall_window: str | None = None


@dataclass
class OrderCandidate:
    """
    One confirmed order eligible for allocation consideration.

    Fields match the `orders` + joined `outlets` row from the repository.
    The engine NEVER mutates this object.
    """
    order_id: str
    outlet_id: str
    brand: Brand
    district: str
    depot: str                       # derived from outlet
    temp_requirement: TempRequirement
    total_weight_kg: float
    total_volume_m3: float
    dock_type: DockType
    parking_constraint: ParkingConstraint
    window_open_time: str            # "HH:MM"
    window_close_time: str           # "HH:MM"
    # Priority policy signals (may be 0 / False if not available)
    deferred_yesterday: bool = False
    days_since_last_served: int = 0


@dataclass
class VehicleCandidate:
    """
    One available vehicle for allocation.

    Fields match the `vehicles` table row.
    The engine NEVER mutates this object — it tracks state in TripState.
    """
    vehicle_id: str
    type: VehicleType
    temp: TempCapability
    weight_cap_kg: float
    volume_cap_m3: float
    fuel_type: str
    km_per_l: float
    weekly_fuel_quota_l: float
    depot: str


@dataclass
class TravelData:
    """
    Depot → district travel parameters from district_travel.csv.
    One row per (district, depot) combination.
    """
    district: str
    depot: str
    depot_to_district_freeflow_min: float
    inter_stop_freeflow_min: float
    depot_to_district_km: float
    inter_stop_km: float


@dataclass
class ServiceAllowance:
    """
    Handling time per brand × dock_type from service_allowance.csv.
    """
    brand: Brand
    dock_type: DockType
    service_allowance_min: int


# ── Mutable planning state (engine-internal) ──────────────────────────────────

@dataclass
class StopPlan:
    """A single planned stop within a trip."""
    order_id: str
    outlet_id: str
    sequence_number: int             # delivery order (1-indexed)
    load_position: int               # loading order (reverse of sequence)
    planned_arrival_time: str | None = None  # "HH:MM"


@dataclass
class TripState:
    """
    Mutable trip state during planning.

    The engine builds these up and then freezes them into TripResult
    once planning is complete.

    A TripState is entirely in-memory — nothing is persisted yet.
    """
    vehicle_id: str
    trip_number: int          # 1 or 2
    brand: Brand
    district: str
    depot: str
    # Accumulated loads
    orders: list[str] = field(default_factory=list)     # order_id list
    stops: list[StopPlan] = field(default_factory=list)
    total_weight_kg: float = 0.0
    total_volume_m3: float = 0.0
    estimated_duration_min: float = 0.0
    estimated_distance_km: float = 0.0
    estimated_fuel_l: float = 0.0
    planned_departure_time: str | None = None

    def order_count(self) -> int:
        return len(self.orders)

    def remaining_weight(self, vehicle: VehicleCandidate) -> float:
        return vehicle.weight_cap_kg - self.total_weight_kg

    def remaining_volume(self, vehicle: VehicleCandidate) -> float:
        return vehicle.volume_cap_m3 - self.total_volume_m3


# ── Output domain models ───────────────────────────────────────────────────────

@dataclass
class DeferredOrderResult:
    """Why a specific order could not be allocated."""
    order_id: str
    reason_code: str    # machine-readable, stable
    reason_detail: str  # human-readable, dispatcher-facing


@dataclass
class TripResult:
    """A finalised, validated trip ready for persistence."""
    vehicle_id: str
    trip_number: int
    brand: Brand
    district: str
    depot: str
    orders: list[str]               # order_id list (allocation sequence)
    stops: list[StopPlan]
    total_weight_kg: float
    total_volume_m3: float
    estimated_duration_min: float
    estimated_distance_km: float
    estimated_fuel_l: float
    planned_departure_time: str | None = None


@dataclass
class AllocationMetrics:
    """Summary statistics for the generated plan."""
    total_orders: int = 0
    served_orders: int = 0
    deferred_orders: int = 0
    vehicles_used: int = 0
    trips_created: int = 0
    reefer_trips: int = 0
    van_trips: int = 0
    fresh_trips: int = 0
    style_trips: int = 0
    tech_trips: int = 0
    total_weight_allocated_kg: float = 0.0
    total_volume_allocated_m3: float = 0.0
    deferred_reason_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class AllocationResult:
    """
    The complete output of one allocation engine run.

    This is the contract between AllocationEngine and the planning service.
    The service validates this, then persists it in a single transaction.
    """
    plan_date: str          # "YYYY-MM-DD"
    depot: str
    status: str = "generated"
    trips: list[TripResult] = field(default_factory=list)
    deferred_orders: list[DeferredOrderResult] = field(default_factory=list)
    metrics: AllocationMetrics = field(default_factory=AllocationMetrics)
