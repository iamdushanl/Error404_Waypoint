"""
Plan validator — proves feasibility of a completed AllocationResult.

This validator is INDEPENDENT of the allocation heuristic.
It can be called on any AllocationResult, including hand-crafted ones.

The validator re-checks every hard constraint against the final plan
and returns a structured ValidationResult.

Design intent:
  ALLOCATION ENGINE
      ↓
  candidate solution

  VALIDATOR
      ↓
  prove feasibility

The planning service calls validate_plan() BEFORE persisting.
If validation fails, nothing is persisted.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import (
    AllocationResult,
    OrderCandidate,
    TripResult,
    VehicleCandidate,
    TravelData,
    ServiceAllowance,
)
from .constraints import (
    FRESH_DAILY_BUDGET_MIN,
    STYLE_TECH_DAILY_BUDGET_MIN,
    calculate_trip_duration,
)


@dataclass
class Violation:
    trip_vehicle_id: str
    trip_number: int
    constraint: str
    detail: str


@dataclass
class ValidationResult:
    valid: bool
    violations: list[Violation] = field(default_factory=list)

    def add(self, vehicle_id: str, trip_num: int, constraint: str, detail: str) -> None:
        self.violations.append(Violation(vehicle_id, trip_num, constraint, detail))
        self.valid = False


def validate_plan(
    result: AllocationResult,
    order_lookup: dict[str, OrderCandidate],
    vehicle_lookup: dict[str, VehicleCandidate],
    travel_lookup: dict[tuple[str, str], TravelData],
    service_allowance_lookup: dict[tuple[str, str], int],
) -> ValidationResult:
    """
    Prove that every trip in the AllocationResult satisfies all hard constraints.

    Args:
        result:                   The AllocationResult to validate.
        order_lookup:             order_id → OrderCandidate
        vehicle_lookup:           vehicle_id → VehicleCandidate
        travel_lookup:            (district, depot) → TravelData
        service_allowance_lookup: (brand, dock_type) → minutes

    Returns:
        ValidationResult(valid=True) if all checks pass.
        ValidationResult(valid=False, violations=[...]) on failure.
    """
    vr = ValidationResult(valid=True)

    # Track per-vehicle aggregate state for budget constraints
    vehicle_trip_counts: dict[str, int] = {}
    vehicle_fresh_min: dict[str, float] = {}
    vehicle_st_min: dict[str, float] = {}
    vehicle_fuel_l: dict[str, float] = {}

    # Track orders that appear in trips (for whole-order constraint)
    order_trip_membership: dict[str, list[str]] = {}  # order_id → list of trip identifiers

    for trip in result.trips:
        vid = trip.vehicle_id
        trip_label = f"vehicle={vid} trip#{trip.trip_number}"
        vehicle = vehicle_lookup.get(vid)

        if vehicle is None:
            vr.add(vid, trip.trip_number, "VEHICLE_EXISTS", f"Vehicle '{vid}' not found in lookup.")
            continue

        # Track trip count
        vehicle_trip_counts[vid] = vehicle_trip_counts.get(vid, 0) + 1

        if vehicle_trip_counts[vid] > 2:
            vr.add(vid, trip.trip_number, "MAX_TRIPS",
                   f"Vehicle has {vehicle_trip_counts[vid]} trips; maximum is 2.")

        # Empty trip check
        if not trip.orders:
            vr.add(vid, trip.trip_number, "EMPTY_TRIP", "Trip has no orders.")
            continue

        # Validate per-order constraints
        total_weight = 0.0
        total_volume = 0.0
        order_objects: list[OrderCandidate] = []

        for oid in trip.orders:
            order = order_lookup.get(oid)
            if order is None:
                vr.add(vid, trip.trip_number, "ORDER_EXISTS", f"Order '{oid}' not in lookup.")
                continue

            order_objects.append(order)

            # C1 — Brand + district
            if order.brand != trip.brand:
                vr.add(vid, trip.trip_number, "BRAND_MISMATCH",
                       f"Order {oid} brand '{order.brand}' ≠ trip brand '{trip.brand}'.")
            if order.district != trip.district:
                vr.add(vid, trip.trip_number, "DISTRICT_MISMATCH",
                       f"Order {oid} district '{order.district}' ≠ trip district '{trip.district}'.")

            # C2 — Temperature
            if order.temp_requirement == "chilled" and vehicle.temp != "reefer":
                vr.add(vid, trip.trip_number, "TEMPERATURE",
                       f"Order {oid} requires reefer but vehicle temp is '{vehicle.temp}'.")

            # C3 — Van access
            if order.parking_constraint == "van_only" and vehicle.type != "van":
                vr.add(vid, trip.trip_number, "VAN_ACCESS",
                       f"Order {oid} outlet is van_only but vehicle type is '{vehicle.type}'.")

            # C4 — Home depot
            if order.depot != vehicle.depot:
                vr.add(vid, trip.trip_number, "HOME_DEPOT",
                       f"Order {oid} depot '{order.depot}' ≠ vehicle depot '{vehicle.depot}'.")

            # C5 — Whole order (track membership)
            if oid not in order_trip_membership:
                order_trip_membership[oid] = []
            order_trip_membership[oid].append(trip_label)

            total_weight += order.total_weight_kg
            total_volume += order.total_volume_m3

        # C6 — Weight capacity
        if total_weight > vehicle.weight_cap_kg + 1e-6:
            vr.add(vid, trip.trip_number, "WEIGHT_CAPACITY",
                   f"Trip total weight {total_weight:.2f} kg > capacity {vehicle.weight_cap_kg:.2f} kg.")

        # C7 — Volume capacity
        if total_volume > vehicle.volume_cap_m3 + 1e-6:
            vr.add(vid, trip.trip_number, "VOLUME_CAPACITY",
                   f"Trip total volume {total_volume:.3f} m³ > capacity {vehicle.volume_cap_m3:.3f} m³.")

        # C9/C10 — Time budget
        travel = travel_lookup.get((trip.district, trip.depot))
        if travel is None:
            vr.add(vid, trip.trip_number, "TRAVEL_DATA",
                   f"No travel data for district '{trip.district}' depot '{trip.depot}'.")
        else:
            duration = calculate_trip_duration(order_objects, travel, service_allowance_lookup)
            if trip.brand == "Fresh":
                vehicle_fresh_min[vid] = vehicle_fresh_min.get(vid, 0.0) + duration
                if vehicle_fresh_min[vid] > FRESH_DAILY_BUDGET_MIN + 1e-6:
                    vr.add(vid, trip.trip_number, "FRESH_TIME_BUDGET",
                           f"Cumulative Fresh time {vehicle_fresh_min[vid]:.1f} min "
                           f"> {FRESH_DAILY_BUDGET_MIN:.0f} min budget.")
            else:
                vehicle_st_min[vid] = vehicle_st_min.get(vid, 0.0) + duration
                if vehicle_st_min[vid] > STYLE_TECH_DAILY_BUDGET_MIN + 1e-6:
                    vr.add(vid, trip.trip_number, "STYLE_TECH_TIME_BUDGET",
                           f"Cumulative Style/Tech time {vehicle_st_min[vid]:.1f} min "
                           f"> {STYLE_TECH_DAILY_BUDGET_MIN:.0f} min budget.")

        # C11 — Fuel quota
        if vehicle.km_per_l > 0 and trip.estimated_distance_km > 0:
            fuel = trip.estimated_distance_km / vehicle.km_per_l
            vehicle_fuel_l[vid] = vehicle_fuel_l.get(vid, 0.0) + fuel
            if vehicle_fuel_l[vid] > vehicle.weekly_fuel_quota_l + 1e-6:
                vr.add(vid, trip.trip_number, "FUEL_QUOTA",
                       f"Cumulative fuel {vehicle_fuel_l[vid]:.2f} L "
                       f"> weekly quota {vehicle.weekly_fuel_quota_l:.2f} L.")

    # C5 — Whole order: each order appears in exactly one trip
    for oid, memberships in order_trip_membership.items():
        if len(memberships) > 1:
            vr.add("*", 0, "WHOLE_ORDER",
                   f"Order {oid} appears in multiple trips: {memberships}.")

    return vr
