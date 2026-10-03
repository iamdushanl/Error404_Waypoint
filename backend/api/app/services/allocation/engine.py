"""
Allocation engine — core greedy/constructive heuristic.

Architecture:
  - AllocationEngine is a pure function object.
  - It accepts domain inputs (no Supabase, no HTTP).
  - It returns AllocationResult (no DB mutations).
  - The planning service is responsible for persistence.

Algorithm summary:

  STEP 1  Score and sort all candidate orders (prioritization policy).
  STEP 2  For each order (priority descending):
    a. Find the best existing trip this order can join.
    b. If no existing trip fits, try to open a new trip on a suitable vehicle.
    c. If still no placement, mark the order deferred with an explicit reason.
  STEP 3  Freeze all TripStates into TripResult objects.
  STEP 4  Compute metrics.
  STEP 5  Return AllocationResult.

Trip placement strategy (when multiple choices exist):
  Prefer the trip with the least incremental duration added.
  If equal, prefer least incremental volume utilization.
  If equal, prefer least incremental weight utilization.
  If equal, prefer the vehicle_id that sorts first (deterministic).

This is a greedy constructive heuristic.  It is not globally optimal.
It is correct (all hard constraints are enforced), deterministic, and
independently verifiable.
"""
from __future__ import annotations

import datetime
import logging
from typing import Optional

from .constraints import (
    FRESH_DAILY_BUDGET_MIN,
    STYLE_TECH_DAILY_BUDGET_MIN,
    calculate_trip_distance,
    calculate_trip_duration,
    check_brand_district,
    check_fuel_quota,
    check_fresh_time_budget,
    check_home_depot,
    check_max_trips,
    check_order_can_join_trip,
    check_style_tech_time_budget,
    check_temperature,
    check_van_access,
    check_volume_capacity,
    check_weight_capacity,
)
from .models import (
    AllocationMetrics,
    AllocationResult,
    DeferredOrderResult,
    OrderCandidate,
    ServiceAllowance,
    StopPlan,
    TravelData,
    TripResult,
    TripState,
    VehicleCandidate,
)
from .prioritization import sort_orders

log = logging.getLogger(__name__)


class AllocationEngine:
    """
    Constraint-aware delivery planning engine.

    Usage:
        engine = AllocationEngine(
            orders=orders,
            vehicles=vehicles,
            travel_lookup=travel_lookup,
            service_allowance_lookup=service_allowance_lookup,
            plan_date=plan_date,
        )
        result = engine.generate()

    The engine never touches the database.
    """

    def __init__(
        self,
        orders: list[OrderCandidate],
        vehicles: list[VehicleCandidate],
        travel_lookup: dict[tuple[str, str], TravelData],
        service_allowance_lookup: dict[tuple[str, str], int],
        plan_date: datetime.date,
    ) -> None:
        self._orders = orders
        self._vehicles = {v.vehicle_id: v for v in vehicles}
        self._travel = travel_lookup           # (district, depot) → TravelData
        self._service = service_allowance_lookup  # (brand, dock_type) → minutes
        self._plan_date = plan_date

        # In-progress trips keyed by vehicle_id → list[TripState]
        self._trips: dict[str, list[TripState]] = {}

        # Orders already placed (set of order_id)
        self._placed: set[str] = set()

    # ── Public API ────────────────────────────────────────────────────────────

    def generate(self) -> AllocationResult:
        """Run the full allocation and return the result."""
        log.info(
            "Allocation started",
            extra={
                "plan_date": str(self._plan_date),
                "order_count": len(self._orders),
                "vehicle_count": len(self._vehicles),
            },
        )

        # STEP 1 — Sort orders by priority
        prioritized = sort_orders(self._orders, self._plan_date)

        deferred: list[DeferredOrderResult] = []

        # STEP 2 — Greedy placement
        for order in prioritized:
            if order.order_id in self._placed:
                continue  # safety guard against duplicates in input

            reason = self._place_order(order)
            if reason:
                deferred.append(reason)
                log.debug(
                    "Order deferred",
                    extra={"order_id": order.order_id, "reason": reason.reason_code},
                )

        # STEP 3 — Freeze trips into results
        trip_results = self._freeze_trips()

        # STEP 4 — Compute metrics
        metrics = self._compute_metrics(trip_results, deferred)

        log.info(
            "Allocation complete",
            extra={
                "served": metrics.served_orders,
                "deferred": metrics.deferred_orders,
                "trips": metrics.trips_created,
            },
        )

        return AllocationResult(
            plan_date=str(self._plan_date),
            depot=self._detect_depot(),
            status="generated",
            trips=trip_results,
            deferred_orders=deferred,
            metrics=metrics,
        )

    # ── Placement logic ───────────────────────────────────────────────────────

    def _place_order(self, order: OrderCandidate) -> Optional[DeferredOrderResult]:
        """
        Try to place order in the best existing trip, then in a new trip.
        Returns DeferredOrderResult if no placement is found.
        """
        travel = self._travel.get((order.district, order.depot))
        if travel is None:
            return DeferredOrderResult(
                order_id=order.order_id,
                reason_code="NO_ELIGIBLE_VEHICLE",
                reason_detail=(
                    f"No travel data found for district '{order.district}' "
                    f"from depot '{order.depot}'. Cannot calculate trip duration."
                ),
            )

        # Check if a single order would ever fit in ANY vehicle on its own
        pre_filter_reason = self._pre_filter_order(order, travel)
        if pre_filter_reason:
            return pre_filter_reason

        # Try to add to an existing compatible trip
        best_trip, best_vehicle = self._find_best_existing_trip(order, travel)
        if best_trip is not None and best_vehicle is not None:
            self._add_order_to_trip(order, best_trip, best_vehicle, travel)
            self._placed.add(order.order_id)
            return None

        # Try to open a new trip
        new_trip_result = self._open_new_trip(order, travel)
        if new_trip_result:
            new_trip, vehicle = new_trip_result
            self._add_order_to_trip(order, new_trip, vehicle, travel)
            self._placed.add(order.order_id)
            return None

        # No placement possible — build an explanatory deferral reason
        return self._build_deferral_reason(order, travel)

    def _pre_filter_order(
        self, order: OrderCandidate, travel: TravelData
    ) -> Optional[DeferredOrderResult]:
        """
        Quick filter: reject orders that cannot possibly fit on ANY vehicle,
        even on an empty trip.  Produces the most specific reason possible.
        """
        eligible_vehicles = [v for v in self._vehicles.values()]
        if not eligible_vehicles:
            return DeferredOrderResult(
                order_id=order.order_id,
                reason_code="NO_ELIGIBLE_VEHICLE",
                reason_detail="No vehicles are available for this depot.",
            )

        reasons: list[str] = []

        for vehicle in eligible_vehicles:
            # Depot check
            ok, code, detail = check_home_depot(order, vehicle)
            if not ok:
                reasons.append(code)
                continue

            # Temperature check
            ok, code, detail = check_temperature(order, vehicle)
            if not ok:
                reasons.append(code)
                continue

            # Van access check
            ok, code, detail = check_van_access(order, vehicle)
            if not ok:
                reasons.append(code)
                continue

            # Weight check (single order vs vehicle cap)
            if order.total_weight_kg > vehicle.weight_cap_kg:
                reasons.append("CAPACITY_WEIGHT")
                continue

            # Volume check (single order vs vehicle cap)
            if order.total_volume_m3 > vehicle.volume_cap_m3:
                reasons.append("CAPACITY_VOLUME")
                continue

            # If we got here, at least this vehicle is physically compatible
            return None

        # Determine the dominant rejection reason
        if not reasons:
            dominant = "NO_ELIGIBLE_VEHICLE"
        else:
            # Most common reason wins as dominant code
            dominant = max(set(reasons), key=reasons.count)

        detail_map = {
            "NO_REEFER_VEHICLE": "Order requires refrigeration but no reefer vehicle is available at this depot.",
            "NO_VAN_AVAILABLE": "Outlet requires van-only access but no van is available at this depot.",
            "WRONG_DEPOT": "No vehicle is assigned to this order's depot.",
            "CAPACITY_WEIGHT": "Order weight exceeds the capacity of every available vehicle.",
            "CAPACITY_VOLUME": "Order volume exceeds the capacity of every available vehicle.",
            "NO_ELIGIBLE_VEHICLE": "No vehicle meets all feasibility constraints for this order.",
        }
        return DeferredOrderResult(
            order_id=order.order_id,
            reason_code=dominant,
            reason_detail=detail_map.get(dominant, "No eligible vehicle found."),
        )

    def _find_best_existing_trip(
        self, order: OrderCandidate, travel: TravelData
    ) -> tuple[Optional[TripState], Optional[VehicleCandidate]]:
        """
        Find the best existing TripState to add this order to.

        Scoring criteria (lower = better):
          1. incremental trip duration added
          2. incremental volume utilization fraction
          3. incremental weight utilization fraction
          4. vehicle_id (deterministic tie-break)
        """
        candidates: list[tuple[float, float, float, str, TripState, VehicleCandidate]] = []

        for vehicle_id, trips in self._trips.items():
            vehicle = self._vehicles[vehicle_id]
            fresh_used, st_used, fuel_used = self._vehicle_budgets(vehicle_id)

            for trip in trips:
                # Get existing order objects for this trip
                existing_orders = self._orders_in_trip(trip)

                passed, _, _ = check_order_can_join_trip(
                    order=order,
                    trip=trip,
                    vehicle=vehicle,
                    additional_orders=existing_orders,
                    travel=travel,
                    service_allowances=self._service,
                    vehicle_fresh_minutes_used=fresh_used,
                    vehicle_style_tech_minutes_used=st_used,
                    vehicle_fuel_used_l=fuel_used,
                )
                if not passed:
                    continue

                # Score the incremental cost of adding this order
                old_dur = calculate_trip_duration(existing_orders, travel, self._service)
                new_dur = calculate_trip_duration(existing_orders + [order], travel, self._service)
                delta_dur = new_dur - old_dur

                vol_fraction = (trip.total_volume_m3 + order.total_volume_m3) / vehicle.volume_cap_m3
                wt_fraction = (trip.total_weight_kg + order.total_weight_kg) / vehicle.weight_cap_kg

                candidates.append((delta_dur, vol_fraction, wt_fraction, vehicle_id, trip, vehicle))

        if not candidates:
            return None, None

        candidates.sort(key=lambda c: (c[0], c[1], c[2], c[3]))
        _, _, _, _, best_trip, best_vehicle = candidates[0]
        return best_trip, best_vehicle

    def _open_new_trip(
        self, order: OrderCandidate, travel: TravelData
    ) -> Optional[tuple[TripState, VehicleCandidate]]:
        """
        Try to open a new TripState on a vehicle that can serve this order.

        Resource scarcity policy:
          - Prefer non-reefer vehicles for ambient orders (save reefer for chilled).
          - Prefer non-van vehicles for normal-access orders (save vans for van-only).
          - Among equal candidates, sort by vehicle_id for determinism.
        """
        candidates: list[tuple[int, int, str, VehicleCandidate]] = []

        for vehicle in sorted(self._vehicles.values(), key=lambda v: v.vehicle_id):
            existing_trips = self._trips.get(vehicle.vehicle_id, [])

            # Max trips check
            ok, _, _ = check_max_trips(vehicle.vehicle_id, len(existing_trips))
            if not ok:
                continue

            # Basic compatibility checks
            ok, _, _ = check_home_depot(order, vehicle)
            if not ok:
                continue
            ok, _, _ = check_temperature(order, vehicle)
            if not ok:
                continue
            ok, _, _ = check_van_access(order, vehicle)
            if not ok:
                continue

            # Single-order fits the vehicle
            if order.total_weight_kg > vehicle.weight_cap_kg:
                continue
            if order.total_volume_m3 > vehicle.volume_cap_m3:
                continue

            # Time budget check for a single-order trip
            single_duration = calculate_trip_duration([order], travel, self._service)
            single_distance = calculate_trip_distance([order], travel)
            single_fuel = single_distance / vehicle.km_per_l if vehicle.km_per_l > 0 else 0.0

            fresh_used, st_used, fuel_used = self._vehicle_budgets(vehicle.vehicle_id)

            if order.brand == "Fresh":
                ok, _, _ = check_fresh_time_budget(single_duration, fresh_used)
            else:
                ok, _, _ = check_style_tech_time_budget(single_duration, st_used)
            if not ok:
                continue

            ok, _, _ = check_fuel_quota(single_fuel, vehicle, fuel_used)
            if not ok:
                continue

            # Scarcity penalty: avoid wasting scarce resources
            # 0 = ideal, higher = less preferred
            reefer_waste_penalty = (
                1 if vehicle.temp == "reefer" and order.temp_requirement == "ambient" else 0
            )
            van_waste_penalty = (
                1 if vehicle.type == "van" and order.parking_constraint == "normal" else 0
            )

            candidates.append((reefer_waste_penalty, van_waste_penalty, vehicle.vehicle_id, vehicle))

        if not candidates:
            return None

        candidates.sort(key=lambda c: (c[0], c[1], c[2]))
        _, _, _, vehicle = candidates[0]

        trip_number = len(self._trips.get(vehicle.vehicle_id, [])) + 1
        new_trip = TripState(
            vehicle_id=vehicle.vehicle_id,
            trip_number=trip_number,
            brand=order.brand,
            district=order.district,
            depot=order.depot,
        )
        if vehicle.vehicle_id not in self._trips:
            self._trips[vehicle.vehicle_id] = []
        self._trips[vehicle.vehicle_id].append(new_trip)

        return new_trip, vehicle

    def _add_order_to_trip(
        self,
        order: OrderCandidate,
        trip: TripState,
        vehicle: VehicleCandidate,
        travel: TravelData,
    ) -> None:
        """Mutate TripState to include the order."""
        trip.orders.append(order.order_id)

        seq = len(trip.stops) + 1
        trip.stops.append(StopPlan(
            order_id=order.order_id,
            outlet_id=order.outlet_id,
            sequence_number=seq,
            load_position=seq,      # will be reversed at freeze time
        ))

        trip.total_weight_kg += order.total_weight_kg
        trip.total_volume_m3 += order.total_volume_m3

        # Recalculate duration and distance from scratch
        all_orders = self._orders_in_trip(trip)
        trip.estimated_duration_min = calculate_trip_duration(all_orders, travel, self._service)
        trip.estimated_distance_km = calculate_trip_distance(all_orders, travel)
        trip.estimated_fuel_l = (
            trip.estimated_distance_km / vehicle.km_per_l if vehicle.km_per_l > 0 else 0.0
        )

    def _build_deferral_reason(
        self, order: OrderCandidate, travel: TravelData
    ) -> DeferredOrderResult:
        """
        Build the most specific deferral reason by probing existing trips
        and vehicles to find the actual binding constraint.
        """
        # Check if any vehicle is even eligible in principle
        eligible_vehicles = [
            v for v in self._vehicles.values()
            if (
                check_home_depot(order, v)[0]
                and check_temperature(order, v)[0]
                and check_van_access(order, v)[0]
            )
        ]
        if not eligible_vehicles:
            if order.temp_requirement == "chilled":
                return DeferredOrderResult(
                    order_id=order.order_id,
                    reason_code="NO_REEFER_VEHICLE",
                    reason_detail="Order requires refrigeration; no reefer vehicle is available or eligible.",
                )
            if order.parking_constraint == "van_only":
                return DeferredOrderResult(
                    order_id=order.order_id,
                    reason_code="NO_VAN_AVAILABLE",
                    reason_detail="Outlet requires van-only access; no van is available.",
                )
            return DeferredOrderResult(
                order_id=order.order_id,
                reason_code="NO_ELIGIBLE_VEHICLE",
                reason_detail="No vehicle meets all compatibility constraints for this order.",
            )

        # Vehicles exist but trips are full or time/fuel is exhausted
        all_at_max_trips = all(
            len(self._trips.get(v.vehicle_id, [])) >= 2 for v in eligible_vehicles
        )
        if all_at_max_trips:
            return DeferredOrderResult(
                order_id=order.order_id,
                reason_code="TRIP_LIMIT_REACHED",
                reason_detail=(
                    "All eligible vehicles have already reached the 2-trip daily limit. "
                    "No additional trips can be created."
                ),
            )

        # Capacity / time / fuel — find the most common blocking constraint
        blocking_codes: list[str] = []
        for vehicle in eligible_vehicles:
            for trips in [self._trips.get(vehicle.vehicle_id, [])]:
                for trip in trips:
                    if trip.brand != order.brand or trip.district != order.district:
                        continue
                    existing = self._orders_in_trip(trip)
                    fresh_used, st_used, fuel_used = self._vehicle_budgets(vehicle.vehicle_id)
                    passed, code, _ = check_order_can_join_trip(
                        order, trip, vehicle, existing, travel, self._service,
                        fresh_used, st_used, fuel_used,
                    )
                    if not passed:
                        blocking_codes.append(code)

        if blocking_codes:
            dominant = max(set(blocking_codes), key=blocking_codes.count)
            detail_map = {
                "CAPACITY_WEIGHT": "All compatible trips have insufficient remaining weight capacity.",
                "CAPACITY_VOLUME": "All compatible trips have insufficient remaining volume capacity.",
                "FRESH_TIME_CAPACITY": "Fresh operating time budget is exhausted for all eligible vehicles.",
                "STYLE_TECH_TIME_CAPACITY": "Style/Tech operating time budget is exhausted for all eligible vehicles.",
                "FUEL_QUOTA_EXCEEDED": "Adding this trip would exceed the weekly fuel quota for all eligible vehicles.",
            }
            return DeferredOrderResult(
                order_id=order.order_id,
                reason_code=dominant,
                reason_detail=detail_map.get(dominant, f"Constraint violated: {dominant}."),
            )

        return DeferredOrderResult(
            order_id=order.order_id,
            reason_code="NO_ELIGIBLE_VEHICLE",
            reason_detail=(
                "No compatible trip exists satisfying brand, district, temperature, "
                "access, capacity, and time constraints simultaneously."
            ),
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _orders_in_trip(self, trip: TripState) -> list[OrderCandidate]:
        """Return the OrderCandidate objects for orders already in a trip."""
        order_map = {o.order_id: o for o in self._orders}
        return [order_map[oid] for oid in trip.orders if oid in order_map]

    def _vehicle_budgets(self, vehicle_id: str) -> tuple[float, float, float]:
        """
        Return (fresh_minutes_used, style_tech_minutes_used, fuel_used_l)
        for all trips currently assigned to this vehicle.
        """
        trips = self._trips.get(vehicle_id, [])
        fresh = sum(t.estimated_duration_min for t in trips if t.brand == "Fresh")
        st = sum(t.estimated_duration_min for t in trips if t.brand in ("Style", "Tech"))
        fuel = sum(t.estimated_fuel_l for t in trips)
        return fresh, st, fuel

    def _freeze_trips(self) -> list[TripResult]:
        """Convert all TripStates into immutable TripResult objects."""
        results: list[TripResult] = []
        for vehicle_id, trips in sorted(self._trips.items()):
            vehicle = self._vehicles[vehicle_id]
            for trip in trips:
                if not trip.orders:
                    continue  # skip empty trips (shouldn't happen)

                # Fix load_position: loading order is reverse of delivery sequence
                n = len(trip.stops)
                stops = []
                for stop in trip.stops:
                    stops.append(StopPlan(
                        order_id=stop.order_id,
                        outlet_id=stop.outlet_id,
                        sequence_number=stop.sequence_number,
                        load_position=n - stop.sequence_number + 1,
                        planned_arrival_time=stop.planned_arrival_time,
                    ))

                # Assign departure time based on brand
                departure_time = "03:30" if trip.brand == "Fresh" else "08:00"

                results.append(TripResult(
                    vehicle_id=vehicle_id,
                    trip_number=trip.trip_number,
                    brand=trip.brand,
                    district=trip.district,
                    depot=trip.depot,
                    orders=list(trip.orders),
                    stops=stops,
                    total_weight_kg=round(trip.total_weight_kg, 3),
                    total_volume_m3=round(trip.total_volume_m3, 4),
                    estimated_duration_min=round(trip.estimated_duration_min, 1),
                    estimated_distance_km=round(trip.estimated_distance_km, 2),
                    estimated_fuel_l=round(trip.estimated_fuel_l, 2),
                    planned_departure_time=departure_time,
                ))

        return results

    def _compute_metrics(
        self,
        trips: list[TripResult],
        deferred: list[DeferredOrderResult],
    ) -> AllocationMetrics:
        served_ids = {oid for t in trips for oid in t.orders}
        reason_counts: dict[str, int] = {}
        for d in deferred:
            reason_counts[d.reason_code] = reason_counts.get(d.reason_code, 0) + 1

        vehicles_used = len({t.vehicle_id for t in trips})

        m = AllocationMetrics(
            total_orders=len(self._orders),
            served_orders=len(served_ids),
            deferred_orders=len(deferred),
            vehicles_used=vehicles_used,
            trips_created=len(trips),
            reefer_trips=sum(
                1 for t in trips
                if self._vehicles[t.vehicle_id].temp == "reefer"
            ),
            van_trips=sum(
                1 for t in trips
                if self._vehicles[t.vehicle_id].type == "van"
            ),
            fresh_trips=sum(1 for t in trips if t.brand == "Fresh"),
            style_trips=sum(1 for t in trips if t.brand == "Style"),
            tech_trips=sum(1 for t in trips if t.brand == "Tech"),
            total_weight_allocated_kg=round(sum(t.total_weight_kg for t in trips), 3),
            total_volume_allocated_m3=round(sum(t.total_volume_m3 for t in trips), 4),
            deferred_reason_counts=reason_counts,
        )
        return m

    def _detect_depot(self) -> str:
        """Infer depot from the order set (all orders should share one depot)."""
        if self._orders:
            return self._orders[0].depot
        return "Unknown"
