"""
Allocation constraints — hard feasibility rules.

Each function is a pure predicate.  It returns (passed: bool, reason_code: str, reason_detail: str).
These are the ONLY gatekeepers that decide whether an order can join a trip.

Design philosophy:
  - Hard constraints are binary — either the allocation is feasible or it is not.
  - They are NEVER soft penalties.
  - Every constraint can be tested independently with no infrastructure.
  - A new constraint = add one function + one unit test.

Constraint catalogue (matches challenge spec §Task 2B Feasibility Rules):

  C1  BRAND_DISTRICT     — all orders in a trip share brand + district
  C2  TEMPERATURE        — chilled ⇒ reefer vehicle; reefer may carry ambient
  C3  VAN_ACCESS         — van_only outlet ⇒ van vehicle
  C4  HOME_DEPOT         — order depot == vehicle depot
  C5  WHOLE_ORDER        — order belongs to exactly one trip (enforced by caller)
  C6  WEIGHT_CAPACITY    — sum(weight) ≤ vehicle weight cap
  C7  VOLUME_CAPACITY    — sum(volume) ≤ vehicle volume cap
  C8  MAX_TRIPS          — vehicle ≤ 2 trips per day
  C9  FRESH_TIME_BUDGET  — Fresh trips ≤ 270 min total per vehicle per day
  C10 STYLE_TECH_BUDGET  — Style + Tech trips ≤ 480 min total per vehicle per day
  C11 FUEL_QUOTA         — estimated fuel ≤ vehicle weekly_fuel_quota_l
"""
from __future__ import annotations

from .models import (
    OrderCandidate,
    TripState,
    VehicleCandidate,
    TravelData,
    ServiceAllowance,
)

# ── Time budget constants (from challenge spec) ───────────────────────────────

FRESH_DAILY_BUDGET_MIN: float = 270.0
STYLE_TECH_DAILY_BUDGET_MIN: float = 480.0

# ── Result type ───────────────────────────────────────────────────────────────

ConstraintResult = tuple[bool, str, str]  # (passed, reason_code, reason_detail)


def _ok() -> ConstraintResult:
    return True, "", ""


def _fail(code: str, detail: str) -> ConstraintResult:
    return False, code, detail


# ── Individual hard constraints ───────────────────────────────────────────────

def check_brand_district(
    order: OrderCandidate,
    trip: TripState,
) -> ConstraintResult:
    """C1 — Brand and district must match the trip."""
    if order.brand != trip.brand:
        return _fail(
            "BRAND_MISMATCH",
            f"Order brand '{order.brand}' does not match trip brand '{trip.brand}'.",
        )
    if order.district != trip.district:
        return _fail(
            "DISTRICT_MISMATCH",
            f"Order district '{order.district}' does not match trip district '{trip.district}'.",
        )
    return _ok()


def check_temperature(
    order: OrderCandidate,
    vehicle: VehicleCandidate,
) -> ConstraintResult:
    """C2 — Chilled orders require reefer vehicle; reefer may carry ambient."""
    if order.temp_requirement == "chilled" and vehicle.temp != "reefer":
        return _fail(
            "NO_REEFER_VEHICLE",
            "Order requires refrigeration but the vehicle is not reefer-capable.",
        )
    return _ok()


def check_van_access(
    order: OrderCandidate,
    vehicle: VehicleCandidate,
) -> ConstraintResult:
    """C3 — van_only outlet requires van vehicle."""
    if order.parking_constraint == "van_only" and vehicle.type != "van":
        return _fail(
            "NO_VAN_AVAILABLE",
            "Outlet requires van-only access but the vehicle is a truck.",
        )
    return _ok()


def check_home_depot(
    order: OrderCandidate,
    vehicle: VehicleCandidate,
) -> ConstraintResult:
    """C4 — Order/outlet depot must equal vehicle home depot."""
    if order.depot != vehicle.depot:
        return _fail(
            "WRONG_DEPOT",
            f"Order depot '{order.depot}' does not match vehicle depot '{vehicle.depot}'.",
        )
    return _ok()


def check_weight_capacity(
    order: OrderCandidate,
    trip: TripState,
    vehicle: VehicleCandidate,
) -> ConstraintResult:
    """C6 — Adding this order must not exceed vehicle weight capacity."""
    new_weight = trip.total_weight_kg + order.total_weight_kg
    if new_weight > vehicle.weight_cap_kg:
        return _fail(
            "CAPACITY_WEIGHT",
            (
                f"Adding {order.total_weight_kg:.2f} kg would bring trip to "
                f"{new_weight:.2f} kg, exceeding the {vehicle.weight_cap_kg:.2f} kg limit."
            ),
        )
    return _ok()


def check_volume_capacity(
    order: OrderCandidate,
    trip: TripState,
    vehicle: VehicleCandidate,
) -> ConstraintResult:
    """C7 — Adding this order must not exceed vehicle volume capacity."""
    new_volume = trip.total_volume_m3 + order.total_volume_m3
    if new_volume > vehicle.volume_cap_m3:
        return _fail(
            "CAPACITY_VOLUME",
            (
                f"Adding {order.total_volume_m3:.3f} m³ would bring trip to "
                f"{new_volume:.3f} m³, exceeding the {vehicle.volume_cap_m3:.3f} m³ limit."
            ),
        )
    return _ok()


def check_max_trips(
    vehicle_id: str,
    existing_trip_count: int,
) -> ConstraintResult:
    """C8 — Vehicle may run at most 2 trips per day."""
    if existing_trip_count >= 2:
        return _fail(
            "TRIP_LIMIT_REACHED",
            f"Vehicle '{vehicle_id}' already has {existing_trip_count} trip(s) planned; maximum is 2.",
        )
    return _ok()


def calculate_trip_duration(
    orders: list[OrderCandidate],
    travel: TravelData,
    service_allowances: dict[tuple[str, str], int],
) -> float:
    """
    Compute estimated trip duration in minutes using the challenge formula.

    trip_minutes =
        depot_to_district_freeflow_min
        + inter_stop_freeflow_min × (number_of_orders − 1)
        + Σ service_allowance_min(brand, dock_type)

    Early arrivals wait until the window opens — this does NOT add waiting time
    to the duration budget, as the budget covers the operational window, not
    the cumulative idle wait.  Window compliance is checked in check_delivery_window.
    """
    if not orders:
        return 0.0

    n = len(orders)
    outbound = travel.depot_to_district_freeflow_min
    inter_stop = travel.inter_stop_freeflow_min * (n - 1)
    handling = sum(
        service_allowances.get((o.brand, o.dock_type), 15) for o in orders
    )
    return outbound + inter_stop + handling


def calculate_trip_distance(
    orders: list[OrderCandidate],
    travel: TravelData,
) -> float:
    """Estimate total one-way trip distance in km."""
    if not orders:
        return 0.0
    n = len(orders)
    return travel.depot_to_district_km + travel.inter_stop_km * (n - 1)


def check_fresh_time_budget(
    new_duration_min: float,
    vehicle_fresh_minutes_used: float,
) -> ConstraintResult:
    """C9 — Fresh trips for this vehicle must not exceed 270 minutes total."""
    if vehicle_fresh_minutes_used + new_duration_min > FRESH_DAILY_BUDGET_MIN:
        return _fail(
            "FRESH_TIME_CAPACITY",
            (
                f"Adding this trip ({new_duration_min:.0f} min) would consume "
                f"{vehicle_fresh_minutes_used + new_duration_min:.0f} min of the "
                f"{FRESH_DAILY_BUDGET_MIN:.0f} min Fresh daily budget."
            ),
        )
    return _ok()


def check_style_tech_time_budget(
    new_duration_min: float,
    vehicle_style_tech_minutes_used: float,
) -> ConstraintResult:
    """C10 — Style + Tech trips for this vehicle must not exceed 480 minutes total."""
    if vehicle_style_tech_minutes_used + new_duration_min > STYLE_TECH_DAILY_BUDGET_MIN:
        return _fail(
            "STYLE_TECH_TIME_CAPACITY",
            (
                f"Adding this trip ({new_duration_min:.0f} min) would consume "
                f"{vehicle_style_tech_minutes_used + new_duration_min:.0f} min of the "
                f"{STYLE_TECH_DAILY_BUDGET_MIN:.0f} min Style/Tech daily budget."
            ),
        )
    return _ok()


def check_fuel_quota(
    estimated_fuel_l: float,
    vehicle: VehicleCandidate,
    fuel_already_used_l: float,
) -> ConstraintResult:
    """C11 — Fuel used by this trip must not exceed vehicle's weekly quota."""
    total = fuel_already_used_l + estimated_fuel_l
    if total > vehicle.weekly_fuel_quota_l:
        return _fail(
            "FUEL_QUOTA_EXCEEDED",
            (
                f"This trip would use {estimated_fuel_l:.1f} L of fuel; "
                f"the vehicle has only {vehicle.weekly_fuel_quota_l - fuel_already_used_l:.1f} L remaining "
                f"of its {vehicle.weekly_fuel_quota_l:.1f} L weekly quota."
            ),
        )
    return _ok()


# ── Composite feasibility check ───────────────────────────────────────────────

def check_order_can_join_trip(
    order: OrderCandidate,
    trip: TripState,
    vehicle: VehicleCandidate,
    additional_orders: list[OrderCandidate],   # orders already in trip as objects
    travel: TravelData,
    service_allowances: dict[tuple[str, str], int],
    vehicle_fresh_minutes_used: float,
    vehicle_style_tech_minutes_used: float,
    vehicle_fuel_used_l: float,
) -> ConstraintResult:
    """
    Run all hard constraints for adding `order` to an existing `trip`.

    Returns the first failure, or _ok() if all pass.
    The order in which constraints are checked is intentional:
    cheapest checks first, then capacity, then time budget.
    """
    for check_fn, args in [
        (check_brand_district,  (order, trip)),
        (check_temperature,     (order, vehicle)),
        (check_van_access,      (order, vehicle)),
        (check_home_depot,      (order, vehicle)),
        (check_weight_capacity, (order, trip, vehicle)),
        (check_volume_capacity, (order, trip, vehicle)),
    ]:
        passed, code, detail = check_fn(*args)
        if not passed:
            return passed, code, detail

    # Recalculate duration with the new order included
    candidate_orders = additional_orders + [order]
    new_duration = calculate_trip_duration(candidate_orders, travel, service_allowances)
    new_distance = calculate_trip_distance(candidate_orders, travel)
    new_fuel = new_distance / vehicle.km_per_l if vehicle.km_per_l > 0 else 0.0

    # Time budget check
    if order.brand == "Fresh":
        # Fresh budget covers all Fresh trips for this vehicle
        existing_fresh_excl_this_trip = vehicle_fresh_minutes_used - trip.estimated_duration_min
        passed, code, detail = check_fresh_time_budget(new_duration, max(0.0, existing_fresh_excl_this_trip))
    else:
        existing_st_excl_this_trip = vehicle_style_tech_minutes_used - trip.estimated_duration_min
        passed, code, detail = check_style_tech_time_budget(new_duration, max(0.0, existing_st_excl_this_trip))
    if not passed:
        return passed, code, detail

    # Fuel check
    fuel_excl_this_trip = vehicle_fuel_used_l - (
        trip.estimated_distance_km / vehicle.km_per_l if vehicle.km_per_l > 0 else 0.0
    )
    passed, code, detail = check_fuel_quota(new_fuel, vehicle, max(0.0, fuel_excl_this_trip))
    return passed, code, detail
