"""
Planning service — orchestrates data loading, engine execution, and persistence.

This is the ONLY module that touches both the allocation engine and the database.

Responsibility:
  1. Load confirmed orders for a planning date + depot (repository layer).
  2. Load available vehicles for the depot (repository layer).
  3. Build travel / service-allowance lookup tables.
  4. Call AllocationEngine.generate() — pure, no DB.
  5. Call validate_plan() — prove feasibility.
  6. If dry_run=True: return result without persisting.
  7. If valid: persist in a single logical transaction sequence:
       delivery_plans → trips → trip_stops → deferred_orders → update order statuses.
  8. Return the AllocationResult.

Database note:
  Supabase's Python client does not expose a true begin/commit API for the
  service-role key, so we execute inserts in dependency order and rely on
  the plan being generated-in-memory and validated before any writes start.
  If a write fails mid-way, the plan record can be deleted via its id.
"""
from __future__ import annotations

import datetime
import logging
from typing import Optional

from supabase import Client

from app.repositories.order_repository import OrderRepository
from app.repositories.outlet_repository import OutletRepository
from app.repositories.vehicle_repository import VehicleRepository
from app.repositories.trip_repository import TripRepository

from app.services.allocation import (
    AllocationEngine,
    AllocationResult,
    DeferredOrderResult,
    OrderCandidate,
    ServiceAllowance,
    TravelData,
    TripResult,
    VehicleCandidate,
    validate_plan,
    ValidationResult,
)

log = logging.getLogger(__name__)

# ── Static reference data (loaded once at service construction) ────────────────
# district_travel.csv embedded as defaults; overridden if DB lookup exists.
# In production the seed script populates these; if unavailable we use the
# official CSV values directly.

_STATIC_TRAVEL: list[dict] = [
    {"district": "Colombo",      "depot": "Peliyagoda", "depot_to_district_freeflow_min": 24, "inter_stop_freeflow_min": 8,  "depot_to_district_km": 12,  "inter_stop_km": 4.0},
    {"district": "Gampaha",      "depot": "Peliyagoda", "depot_to_district_freeflow_min": 37, "inter_stop_freeflow_min": 9,  "depot_to_district_km": 28,  "inter_stop_km": 7.0},
    {"district": "Kalutara",     "depot": "Peliyagoda", "depot_to_district_freeflow_min": 64, "inter_stop_freeflow_min": 12, "depot_to_district_km": 48,  "inter_stop_km": 9.0},
    {"district": "Galle",        "depot": "Peliyagoda", "depot_to_district_freeflow_min": 103,"inter_stop_freeflow_min": 9,  "depot_to_district_km": 120, "inter_stop_km": 10.0},
    {"district": "Matara",       "depot": "Peliyagoda", "depot_to_district_freeflow_min": 137,"inter_stop_freeflow_min": 10, "depot_to_district_km": 160, "inter_stop_km": 12.0},
    {"district": "Kurunegala",   "depot": "Peliyagoda", "depot_to_district_freeflow_min": 127,"inter_stop_freeflow_min": 19, "depot_to_district_km": 95,  "inter_stop_km": 14.0},
    {"district": "Puttalam",     "depot": "Peliyagoda", "depot_to_district_freeflow_min": 173,"inter_stop_freeflow_min": 24, "depot_to_district_km": 130, "inter_stop_km": 18.0},
    {"district": "Kandy",        "depot": "Kandy",      "depot_to_district_freeflow_min": 16, "inter_stop_freeflow_min": 6,  "depot_to_district_km": 8,   "inter_stop_km": 3.0},
    {"district": "Matale",       "depot": "Kandy",      "depot_to_district_freeflow_min": 35, "inter_stop_freeflow_min": 11, "depot_to_district_km": 26,  "inter_stop_km": 8.0},
    {"district": "Nuwara Eliya", "depot": "Kandy",      "depot_to_district_freeflow_min": 111,"inter_stop_freeflow_min": 20, "depot_to_district_km": 78,  "inter_stop_km": 14.0},
    {"district": "Badulla",      "depot": "Kandy",      "depot_to_district_freeflow_min": 186,"inter_stop_freeflow_min": 23, "depot_to_district_km": 130, "inter_stop_km": 16.0},
    {"district": "Kegalle",      "depot": "Kandy",      "depot_to_district_freeflow_min": 53, "inter_stop_freeflow_min": 13, "depot_to_district_km": 40,  "inter_stop_km": 10.0},
]

_STATIC_SERVICE: list[dict] = [
    {"brand": "Fresh", "dock_type": "rear_dock", "service_allowance_min": 15},
    {"brand": "Fresh", "dock_type": "street",    "service_allowance_min": 16},
    {"brand": "Fresh", "dock_type": "mall_bay",  "service_allowance_min": 18},
    {"brand": "Style", "dock_type": "rear_dock", "service_allowance_min": 38},
    {"brand": "Style", "dock_type": "street",    "service_allowance_min": 46},
    {"brand": "Style", "dock_type": "mall_bay",  "service_allowance_min": 59},
    {"brand": "Tech",  "dock_type": "rear_dock", "service_allowance_min": 43},
    {"brand": "Tech",  "dock_type": "street",    "service_allowance_min": 55},
    {"brand": "Tech",  "dock_type": "mall_bay",  "service_allowance_min": 55},
]


class PlanningService:
    """
    Orchestrates plan generation for one depot on one planning date.

    Inject a Supabase client; the service creates all repositories internally.
    """

    def __init__(self, db: Client, dispatcher_id: Optional[str] = None) -> None:
        self._db = db
        self._dispatcher_id = dispatcher_id
        self._order_repo = OrderRepository(db)
        self._outlet_repo = OutletRepository(db)
        self._vehicle_repo = VehicleRepository(db)
        self._trip_repo = TripRepository(db)

    # ── Public method ─────────────────────────────────────────────────────────

    def generate_plan(
        self,
        plan_date: datetime.date,
        depot: str,
        dry_run: bool = False,
    ) -> dict:
        """
        Generate a delivery plan for `plan_date` and `depot`.

        Args:
            plan_date: The date for which to plan deliveries.
            depot:     'Peliyagoda' or 'Kandy'.
            dry_run:   If True, compute the plan but do not persist it.

        Returns:
            A dictionary matching the AllocationResult structure, plus
            'plan_id' if the plan was persisted.
        """
        log.info("Plan generation started", extra={"plan_date": str(plan_date), "depot": depot})

        # ── STEP 1: Load data ─────────────────────────────────────────────────
        orders = self._load_orders(plan_date, depot)
        vehicles = self._load_vehicles(depot)
        travel_lookup = self._build_travel_lookup()
        service_lookup = self._build_service_lookup()

        log.info(
            "Data loaded",
            extra={"orders": len(orders), "vehicles": len(vehicles)},
        )

        if not orders:
            log.warning("No submitted orders found for planning", extra={"plan_date": str(plan_date), "depot": depot})

        # ── STEP 2: Run allocation engine ─────────────────────────────────────
        engine = AllocationEngine(
            orders=orders,
            vehicles=vehicles,
            travel_lookup=travel_lookup,
            service_allowance_lookup=service_lookup,
            plan_date=plan_date,
        )
        result = engine.generate()

        # ── STEP 3: Validate ──────────────────────────────────────────────────
        order_lookup = {o.order_id: o for o in orders}
        vehicle_lookup = {v.vehicle_id: v for v in vehicles}

        validation = validate_plan(
            result=result,
            order_lookup=order_lookup,
            vehicle_lookup=vehicle_lookup,
            travel_lookup=travel_lookup,
            service_allowance_lookup=service_lookup,
        )

        log.info(
            "Validation complete",
            extra={"valid": validation.valid, "violations": len(validation.violations)},
        )

        if not validation.valid:
            violation_details = [
                f"{v.constraint}: {v.detail}" for v in validation.violations
            ]
            log.error("Plan validation failed", extra={"violations": violation_details})
            raise ValueError(
                f"Generated plan failed validation with {len(validation.violations)} violation(s). "
                f"First: {violation_details[0] if violation_details else 'unknown'}"
            )

        # ── STEP 4: Persist (unless dry_run) ─────────────────────────────────
        plan_id: Optional[str] = None
        if not dry_run:
            plan_id = self._persist(result, plan_date, depot)
            log.info("Plan persisted", extra={"plan_id": plan_id})

        # ── STEP 5: Build API response ────────────────────────────────────────
        return self._to_response_dict(result, plan_id, validation)

    # ── Data loading ──────────────────────────────────────────────────────────

    def _load_orders(
        self, plan_date: datetime.date, depot: str
    ) -> list[OrderCandidate]:
        """
        Load all submitted orders for this date+depot and enrich with outlet data.
        Uses the existing list_for_date_depot method which joins outlets.
        """
        rows = self._order_repo.list_for_date_depot(plan_date, depot, status="submitted")

        candidates: list[OrderCandidate] = []
        for row in rows:
            outlet = row.get("outlets") or {}

            # Determine parking_constraint — DB may have 'mall_dock', normalize
            pc = outlet.get("parking_constraint", "normal")
            if pc not in ("normal", "van_only", "mall_dock"):
                pc = "normal"

            dock_type = outlet.get("dock_type", "rear_dock")
            if dock_type not in ("rear_dock", "street", "mall_bay"):
                dock_type = "rear_dock"

            candidates.append(OrderCandidate(
                order_id=str(row["id"]),
                outlet_id=row["outlet_id"],
                brand=row["brand"],
                district=outlet.get("district", ""),
                depot=outlet.get("depot", depot),
                temp_requirement=row["temp_requirement"],
                total_weight_kg=float(row.get("total_weight_kg", 0) or 0),
                total_volume_m3=float(row.get("total_volume_m3", 0) or 0),
                dock_type=dock_type,
                parking_constraint=pc,
                window_open_time=outlet.get("window_open_time", "08:00"),
                window_close_time=outlet.get("window_close_time", "20:00"),
                deferred_yesterday=False,  # not available from current schema; placeholder
                days_since_last_served=0,  # not available from current schema; placeholder
            ))

        return candidates

    def _load_vehicles(self, depot: str) -> list[VehicleCandidate]:
        """Load all vehicles for this depot."""
        rows = self._vehicle_repo.list_by_depot(depot)
        return [
            VehicleCandidate(
                vehicle_id=row["vehicle_id"],
                type=row["type"],
                temp=row["temp"],
                weight_cap_kg=float(row["weight_cap_kg"]),
                volume_cap_m3=float(row["volume_cap_m3"]),
                fuel_type=row.get("fuel_type", "diesel"),
                km_per_l=float(row.get("km_per_l", 10) or 10),
                weekly_fuel_quota_l=float(row.get("weekly_fuel_quota_l", 200) or 200),
                depot=row["depot"],
            )
            for row in rows
        ]

    def _build_travel_lookup(self) -> dict[tuple[str, str], TravelData]:
        """Build (district, depot) → TravelData lookup from static CSV data."""
        lookup: dict[tuple[str, str], TravelData] = {}
        for row in _STATIC_TRAVEL:
            key = (row["district"], row["depot"])
            lookup[key] = TravelData(
                district=row["district"],
                depot=row["depot"],
                depot_to_district_freeflow_min=float(row["depot_to_district_freeflow_min"]),
                inter_stop_freeflow_min=float(row["inter_stop_freeflow_min"]),
                depot_to_district_km=float(row["depot_to_district_km"]),
                inter_stop_km=float(row["inter_stop_km"]),
            )
        return lookup

    def _build_service_lookup(self) -> dict[tuple[str, str], int]:
        """Build (brand, dock_type) → service_allowance_min lookup from static CSV data."""
        lookup: dict[tuple[str, str], int] = {}
        for row in _STATIC_SERVICE:
            key = (row["brand"], row["dock_type"])
            lookup[key] = int(row["service_allowance_min"])
        return lookup

    # ── Persistence ───────────────────────────────────────────────────────────

    def _persist(
        self,
        result: AllocationResult,
        plan_date: datetime.date,
        depot: str,
    ) -> str:
        """
        Persist the validated AllocationResult to Supabase.

        Sequence:
          1. Upsert delivery_plans (one per date+depot).
          2. Insert trips.
          3. Insert trip_stops.
          4. Insert deferred_orders.
          5. Bulk-update order statuses.

        Returns the plan_id (UUID string).
        """
        # 1. Create or get delivery plan
        plan_id = self._upsert_delivery_plan(plan_date, depot)

        # 2. Insert trips and collect trip_id map
        trip_id_map: dict[tuple[str, int], str] = {}  # (vehicle_id, trip_number) → trip_id

        for trip in result.trips:
            trip_row = self._db.table("trips").insert({
                "plan_id": plan_id,
                "vehicle_id": trip.vehicle_id,
                "trip_number": trip.trip_number,
                "brand": trip.brand,
                "district": trip.district,
                "depot": trip.depot,
                "status": "planned",
                "planned_departure_time": trip.planned_departure_time,
                "total_weight_kg": trip.total_weight_kg,
                "total_volume_m3": trip.total_volume_m3,
                "total_distance_km": trip.estimated_distance_km,
                "fuel_used_l": trip.estimated_fuel_l,
                "estimated_duration_min": int(trip.estimated_duration_min),
            }).execute()
            trip_db_id = trip_row.data[0]["id"]
            trip_id_map[(trip.vehicle_id, trip.trip_number)] = trip_db_id

        # 3. Insert trip stops
        stops_payload: list[dict] = []
        for trip in result.trips:
            trip_db_id = trip_id_map[(trip.vehicle_id, trip.trip_number)]
            for stop in trip.stops:
                stops_payload.append({
                    "trip_id": trip_db_id,
                    "order_id": stop.order_id,
                    "outlet_id": stop.outlet_id,
                    "sequence_number": stop.sequence_number,
                    "load_position": stop.load_position,
                    "planned_arrival_time": stop.planned_arrival_time,
                    "status": "planned",
                })

        if stops_payload:
            self._db.table("trip_stops").insert(stops_payload).execute()

        # 4. Insert deferred orders
        if result.deferred_orders:
            deferred_payload = [
                {
                    "plan_id": plan_id,
                    "order_id": d.order_id,
                    "reason_code": self._map_reason_code(d.reason_code),
                    "reason_detail": d.reason_detail,
                    "consecutive_deferrals": 1,
                    "deferred_by": self._dispatcher_id,
                }
                for d in result.deferred_orders
            ]
            self._db.table("deferred_orders").insert(deferred_payload).execute()

        # 5. Update order statuses
        served_ids = {oid for t in result.trips for oid in t.orders}
        deferred_ids = {d.order_id for d in result.deferred_orders}

        for oid in served_ids:
            self._order_repo.update_status(oid, "allocated")

        for oid in deferred_ids:
            self._order_repo.update_status(oid, "deferred")

        return plan_id

    def _upsert_delivery_plan(self, plan_date: datetime.date, depot: str) -> str:
        """
        Get existing draft plan for this date+depot, or create a new one.
        Returns the plan UUID.
        """
        resp = (
            self._db.table("delivery_plans")
            .select("id")
            .eq("plan_date", str(plan_date))
            .eq("depot", depot)
            .maybe_single()
            .execute()
        )
        if resp.data:
            return resp.data["id"]

        create_resp = self._db.table("delivery_plans").insert({
            "plan_date": str(plan_date),
            "depot": depot,
            "status": "draft",
            "created_by": self._dispatcher_id,
        }).execute()
        return create_resp.data[0]["id"]

    def _map_reason_code(self, engine_code: str) -> str:
        """
        Map engine-internal reason codes to the DB CHECK constraint values.
        The DB schema has a fixed set; we map engine codes to the nearest match.
        """
        mapping = {
            "CAPACITY_WEIGHT":        "CAPACITY_WEIGHT",
            "CAPACITY_VOLUME":        "CAPACITY_VOLUME",
            "NO_REEFER_VEHICLE":      "NO_REEFER_VEHICLE",
            "NO_VAN_AVAILABLE":       "NO_VAN_AVAILABLE",
            "WINDOW_CONFLICT":        "WINDOW_CONFLICT",
            "FUEL_QUOTA_EXCEEDED":    "FUEL_QUOTA_EXCEEDED",
            "TRIP_LIMIT_REACHED":     "TRIP_LIMIT_REACHED",
            "NO_ELIGIBLE_VEHICLE":    "NO_ELIGIBLE_VEHICLE",
            "BRAND_MISMATCH":         "NO_ELIGIBLE_VEHICLE",
            "DISTRICT_MISMATCH":      "NO_ELIGIBLE_VEHICLE",
            "WRONG_DEPOT":            "NO_ELIGIBLE_VEHICLE",
            "FRESH_TIME_CAPACITY":    "NO_ELIGIBLE_VEHICLE",
            "STYLE_TECH_TIME_CAPACITY": "NO_ELIGIBLE_VEHICLE",
            "MANUALLY_DEFERRED":      "MANUALLY_DEFERRED",
        }
        return mapping.get(engine_code, "NO_ELIGIBLE_VEHICLE")

    # ── Response serialization ────────────────────────────────────────────────

    def _to_response_dict(
        self,
        result: AllocationResult,
        plan_id: Optional[str],
        validation: ValidationResult,
    ) -> dict:
        """Serialize AllocationResult to a plain dict for the API layer."""
        return {
            "plan_id": plan_id,
            "plan_date": result.plan_date,
            "depot": result.depot,
            "status": result.status,
            "validation": {
                "valid": validation.valid,
                "violation_count": len(validation.violations),
            },
            "trips": [
                {
                    "vehicle_id": t.vehicle_id,
                    "trip_number": t.trip_number,
                    "brand": t.brand,
                    "district": t.district,
                    "depot": t.depot,
                    "orders": t.orders,
                    "total_weight_kg": t.total_weight_kg,
                    "total_volume_m3": t.total_volume_m3,
                    "estimated_duration_min": t.estimated_duration_min,
                    "estimated_distance_km": t.estimated_distance_km,
                    "estimated_fuel_l": t.estimated_fuel_l,
                    "planned_departure_time": t.planned_departure_time,
                    "stops": [
                        {
                            "order_id": s.order_id,
                            "outlet_id": s.outlet_id,
                            "sequence_number": s.sequence_number,
                            "load_position": s.load_position,
                            "planned_arrival_time": s.planned_arrival_time,
                        }
                        for s in t.stops
                    ],
                }
                for t in result.trips
            ],
            "deferred_orders": [
                {
                    "order_id": d.order_id,
                    "reason_code": d.reason_code,
                    "reason_detail": d.reason_detail,
                }
                for d in result.deferred_orders
            ],
            "metrics": {
                "total_orders": result.metrics.total_orders,
                "served_orders": result.metrics.served_orders,
                "deferred_orders": result.metrics.deferred_orders,
                "vehicles_used": result.metrics.vehicles_used,
                "trips_created": result.metrics.trips_created,
                "reefer_trips": result.metrics.reefer_trips,
                "van_trips": result.metrics.van_trips,
                "fresh_trips": result.metrics.fresh_trips,
                "style_trips": result.metrics.style_trips,
                "tech_trips": result.metrics.tech_trips,
                "total_weight_allocated_kg": result.metrics.total_weight_allocated_kg,
                "total_volume_allocated_m3": result.metrics.total_volume_allocated_m3,
                "deferred_reason_counts": result.metrics.deferred_reason_counts,
            },
        }
