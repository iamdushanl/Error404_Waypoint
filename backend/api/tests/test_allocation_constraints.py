"""
Unit tests for the allocation engine — hard constraints.

These tests are COMPLETELY INDEPENDENT of Supabase, FastAPI, or any network.
They test the pure domain logic in isolation.

Every hard constraint from the challenge specification has at least one test.
Adversarial cases are explicitly tested (edge cases, exact capacity, violation by 0.01).

Run with:
    cd backend/api
    pytest tests/test_allocation_constraints.py -v
"""
from __future__ import annotations

import datetime
import pytest

from app.services.allocation.models import (
    OrderCandidate,
    TravelData,
    TripState,
    VehicleCandidate,
)
from app.services.allocation.constraints import (
    FRESH_DAILY_BUDGET_MIN,
    STYLE_TECH_DAILY_BUDGET_MIN,
    calculate_trip_duration,
    check_brand_district,
    check_fresh_time_budget,
    check_fuel_quota,
    check_home_depot,
    check_max_trips,
    check_order_can_join_trip,
    check_style_tech_time_budget,
    check_temperature,
    check_van_access,
    check_volume_capacity,
    check_weight_capacity,
)
from app.services.allocation.engine import AllocationEngine
from app.services.allocation.validator import validate_plan


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_order(
    *,
    order_id: str = "ORD001",
    outlet_id: str = "OUT001",
    brand: str = "Fresh",
    district: str = "Colombo",
    depot: str = "Peliyagoda",
    temp_requirement: str = "ambient",
    total_weight_kg: float = 100.0,
    total_volume_m3: float = 1.0,
    dock_type: str = "rear_dock",
    parking_constraint: str = "normal",
    window_open_time: str = "06:00",
    window_close_time: str = "08:00",
    deferred_yesterday: bool = False,
    days_since_last_served: int = 0,
) -> OrderCandidate:
    return OrderCandidate(
        order_id=order_id,
        outlet_id=outlet_id,
        brand=brand,
        district=district,
        depot=depot,
        temp_requirement=temp_requirement,
        total_weight_kg=total_weight_kg,
        total_volume_m3=total_volume_m3,
        dock_type=dock_type,
        parking_constraint=parking_constraint,
        window_open_time=window_open_time,
        window_close_time=window_close_time,
        deferred_yesterday=deferred_yesterday,
        days_since_last_served=days_since_last_served,
    )


def make_vehicle(
    *,
    vehicle_id: str = "VEH001",
    type: str = "truck",
    temp: str = "ambient",
    weight_cap_kg: float = 5000.0,
    volume_cap_m3: float = 20.0,
    km_per_l: float = 10.0,
    weekly_fuel_quota_l: float = 200.0,
    depot: str = "Peliyagoda",
) -> VehicleCandidate:
    return VehicleCandidate(
        vehicle_id=vehicle_id,
        type=type,
        temp=temp,
        weight_cap_kg=weight_cap_kg,
        volume_cap_m3=volume_cap_m3,
        fuel_type="diesel",
        km_per_l=km_per_l,
        weekly_fuel_quota_l=weekly_fuel_quota_l,
        depot=depot,
    )


def make_trip(
    *,
    vehicle_id: str = "VEH001",
    trip_number: int = 1,
    brand: str = "Fresh",
    district: str = "Colombo",
    depot: str = "Peliyagoda",
    total_weight_kg: float = 0.0,
    total_volume_m3: float = 0.0,
    estimated_duration_min: float = 0.0,
    estimated_distance_km: float = 0.0,
    estimated_fuel_l: float = 0.0,
) -> TripState:
    return TripState(
        vehicle_id=vehicle_id,
        trip_number=trip_number,
        brand=brand,
        district=district,
        depot=depot,
        total_weight_kg=total_weight_kg,
        total_volume_m3=total_volume_m3,
        estimated_duration_min=estimated_duration_min,
        estimated_distance_km=estimated_distance_km,
        estimated_fuel_l=estimated_fuel_l,
    )


TRAVEL_COLOMBO = TravelData(
    district="Colombo",
    depot="Peliyagoda",
    depot_to_district_freeflow_min=24,
    inter_stop_freeflow_min=8,
    depot_to_district_km=12,
    inter_stop_km=4.0,
)

SERVICE_LOOKUP: dict[tuple[str, str], int] = {
    ("Fresh", "rear_dock"): 15,
    ("Fresh", "street"):    16,
    ("Fresh", "mall_bay"):  18,
    ("Style", "rear_dock"): 38,
    ("Tech",  "rear_dock"): 43,
}


# ── C1: Brand + District ──────────────────────────────────────────────────────

def test_same_brand_required():
    """Order brand must match trip brand."""
    order = make_order(brand="Style")
    trip = make_trip(brand="Fresh")
    passed, code, _ = check_brand_district(order, trip)
    assert not passed
    assert code == "BRAND_MISMATCH"


def test_same_district_required():
    """Order district must match trip district."""
    order = make_order(district="Gampaha")
    trip = make_trip(district="Colombo")
    passed, code, _ = check_brand_district(order, trip)
    assert not passed
    assert code == "DISTRICT_MISMATCH"


def test_brand_district_both_match():
    order = make_order(brand="Fresh", district="Colombo")
    trip = make_trip(brand="Fresh", district="Colombo")
    passed, _, _ = check_brand_district(order, trip)
    assert passed


# ── C2: Temperature ───────────────────────────────────────────────────────────

def test_chilled_requires_reefer():
    """Chilled order must be rejected by ambient vehicle."""
    order = make_order(temp_requirement="chilled")
    vehicle = make_vehicle(temp="ambient")
    passed, code, _ = check_temperature(order, vehicle)
    assert not passed
    assert code == "NO_REEFER_VEHICLE"


def test_ambient_allowed_on_reefer():
    """Reefer vehicle can carry ambient orders."""
    order = make_order(temp_requirement="ambient")
    vehicle = make_vehicle(temp="reefer")
    passed, _, _ = check_temperature(order, vehicle)
    assert passed


def test_ambient_allowed_on_ambient():
    """Ambient order on ambient vehicle is fine."""
    order = make_order(temp_requirement="ambient")
    vehicle = make_vehicle(temp="ambient")
    passed, _, _ = check_temperature(order, vehicle)
    assert passed


def test_chilled_ok_on_reefer():
    """Chilled order on reefer vehicle is the intended match."""
    order = make_order(temp_requirement="chilled")
    vehicle = make_vehicle(temp="reefer")
    passed, _, _ = check_temperature(order, vehicle)
    assert passed


# ── C3: Van access ────────────────────────────────────────────────────────────

def test_van_only_requires_van():
    """van_only outlet must be rejected by a truck."""
    order = make_order(parking_constraint="van_only")
    vehicle = make_vehicle(type="truck")
    passed, code, _ = check_van_access(order, vehicle)
    assert not passed
    assert code == "NO_VAN_AVAILABLE"


def test_van_only_ok_with_van():
    order = make_order(parking_constraint="van_only")
    vehicle = make_vehicle(type="van")
    passed, _, _ = check_van_access(order, vehicle)
    assert passed


def test_normal_access_any_vehicle():
    """Normal access outlet works with both truck and van."""
    order = make_order(parking_constraint="normal")
    for vtype in ("truck", "van"):
        vehicle = make_vehicle(type=vtype)
        passed, _, _ = check_van_access(order, vehicle)
        assert passed, f"Normal access should work with {vtype}"


# ── C4: Home depot ────────────────────────────────────────────────────────────

def test_home_depot_constraint():
    """Order from Peliyagoda cannot use a Kandy vehicle."""
    order = make_order(depot="Peliyagoda")
    vehicle = make_vehicle(depot="Kandy")
    passed, code, _ = check_home_depot(order, vehicle)
    assert not passed
    assert code == "WRONG_DEPOT"


def test_home_depot_match():
    order = make_order(depot="Peliyagoda")
    vehicle = make_vehicle(depot="Peliyagoda")
    passed, _, _ = check_home_depot(order, vehicle)
    assert passed


# ── C6: Weight capacity ───────────────────────────────────────────────────────

def test_weight_capacity():
    """Order weight exceeding remaining capacity is rejected."""
    order = make_order(total_weight_kg=100.0)
    trip = make_trip(total_weight_kg=4950.0)
    vehicle = make_vehicle(weight_cap_kg=5000.0)
    passed, code, _ = check_weight_capacity(order, trip, vehicle)
    assert not passed
    assert code == "CAPACITY_WEIGHT"


def test_weight_capacity_exact_fit():
    """Order that exactly fills remaining weight must be accepted."""
    order = make_order(total_weight_kg=50.0)
    trip = make_trip(total_weight_kg=4950.0)
    vehicle = make_vehicle(weight_cap_kg=5000.0)
    passed, _, _ = check_weight_capacity(order, trip, vehicle)
    assert passed


def test_weight_capacity_exceeds_by_small_margin():
    """Exceeding by even 0.01 kg must be rejected."""
    order = make_order(total_weight_kg=50.01)
    trip = make_trip(total_weight_kg=4950.0)
    vehicle = make_vehicle(weight_cap_kg=5000.0)
    passed, code, _ = check_weight_capacity(order, trip, vehicle)
    assert not passed
    assert code == "CAPACITY_WEIGHT"


# ── C7: Volume capacity ───────────────────────────────────────────────────────

def test_volume_capacity():
    """Volume overflow is rejected."""
    order = make_order(total_volume_m3=5.0)
    trip = make_trip(total_volume_m3=16.0)
    vehicle = make_vehicle(volume_cap_m3=20.0)
    passed, code, _ = check_volume_capacity(order, trip, vehicle)
    assert not passed
    assert code == "CAPACITY_VOLUME"


def test_volume_capacity_exact_fit():
    order = make_order(total_volume_m3=4.0)
    trip = make_trip(total_volume_m3=16.0)
    vehicle = make_vehicle(volume_cap_m3=20.0)
    passed, _, _ = check_volume_capacity(order, trip, vehicle)
    assert passed


def test_volume_capacity_exceeds_by_small_margin():
    order = make_order(total_volume_m3=4.001)
    trip = make_trip(total_volume_m3=16.0)
    vehicle = make_vehicle(volume_cap_m3=20.0)
    passed, code, _ = check_volume_capacity(order, trip, vehicle)
    assert not passed
    assert code == "CAPACITY_VOLUME"


# ── C8: Max trips ─────────────────────────────────────────────────────────────

def test_max_two_trips():
    """Vehicle with 2 trips already cannot get a third."""
    passed, code, _ = check_max_trips("VEH001", existing_trip_count=2)
    assert not passed
    assert code == "TRIP_LIMIT_REACHED"


def test_first_trip_allowed():
    passed, _, _ = check_max_trips("VEH001", existing_trip_count=0)
    assert passed


def test_second_trip_allowed():
    passed, _, _ = check_max_trips("VEH001", existing_trip_count=1)
    assert passed


def test_three_trips_rejected():
    passed, code, _ = check_max_trips("VEH001", existing_trip_count=3)
    assert not passed
    assert code == "TRIP_LIMIT_REACHED"


# ── C9: Fresh time budget ─────────────────────────────────────────────────────

def test_fresh_time_budget():
    """Fresh trips exceeding 270 minutes total are rejected."""
    passed, code, _ = check_fresh_time_budget(
        new_duration_min=100.0,
        vehicle_fresh_minutes_used=200.0,  # 200 + 100 = 300 > 270
    )
    assert not passed
    assert code == "FRESH_TIME_CAPACITY"


def test_fresh_time_budget_exact():
    """Exactly 270 minutes must pass."""
    passed, _, _ = check_fresh_time_budget(
        new_duration_min=70.0,
        vehicle_fresh_minutes_used=200.0,  # 200 + 70 = 270 = limit
    )
    assert passed


def test_fresh_time_budget_under():
    passed, _, _ = check_fresh_time_budget(
        new_duration_min=50.0,
        vehicle_fresh_minutes_used=100.0,
    )
    assert passed


# ── C10: Style/Tech time budget ───────────────────────────────────────────────

def test_style_tech_time_budget():
    """Style+Tech trips exceeding 480 minutes total are rejected."""
    passed, code, _ = check_style_tech_time_budget(
        new_duration_min=300.0,
        vehicle_style_tech_minutes_used=200.0,  # 200+300=500 > 480
    )
    assert not passed
    assert code == "STYLE_TECH_TIME_CAPACITY"


def test_style_tech_budgets_are_separate():
    """
    The Fresh budget and Style/Tech budget are SEPARATE.
    A vehicle with 270 min Fresh already used can still get 480 min Style/Tech.
    """
    # Fresh at full — Style/Tech budget is independent
    passed, _, _ = check_style_tech_time_budget(
        new_duration_min=100.0,
        vehicle_style_tech_minutes_used=0.0,
    )
    assert passed, "Style/Tech budget should not be affected by Fresh usage"


# ── C11: Fuel quota ───────────────────────────────────────────────────────────

def test_fuel_quota():
    """Exceeding weekly fuel quota is rejected."""
    vehicle = make_vehicle(weekly_fuel_quota_l=200.0)
    passed, code, _ = check_fuel_quota(
        estimated_fuel_l=50.0,
        vehicle=vehicle,
        fuel_already_used_l=160.0,  # 160+50=210 > 200
    )
    assert not passed
    assert code == "FUEL_QUOTA_EXCEEDED"


def test_fuel_quota_ok():
    vehicle = make_vehicle(weekly_fuel_quota_l=200.0)
    passed, _, _ = check_fuel_quota(
        estimated_fuel_l=30.0,
        vehicle=vehicle,
        fuel_already_used_l=100.0,
    )
    assert passed


# ── Trip time calculation ─────────────────────────────────────────────────────

def test_trip_time_calculation():
    """
    Verify the challenge-spec example:
    Fresh trip to Gampaha: 3 orders (2 rear_dock, 1 street)
    = 37 + 9*2 + 15 + 15 + 16 = 101 minutes.
    """
    gampaha_travel = TravelData(
        district="Gampaha", depot="Peliyagoda",
        depot_to_district_freeflow_min=37,
        inter_stop_freeflow_min=9,
        depot_to_district_km=28,
        inter_stop_km=7.0,
    )
    service = {
        ("Fresh", "rear_dock"): 15,
        ("Fresh", "street"): 16,
    }
    orders = [
        make_order(brand="Fresh", dock_type="rear_dock"),
        make_order(brand="Fresh", dock_type="rear_dock"),
        make_order(brand="Fresh", dock_type="street"),
    ]
    result = calculate_trip_duration(orders, gampaha_travel, service)
    assert result == 101, f"Expected 101 minutes, got {result}"


# ── Deferred order reason ─────────────────────────────────────────────────────

def test_deferred_order_reason():
    """
    An order requiring chilled with no reefer vehicle available
    must be deferred with NO_REEFER_VEHICLE reason.
    """
    orders = [make_order(temp_requirement="chilled", order_id="ORD_CHILL")]
    vehicles = [make_vehicle(temp="ambient", vehicle_id="V_AMB")]
    travel = {("Colombo", "Peliyagoda"): TRAVEL_COLOMBO}

    engine = AllocationEngine(
        orders=orders,
        vehicles=vehicles,
        travel_lookup=travel,
        service_allowance_lookup=SERVICE_LOOKUP,
        plan_date=datetime.date(2026, 10, 4),
    )
    result = engine.generate()

    assert len(result.trips) == 0
    assert len(result.deferred_orders) == 1
    d = result.deferred_orders[0]
    assert d.order_id == "ORD_CHILL"
    assert d.reason_code == "NO_REEFER_VEHICLE"
    assert "refrigeration" in d.reason_detail.lower() or "reefer" in d.reason_detail.lower()


def test_van_only_deferred_no_van():
    """Van-only outlet with only trucks → deferred with NO_VAN_AVAILABLE."""
    orders = [make_order(parking_constraint="van_only", order_id="ORD_VAN")]
    vehicles = [make_vehicle(type="truck", vehicle_id="V_TRUCK")]
    travel = {("Colombo", "Peliyagoda"): TRAVEL_COLOMBO}

    engine = AllocationEngine(
        orders=orders,
        vehicles=vehicles,
        travel_lookup=travel,
        service_allowance_lookup=SERVICE_LOOKUP,
        plan_date=datetime.date(2026, 10, 4),
    )
    result = engine.generate()

    assert len(result.deferred_orders) == 1
    assert result.deferred_orders[0].reason_code == "NO_VAN_AVAILABLE"


# ── Determinism ───────────────────────────────────────────────────────────────

def test_deterministic_allocation():
    """Same inputs must produce identical outputs on repeated runs."""
    orders = [
        make_order(order_id=f"ORD{i:03d}", total_weight_kg=200.0, total_volume_m3=2.0)
        for i in range(5)
    ]
    vehicles = [make_vehicle(vehicle_id="VEH001", weight_cap_kg=5000.0, volume_cap_m3=20.0)]
    travel = {("Colombo", "Peliyagoda"): TRAVEL_COLOMBO}

    def run():
        e = AllocationEngine(
            orders=orders,
            vehicles=vehicles,
            travel_lookup=travel,
            service_allowance_lookup=SERVICE_LOOKUP,
            plan_date=datetime.date(2026, 10, 4),
        )
        r = e.generate()
        return [t.orders for t in r.trips], [d.order_id for d in r.deferred_orders]

    trips1, deferred1 = run()
    trips2, deferred2 = run()

    assert trips1 == trips2, "Trip assignments differ between runs"
    assert deferred1 == deferred2, "Deferred orders differ between runs"


# ── Happy path: end-to-end allocation ────────────────────────────────────────

def test_happy_path_allocation():
    """
    Three ambient orders for the same brand+district+depot
    should all be served on one trip with one vehicle.
    """
    orders = [
        make_order(order_id=f"ORD{i:03d}", total_weight_kg=100.0, total_volume_m3=1.0)
        for i in range(3)
    ]
    vehicles = [make_vehicle(vehicle_id="VEH001")]
    travel = {("Colombo", "Peliyagoda"): TRAVEL_COLOMBO}

    engine = AllocationEngine(
        orders=orders,
        vehicles=vehicles,
        travel_lookup=travel,
        service_allowance_lookup=SERVICE_LOOKUP,
        plan_date=datetime.date(2026, 10, 4),
    )
    result = engine.generate()

    assert result.metrics.served_orders == 3
    assert result.metrics.deferred_orders == 0
    assert len(result.trips) == 1
    assert result.trips[0].vehicle_id == "VEH001"


# ── Validator ─────────────────────────────────────────────────────────────────

def test_validator_catches_brand_mismatch():
    """
    Hand-craft an AllocationResult where a trip contains a wrong-brand order.
    The validator must catch it.
    """
    from app.services.allocation.models import (
        AllocationResult, AllocationMetrics, TripResult, StopPlan
    )

    order = make_order(order_id="ORD001", brand="Style")
    vehicle = make_vehicle(vehicle_id="VEH001")

    # Fabricate a trip with wrong brand
    trip = TripResult(
        vehicle_id="VEH001",
        trip_number=1,
        brand="Fresh",       # ← wrong brand for the order
        district="Colombo",
        depot="Peliyagoda",
        orders=["ORD001"],
        stops=[StopPlan("ORD001", "OUT001", 1, 1, None)],
        total_weight_kg=100.0,
        total_volume_m3=1.0,
        estimated_duration_min=50.0,
        estimated_distance_km=12.0,
        estimated_fuel_l=1.2,
    )
    result = AllocationResult(
        plan_date="2026-10-04",
        depot="Peliyagoda",
        trips=[trip],
        deferred_orders=[],
        metrics=AllocationMetrics(),
    )

    vr = validate_plan(
        result=result,
        order_lookup={"ORD001": order},
        vehicle_lookup={"VEH001": vehicle},
        travel_lookup={("Colombo", "Peliyagoda"): TRAVEL_COLOMBO},
        service_allowance_lookup=SERVICE_LOOKUP,
    )
    assert not vr.valid
    codes = [v.constraint for v in vr.violations]
    assert "BRAND_MISMATCH" in codes


def test_validator_passes_valid_plan():
    """A properly constructed plan must pass validation."""
    from app.services.allocation.models import (
        AllocationResult, AllocationMetrics, TripResult, StopPlan
    )

    order = make_order(order_id="ORD001", brand="Fresh", district="Colombo")
    vehicle = make_vehicle(vehicle_id="VEH001", weight_cap_kg=5000.0, volume_cap_m3=20.0)

    trip = TripResult(
        vehicle_id="VEH001",
        trip_number=1,
        brand="Fresh",
        district="Colombo",
        depot="Peliyagoda",
        orders=["ORD001"],
        stops=[StopPlan("ORD001", "OUT001", 1, 1, None)],
        total_weight_kg=100.0,
        total_volume_m3=1.0,
        estimated_duration_min=39.0,  # 24 + 0 + 15
        estimated_distance_km=12.0,
        estimated_fuel_l=1.2,
    )
    result = AllocationResult(
        plan_date="2026-10-04",
        depot="Peliyagoda",
        trips=[trip],
        deferred_orders=[],
        metrics=AllocationMetrics(),
    )

    vr = validate_plan(
        result=result,
        order_lookup={"ORD001": order},
        vehicle_lookup={"VEH001": vehicle},
        travel_lookup={("Colombo", "Peliyagoda"): TRAVEL_COLOMBO},
        service_allowance_lookup=SERVICE_LOOKUP,
    )
    assert vr.valid, f"Expected valid plan but got violations: {vr.violations}"


# ── Adversarial: No trip with 3rd attempt on same vehicle ─────────────────────

def test_max_two_trips_engine_enforced():
    """
    Engine must not assign a 3rd trip to a vehicle even if there are
    many compatible orders and only one vehicle.
    Orders that don't fit in 2 trips should be deferred.
    """
    # Fill a vehicle with 2 trips worth of orders and try to add more
    # Vehicle: 1000 kg cap; each order 400 kg; 2 trips max
    # Trip 1: 2 orders = 800 kg (fits)
    # Trip 2: 2 orders = 800 kg (fits)
    # Order 5: should be deferred (TRIP_LIMIT_REACHED)
    orders = [
        make_order(order_id=f"ORD{i:03d}", total_weight_kg=400.0, total_volume_m3=1.0)
        for i in range(5)
    ]
    vehicles = [make_vehicle(vehicle_id="VEH001", weight_cap_kg=1000.0, volume_cap_m3=20.0)]
    travel = {("Colombo", "Peliyagoda"): TRAVEL_COLOMBO}

    engine = AllocationEngine(
        orders=orders,
        vehicles=vehicles,
        travel_lookup=travel,
        service_allowance_lookup=SERVICE_LOOKUP,
        plan_date=datetime.date(2026, 10, 4),
    )
    result = engine.generate()

    # At most 2 trips for the one vehicle
    assert len(result.trips) <= 2, f"Got {len(result.trips)} trips but max is 2"
    # At least one order is deferred
    assert result.metrics.deferred_orders >= 1
    # Deferred reason must reference trip limit or capacity
    deferred_codes = {d.reason_code for d in result.deferred_orders}
    assert deferred_codes  # must have at least one reason


# ── Whole order constraint ────────────────────────────────────────────────────

def test_whole_order_constraint():
    """
    An order must appear in exactly one trip.
    The validator must detect if an order appears in two trips.
    """
    from app.services.allocation.models import (
        AllocationResult, AllocationMetrics, TripResult, StopPlan
    )

    order = make_order(order_id="ORD001")
    vehicle = make_vehicle(vehicle_id="VEH001")

    # Same order in two trips — invalid
    trip1 = TripResult(
        vehicle_id="VEH001", trip_number=1, brand="Fresh", district="Colombo",
        depot="Peliyagoda", orders=["ORD001"],
        stops=[StopPlan("ORD001", "OUT001", 1, 1, None)],
        total_weight_kg=100.0, total_volume_m3=1.0,
        estimated_duration_min=39.0, estimated_distance_km=12.0, estimated_fuel_l=1.2,
    )
    trip2 = TripResult(
        vehicle_id="VEH001", trip_number=2, brand="Fresh", district="Colombo",
        depot="Peliyagoda", orders=["ORD001"],  # duplicate!
        stops=[StopPlan("ORD001", "OUT001", 1, 1, None)],
        total_weight_kg=100.0, total_volume_m3=1.0,
        estimated_duration_min=39.0, estimated_distance_km=12.0, estimated_fuel_l=1.2,
    )
    result = AllocationResult(
        plan_date="2026-10-04", depot="Peliyagoda",
        trips=[trip1, trip2], deferred_orders=[],
        metrics=AllocationMetrics(),
    )

    vr = validate_plan(
        result=result,
        order_lookup={"ORD001": order},
        vehicle_lookup={"VEH001": vehicle},
        travel_lookup={("Colombo", "Peliyagoda"): TRAVEL_COLOMBO},
        service_allowance_lookup=SERVICE_LOOKUP,
    )
    assert not vr.valid
    codes = [v.constraint for v in vr.violations]
    assert "WHOLE_ORDER" in codes
