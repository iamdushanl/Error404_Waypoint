# Allocation Engine — Waypoint Phase 5

*Error404 · Tech-Triathlon 2026*

---

## 1. Problem Definition

The dispatcher needs to assign submitted orders to vehicles and trips for a given delivery date and depot. The engine must:

- Serve as many orders as feasibly possible.
- Respect all operating constraints (capacity, temperature, access, time, fuel).
- Explain every deferral with a machine-readable reason code and a human-readable description.
- Produce a deterministic result — the same inputs always yield the same plan.
- Be independently testable without database or HTTP infrastructure.

---

## 2. Inputs

| Input | Source | Description |
|---|---|---|
| `orders` | `orders` table (status=`submitted`) | Confirmed orders for the planning date + depot |
| `vehicles` | `vehicles` table | All vehicles for the depot |
| `travel_lookup` | `district_travel.csv` (static) | Depot→district travel times and distances |
| `service_allowance_lookup` | `service_allowance.csv` (static) | Handling time per brand × dock type |
| `plan_date` | Dispatcher input | The date for which planning is performed |

---

## 3. Hard Constraints

Every candidate allocation must satisfy ALL of the following. These are binary — either satisfied or the allocation is rejected.

| # | Constraint | Rule |
|---|---|---|
| C1 | Brand + District | All orders in a trip must share the same brand AND district |
| C2 | Temperature | `chilled` orders require `vehicle.temp = reefer`; reefer may carry ambient |
| C3 | Vehicle Access | `outlet.parking_constraint = van_only` requires `vehicle.type = van` |
| C4 | Home Depot | `order.depot` must equal `vehicle.depot` |
| C5 | Whole Orders | An order belongs to exactly one trip — never split |
| C6 | Weight Capacity | `sum(order.total_weight_kg) ≤ vehicle.weight_cap_kg` |
| C7 | Volume Capacity | `sum(order.total_volume_m3) ≤ vehicle.volume_cap_m3` |
| C8 | Max Trips | Vehicle may run ≤ 2 trips per day |
| C9 | Fresh Time Budget | Fresh trips ≤ 270 minutes total per vehicle per day |
| C10 | Style/Tech Time Budget | Style + Tech trips ≤ 480 minutes total per vehicle per day (separate from Fresh) |
| C11 | Fuel Quota | Estimated fuel consumed ≤ `vehicle.weekly_fuel_quota_l` |

> **Important:** C9 and C10 are SEPARATE budgets. A vehicle may run one Fresh trip (≤270 min) AND one Style trip (≤480 min) provided the total trip count is ≤2.

---

## 4. Trip-Time Calculation

Taken directly from the challenge specification:

```
trip_minutes =
    depot_to_district_freeflow_min
    + inter_stop_freeflow_min × (number_of_orders − 1)
    + Σ service_allowance_min(brand, dock_type)
```

**Example:** Fresh trip to Gampaha, 3 orders (2 rear_dock + 1 street):

| Component | Minutes |
|---|---|
| Depot to Gampaha | 37 |
| 2 inter-stop journeys (9 × 2) | 18 |
| Fresh + rear_dock | 15 |
| Fresh + rear_dock | 15 |
| Fresh + street | 16 |
| **Total** | **101** |

Early arrivals wait until the delivery window opens. This waiting time is NOT added to the time budget — the budget covers operational driving and handling, not idle waiting.

---

## 5. Prioritization Policy

This is a **deterministic heuristic**, not a proven global optimum.

### Score Formula

```
priority_score =
    (days_since_last_served × 10)    # starvation_points
  + (25 if deferred_yesterday)        # deferral_yesterday_bonus
  + (15 if temp_requirement=chilled)  # cold_chain_bonus
  + window_urgency_points             # 0–20, linear from 0h to 2h before close
```

### Tie-Breaking (deterministic)

1. `priority_score` DESC
2. `window_close_time` ASC (tightest window first)
3. `days_since_last_served` DESC
4. `order_id` ASC (final deterministic tie-break)

### Weight Rationale

| Component | Weight | Rationale |
|---|---|---|
| Starvation per day | 10 | 3 days unserved (30pts) clearly outranks served yesterday (10pts) |
| Deferred yesterday | 25 | Prevents an outlet being repeatedly skipped |
| Cold chain | 15 | Chilled goods spoil; cost of deferral is higher |
| Window urgency max | 20 | Prevents windows closing before vehicle arrives |

These weights were chosen to be simple integers verifiable by inspection. They do not claim optimality.

---

## 6. Allocation Algorithm

### Step-by-Step

1. **Score and sort** all orders by priority (descending).
2. **For each order** (in priority order):
   - a. Search existing trips for a compatible placement.
   - b. If found, add the order to the best trip (least incremental duration first).
   - c. If not found, try to open a new trip on a compatible vehicle.
   - d. When opening a new trip, prefer vehicles that don't waste scarce resources:
     - Don't use a reefer vehicle for ambient orders if an ambient vehicle is available.
     - Don't use a van for normal-access orders if a truck is available.
   - e. If still no placement, mark the order **deferred** with an explicit reason.

### Resource Scarcity Policy

The engine prefers to preserve scarce resources:
- Reefer vehicles are preferred for chilled orders; ambient vehicles used first for ambient.
- Vans are preferred for `van_only` outlets; trucks used first for normal access.

This is a **policy rule**, not a hard constraint. It improves overall allocation quality.

---

## 7. Fuel Calculation

```
distance_km = depot_to_district_km + inter_stop_km × (n − 1)
fuel_l = distance_km / vehicle.km_per_l
```

Fuel is accumulated across all trips for a vehicle and checked against `weekly_fuel_quota_l`.

---

## 8. Deferral Reason Codes

| Code | Description |
|---|---|
| `NO_REEFER_VEHICLE` | Order requires refrigeration; no reefer vehicle available |
| `NO_VAN_AVAILABLE` | Outlet requires van-only access; no van available |
| `WRONG_DEPOT` | No vehicle assigned to this order's depot |
| `CAPACITY_WEIGHT` | Order weight exceeds all compatible vehicles/trips |
| `CAPACITY_VOLUME` | Order volume exceeds all compatible vehicles/trips |
| `TRIP_LIMIT_REACHED` | All eligible vehicles already have 2 trips |
| `FRESH_TIME_CAPACITY` | Fresh daily time budget exhausted for all eligible vehicles |
| `STYLE_TECH_TIME_CAPACITY` | Style/Tech daily time budget exhausted for all eligible vehicles |
| `FUEL_QUOTA_EXCEEDED` | Adding this trip would exceed the vehicle's weekly fuel quota |
| `NO_ELIGIBLE_VEHICLE` | No vehicle satisfies all constraints simultaneously |
| `WINDOW_CONFLICT` | Delivery window incompatible with any feasible schedule |

Each deferred order also carries a `reason_detail` — a human-readable explanation generated from the actual failed constraint, not a generic message.

---

## 9. Validation Strategy

```
ALLOCATION ENGINE
    ↓
candidate AllocationResult (in-memory)

VALIDATE (validate_plan)
    ↓
ValidationResult(valid=True/False, violations=[...])

if valid → persist to database
if invalid → raise ValueError, nothing persisted
```

The validator (`validator.py`) is completely independent of the heuristic. It re-checks every hard constraint against the final plan. This means:
- You can unit-test the validator separately.
- You can validate hand-crafted plans (e.g., from manual dispatcher adjustments).
- Bugs in the heuristic are caught before any DB writes.

---

## 10. Persistence Sequence

When `dry_run=False`, the planning service persists in this order:

1. Upsert `delivery_plans` (one per date + depot).
2. Insert `trips` (one per TripResult).
3. Bulk insert `trip_stops`.
4. Bulk insert `deferred_orders`.
5. Bulk update `orders.status` → `allocated` or `deferred`.

If any insert fails, the plan record can be identified by its `plan_id` for manual cleanup. Future work: wrap in a true atomic transaction using a Postgres function.

---

## 11. API Contract

### Primary Endpoint

```
POST /api/v1/planning/generate
Authorization: Bearer <dispatcher_jwt>

{
    "plan_date": "2026-10-04",
    "depot": "Peliyagoda",
    "dry_run": false
}
```

**Response (201 Created):**

```json
{
    "plan_id": "...",
    "plan_date": "2026-10-04",
    "depot": "Peliyagoda",
    "status": "generated",
    "validation": { "valid": true, "violation_count": 0 },
    "trips": [
        {
            "vehicle_id": "WP-CAB-9241",
            "trip_number": 1,
            "brand": "Fresh",
            "district": "Colombo",
            "orders": ["order-uuid-1", "order-uuid-2"],
            "total_weight_kg": 1200.0,
            "total_volume_m3": 8.5,
            "estimated_duration_min": 79.0,
            "estimated_distance_km": 28.0,
            "estimated_fuel_l": 2.8,
            "planned_departure_time": "03:30",
            "stops": [...]
        }
    ],
    "deferred_orders": [
        {
            "order_id": "order-uuid-3",
            "reason_code": "NO_REEFER_VEHICLE",
            "reason_detail": "Order requires refrigeration but no reefer vehicle is available or eligible."
        }
    ],
    "metrics": {
        "total_orders": 45,
        "served_orders": 43,
        "deferred_orders": 2,
        "vehicles_used": 8,
        "trips_created": 10,
        "reefer_trips": 4,
        "van_trips": 2,
        "fresh_trips": 6,
        "style_trips": 3,
        "tech_trips": 1,
        "deferred_reason_counts": { "NO_REEFER_VEHICLE": 2 }
    }
}
```

### Other Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/planning/plans` | List delivery plans |
| `GET` | `/api/v1/planning/plans/{id}` | Get plan with trips and stops |
| `PATCH` | `/api/v1/planning/plans/{id}/confirm` | Dispatcher confirms plan |

---

## 12. Module Structure

```
backend/api/app/services/
├── allocation/
│   ├── __init__.py          ← public package API
│   ├── models.py            ← pure domain dataclasses (OrderCandidate, TripResult, …)
│   ├── constraints.py       ← hard constraint functions (C1–C11)
│   ├── prioritization.py    ← deterministic scoring and sort policy
│   ├── engine.py            ← AllocationEngine (greedy constructive heuristic)
│   └── validator.py         ← validate_plan() — independent feasibility proof
└── planning_service.py      ← orchestrates data loading + engine + persistence
```

---

## 13. Known Limitations

1. **Greedy, not optimal.** The heuristic makes locally optimal choices. A different order of orders could yield a better global allocation. A combinatorial solver (e.g., OR-Tools CP-SAT) would improve utilization but reduce explainability and testability.

2. **No delivery window scheduling.** The engine enforces time *budgets* but does not schedule specific arrival times per stop. The `planned_arrival_time` fields are null in the current version. Future work: model the schedule forward from departure time.

3. **Static travel data.** Travel times use free-flow values from `district_travel.csv`. Monsoon, traffic congestion, and road conditions are not applied in Phase 5.

4. **Fuel quota is weekly, not daily.** The engine checks `weekly_fuel_quota_l` but only tracks fuel for the single planning day. A multi-day tracking table is needed for production accuracy.

5. **`deferred_yesterday` / `days_since_last_served`** are not in the current orders schema. The engine accepts `0` defaults. These signals should be populated from a historical delivery table for full policy effectiveness.

6. **No transactional rollback.** Supabase's Python client does not expose begin/commit for the service-role key. The persistence sequence is ordered by dependency but is not atomic.

---

## 14. Test Coverage

All 12 hard constraints have dedicated unit tests in `tests/test_allocation_constraints.py`.

Adversarial cases tested:
- Exact capacity boundaries (weight and volume at cap, at cap - ε, at cap + ε)
- No reefer vehicle → deferred with correct reason code
- No van for van-only outlet → deferred with correct reason code
- All vehicles at 2-trip limit → excess orders deferred
- Same order appearing in two trips → validator catches it
- Repeated runs on identical inputs → identical output (determinism)
- Challenge-spec trip-time example (Gampaha, 3 orders) → exactly 101 minutes
