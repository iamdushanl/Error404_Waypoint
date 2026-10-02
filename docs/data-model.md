# Data Model — Waypoint

*Error404 · Tech-Triathlon 2026*

---

## Entity Relationship Diagram

```mermaid
erDiagram
    %% ── Auth / Users ──────────────────────────────────────
    AUTH_USERS {
        uuid id PK
        text email
    }
    USERS {
        uuid id PK "FK → auth.users"
        text email
        text full_name
        text role "dispatcher|loader|driver|store_manager"
        text outlet_id FK "store_manager only"
        text depot "Peliyagoda|Kandy"
        text vehicle_id FK "driver only"
        bool is_active
        timestamptz created_at
        timestamptz updated_at
    }
    AUTH_USERS ||--|| USERS : "extends"

    %% ── Reference / Seed Tables ────────────────────────────
    OUTLETS {
        text outlet_id PK "OUT001–OUT120"
        text brand "Fresh|Style|Tech"
        text district
        text depot "Peliyagoda|Kandy"
        text dock_type "rear_dock|street|mall_bay"
        text parking_constraint "normal|van_only"
        text mall_window "nullable"
        text window_open_time "HH:MM"
        text window_close_time "HH:MM"
    }
    VEHICLES {
        text vehicle_id PK
        text type "truck|van"
        text temp "reefer|ambient"
        numeric weight_cap_kg
        numeric volume_cap_m3
        text fuel_type
        numeric km_per_l
        numeric weekly_fuel_quota_l
        text depot "Peliyagoda|Kandy"
    }
    CALENDAR {
        date date PK
        int dow "0=Monday"
        bool is_weekend
        bool is_payday
        text festival "nullable"
        bool is_holiday
        bool monsoon
        bool is_operating
    }

    %% ── Orders ─────────────────────────────────────────────
    ORDERS {
        uuid id PK
        text outlet_id FK
        text brand
        date requested_date
        text status "draft→submitted→allocated/deferred→delivered→confirmed"
        text temp_requirement "chilled|ambient"
        numeric total_weight_kg
        numeric total_volume_m3
        uuid created_by FK "store_manager"
        timestamptz submitted_at
    }
    ORDER_ITEMS {
        uuid id PK
        uuid order_id FK
        text sku
        text description
        int quantity
        numeric weight_kg
        numeric volume_m3
        text temp_requirement
    }

    %% ── Planning ───────────────────────────────────────────
    DELIVERY_PLANS {
        uuid id PK
        date plan_date
        text depot
        text status "draft|confirmed|dispatched|completed"
        uuid created_by FK "dispatcher"
        timestamptz confirmed_at
    }
    TRIPS {
        uuid id PK
        uuid plan_id FK
        text vehicle_id FK
        int trip_number "1 or 2"
        text brand
        text district
        text status "planned|loading|departed|in_transit|completed"
        text planned_departure_time "HH:MM"
        numeric total_weight_kg
        numeric total_volume_m3
        numeric total_distance_km
        numeric fuel_used_l
        int estimated_duration_min
        bool loader_acknowledged
        bool driver_acknowledged
    }
    TRIP_STOPS {
        uuid id PK
        uuid trip_id FK
        uuid order_id FK
        text outlet_id FK
        int sequence_number "delivery order"
        int load_position "loading order (reverse)"
        text planned_arrival_time "HH:MM"
        text status "planned|loaded|shortfall|delivered|attempted|refused"
    }
    DEFERRED_ORDERS {
        uuid id PK
        uuid plan_id FK
        uuid order_id FK
        text reason_code "CAPACITY_WEIGHT|NO_REEFER_VEHICLE|..."
        text reason_detail
        int consecutive_deferrals
        uuid deferred_by FK
    }

    %% ── Delivery Execution ─────────────────────────────────
    DELIVERIES {
        uuid id PK
        uuid trip_stop_id FK
        uuid driver_id FK
        text outcome "delivered|attempted|refused"
        timestamptz delivered_at
        text recipient_name
        text offline_operation_id "idempotency key"
    }
    PROOF_OF_DELIVERY {
        uuid id PK
        uuid delivery_id FK
        text recipient_name
        text photo_url
        timestamptz recorded_at
    }
    SHORTFALLS {
        uuid id PK
        uuid trip_stop_id FK
        text issue_type "missing|damaged|wrong_item"
        text sku
        int expected_quantity
        int actual_quantity
        text photo_url
        uuid recorded_by FK "loader"
    }
    RECEIPT_CONFIRMATIONS {
        uuid id PK
        uuid delivery_id FK
        uuid order_id FK
        uuid confirmed_by FK "store_manager"
        jsonb items_received
        text issues_noted
        timestamptz confirmed_at
    }

    %% ── Offline Sync ───────────────────────────────────────
    SYNC_EVENTS {
        uuid id PK
        text operation_id "client UUID — idempotency key"
        text device_id
        uuid driver_id FK
        text entity_type "delivery|proof_of_delivery|shortfall"
        text operation "complete_delivery|record_pod|record_shortfall"
        jsonb payload
        text status "pending|applied|duplicate|failed"
        timestamptz received_at
        timestamptz applied_at
    }

    %% ── Relationships ──────────────────────────────────────
    USERS ||--o{ ORDERS : "creates (store_manager)"
    USERS ||--o{ DELIVERY_PLANS : "creates (dispatcher)"
    USERS ||--o{ DELIVERIES : "records (driver)"
    USERS ||--o{ SHORTFALLS : "records (loader)"
    USERS ||--o{ RECEIPT_CONFIRMATIONS : "confirms (store_manager)"
    USERS ||--o{ SYNC_EVENTS : "syncs (driver)"

    OUTLETS ||--o{ ORDERS : "receives"
    OUTLETS ||--o{ TRIP_STOPS : "served by"
    VEHICLES ||--o{ TRIPS : "assigned to"

    ORDERS ||--o{ ORDER_ITEMS : "contains"
    ORDERS ||--o{ TRIP_STOPS : "allocated to"
    ORDERS ||--o{ DEFERRED_ORDERS : "may be deferred"

    DELIVERY_PLANS ||--o{ TRIPS : "contains"
    DELIVERY_PLANS ||--o{ DEFERRED_ORDERS : "records"

    TRIPS ||--o{ TRIP_STOPS : "has stops"

    TRIP_STOPS ||--o| DELIVERIES : "results in"
    TRIP_STOPS ||--o{ SHORTFALLS : "may have"

    DELIVERIES ||--o| PROOF_OF_DELIVERY : "has POD"
    DELIVERIES ||--o| RECEIPT_CONFIRMATIONS : "confirmed by"
```

---

## Table Summary

| Table | Rows (expected) | Source |
|---|---|---|
| `outlets` | 120 | `outlets.csv` |
| `vehicles` | 60 | `vehicles.csv` |
| `calendar` | ~500+ dates | `calendar.csv` |
| `users` | 4 (demo) | Seed script |
| `orders` | Dynamic | Store managers |
| `order_items` | Dynamic | Store managers |
| `delivery_plans` | 1 per depot per day | Dispatcher |
| `trips` | ≤120/day (max 2/vehicle) | Allocation engine |
| `trip_stops` | Dynamic | Allocation engine |
| `deferred_orders` | Dynamic | Allocation engine |
| `deliveries` | 1 per stop | Driver |
| `proof_of_delivery` | 1 per delivery | Driver |
| `shortfalls` | Dynamic | Loader |
| `receipt_confirmations` | 1 per delivery | Store manager |
| `sync_events` | 1 per offline op | Sync engine |

---

## Key Constraints (from challenge brief)

| Constraint | Enforced in |
|---|---|
| Vehicle weight/volume capacity | Allocation engine + trip_stops |
| Refrigerated requirement (chilled orders) | `vehicles.temp = 'reefer'` check |
| Van-only outlet access | `outlets.parking_constraint = 'van_only'` |
| Max 2 trips per vehicle per day | `trips.trip_number IN (1,2)` + UNIQUE |
| Delivery windows | Allocation engine + `outlets.window_*` |
| Weekly fuel quota | Calculated per vehicle per week |
| Fresh window (3:30–8:00 AM) | Allocation engine budget check |
| Style/Tech window (trading day, 480 min) | Allocation engine budget check |

---

## Migrations

| File | Description |
|---|---|
| `supabase/migrations/001_initial_schema.sql` | All 15 tables + indexes + triggers |
| `supabase/migrations/002_rls_policies.sql` | Row-Level Security per role |

## Seed

```bash
cd backend/api
py ../../scripts/seed.py
```

Place `outlets.csv`, `vehicles.csv`, `calendar.csv` in `data/` first.
