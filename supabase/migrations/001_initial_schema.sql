-- ============================================================
-- Migration: 001_initial_schema
-- Waypoint — complete database schema
-- Tech-Triathlon 2026 · Error404
--
-- Run order: this must be the FIRST migration.
-- Requires: Supabase project with auth schema already present.
-- ============================================================

-- ── Enable required extensions ────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- fuzzy text search (future)


-- ============================================================
-- REFERENCE / SEED TABLES
-- Populated from competition CSVs (outlets.csv, vehicles.csv, calendar.csv)
-- ============================================================

-- ── Outlets (120 stores across Sri Lanka) ────────────────────────────────────
CREATE TABLE outlets (
    outlet_id           TEXT PRIMARY KEY,           -- e.g. OUT001 … OUT120
    brand               TEXT NOT NULL
                            CHECK (brand IN ('Fresh', 'Style', 'Tech')),
    district            TEXT NOT NULL,
    depot               TEXT NOT NULL
                            CHECK (depot IN ('Peliyagoda', 'Kandy')),
    dock_type           TEXT NOT NULL
                            CHECK (dock_type IN ('rear_dock', 'street', 'mall_bay')),
    parking_constraint  TEXT NOT NULL DEFAULT 'normal'
                            CHECK (parking_constraint IN ('normal', 'van_only', 'mall_dock')),
    -- mall_window: opening window for mall loading bays (HH:MM–HH:MM), null for non-mall
    mall_window         TEXT,
    window_open_time    TEXT NOT NULL,              -- HH:MM  Asia/Colombo
    window_close_time   TEXT NOT NULL,              -- HH:MM  Asia/Colombo
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE outlets IS
    'One row per retail outlet. Seeded from outlets.csv (120 rows). '
    'Do not modify manually — re-run seed script to refresh.';


-- ── Vehicles (60 vehicles across two depots) ─────────────────────────────────
CREATE TABLE vehicles (
    vehicle_id          TEXT PRIMARY KEY,           -- e.g. WP-CAB-9241
    type                TEXT NOT NULL
                            CHECK (type IN ('truck', 'van')),
    temp                TEXT NOT NULL
                            CHECK (temp IN ('reefer', 'ambient')),
    weight_cap_kg       NUMERIC(10, 2) NOT NULL,
    volume_cap_m3       NUMERIC(8, 3) NOT NULL,
    fuel_type           TEXT NOT NULL,
    km_per_l            NUMERIC(6, 2) NOT NULL,
    weekly_fuel_quota_l NUMERIC(8, 2) NOT NULL,
    depot               TEXT NOT NULL
                            CHECK (depot IN ('Peliyagoda', 'Kandy')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE vehicles IS
    'One row per vehicle. Seeded from vehicles.csv (60 rows). '
    '12 reefer trucks, 40 dry-box trucks, 8 vans (4 of which are reefer).';


-- ── Calendar (operating dates with demand context) ───────────────────────────
CREATE TABLE calendar (
    date                DATE PRIMARY KEY,
    dow                 INTEGER NOT NULL CHECK (dow BETWEEN 0 AND 6),  -- 0=Monday
    dow_name            TEXT NOT NULL,
    is_weekend          BOOLEAN NOT NULL,
    iso_year            INTEGER NOT NULL,
    iso_week            INTEGER NOT NULL,
    is_payday           BOOLEAN NOT NULL DEFAULT FALSE,
    festival            TEXT,                       -- festival name or null
    festival_ramp       INTEGER,                    -- days until festival
    is_holiday          BOOLEAN NOT NULL DEFAULT FALSE,
    monsoon             BOOLEAN NOT NULL DEFAULT FALSE,
    is_operating        BOOLEAN NOT NULL DEFAULT TRUE
);

COMMENT ON TABLE calendar IS
    'One row per date. Seeded from calendar.csv. '
    'Waypoint operates Monday–Saturday (is_operating = true).';


-- ============================================================
-- USER / AUTH TABLES
-- ============================================================

-- ── Users (application profile extending Supabase auth.users) ────────────────
CREATE TABLE users (
    id              UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email           TEXT NOT NULL,
    full_name       TEXT NOT NULL,
    role            TEXT NOT NULL
                        CHECK (role IN ('dispatcher', 'loader', 'driver', 'store_manager')),
    -- Context-specific foreign keys (only relevant field is set per role)
    outlet_id       TEXT REFERENCES outlets(outlet_id),   -- store_manager only
    depot           TEXT CHECK (depot IN ('Peliyagoda', 'Kandy')),  -- loader/driver
    vehicle_id      TEXT REFERENCES vehicles(vehicle_id), -- driver only
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE users IS
    'Application user profile. One row per auth.users row. '
    'Role determines which parts of the UI and API the user may access.';

CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_outlet_id ON users(outlet_id) WHERE outlet_id IS NOT NULL;


-- ============================================================
-- ORDER MANAGEMENT
-- ============================================================

-- ── Orders ───────────────────────────────────────────────────────────────────
CREATE TABLE orders (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    outlet_id           TEXT NOT NULL REFERENCES outlets(outlet_id),
    brand               TEXT NOT NULL CHECK (brand IN ('Fresh', 'Style', 'Tech')),
    requested_date      DATE NOT NULL,              -- date the store wants delivery
    status              TEXT NOT NULL DEFAULT 'draft'
                            CHECK (status IN (
                                'draft',            -- store manager saving
                                'submitted',        -- submitted by store manager
                                'closed',           -- dispatcher locked order queue
                                'allocated',        -- assigned to a trip
                                'deferred',         -- could not be allocated
                                'in_transit',       -- vehicle departed
                                'delivered',        -- driver recorded delivery
                                'confirmed'         -- store manager confirmed receipt
                            )),
    temp_requirement    TEXT NOT NULL
                            CHECK (temp_requirement IN ('chilled', 'ambient')),
    total_weight_kg     NUMERIC(10, 2) NOT NULL DEFAULT 0,
    total_volume_m3     NUMERIC(8, 3) NOT NULL DEFAULT 0,
    notes               TEXT,
    created_by          UUID REFERENCES users(id),  -- store_manager
    submitted_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE orders IS
    'One row per store order. Moves through status lifecycle from draft to confirmed.';

CREATE INDEX idx_orders_outlet_id ON orders(outlet_id);
CREATE INDEX idx_orders_requested_date ON orders(requested_date);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_brand ON orders(brand);


-- ── Order Items ───────────────────────────────────────────────────────────────
CREATE TABLE order_items (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id            UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    sku                 TEXT NOT NULL,
    description         TEXT NOT NULL,
    quantity            INTEGER NOT NULL CHECK (quantity > 0),
    weight_kg           NUMERIC(8, 3) NOT NULL,
    volume_m3           NUMERIC(6, 4) NOT NULL,
    temp_requirement    TEXT NOT NULL
                            CHECK (temp_requirement IN ('chilled', 'ambient')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_order_items_order_id ON order_items(order_id);


-- ============================================================
-- PLANNING / ALLOCATION
-- ============================================================

-- ── Delivery Plans (one per depot per operating day) ─────────────────────────
CREATE TABLE delivery_plans (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_date       DATE NOT NULL,
    depot           TEXT NOT NULL CHECK (depot IN ('Peliyagoda', 'Kandy')),
    status          TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN (
                            'draft',        -- dispatcher building
                            'confirmed',    -- dispatcher published plan
                            'dispatched',   -- vehicles departed
                            'completed'     -- all deliveries recorded
                        )),
    created_by      UUID REFERENCES users(id),  -- dispatcher
    confirmed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (plan_date, depot)
);

COMMENT ON TABLE delivery_plans IS
    'One plan per depot per operating day. '
    'A plan contains multiple trips; dispatcher confirms before vehicles load.';

CREATE INDEX idx_delivery_plans_date ON delivery_plans(plan_date);


-- ── Trips (a vehicle's route on a given day; max 2 per vehicle) ───────────────
CREATE TABLE trips (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id                 UUID NOT NULL REFERENCES delivery_plans(id),
    vehicle_id              TEXT NOT NULL REFERENCES vehicles(vehicle_id),
    trip_number             INTEGER NOT NULL CHECK (trip_number IN (1, 2)),
    brand                   TEXT NOT NULL CHECK (brand IN ('Fresh', 'Style', 'Tech')),
    district                TEXT NOT NULL,
    depot                   TEXT NOT NULL CHECK (depot IN ('Peliyagoda', 'Kandy')),
    status                  TEXT NOT NULL DEFAULT 'planned'
                                CHECK (status IN (
                                    'planned',      -- allocation complete
                                    'loading',      -- loader is loading vehicle
                                    'departed',     -- vehicle has left depot
                                    'in_transit',   -- driver on route
                                    'completed'     -- all stops done
                                )),
    -- Planned timing (HH:MM Asia/Colombo)
    planned_departure_time  TEXT,
    -- Capacity tracking (updated as orders are assigned)
    total_weight_kg         NUMERIC(10, 2) NOT NULL DEFAULT 0,
    total_volume_m3         NUMERIC(8, 3) NOT NULL DEFAULT 0,
    total_distance_km       NUMERIC(8, 2) NOT NULL DEFAULT 0,
    fuel_used_l             NUMERIC(8, 2) NOT NULL DEFAULT 0,
    estimated_duration_min  INTEGER NOT NULL DEFAULT 0,
    -- Acknowledgement flags
    loader_acknowledged     BOOLEAN NOT NULL DEFAULT FALSE,
    driver_acknowledged     BOOLEAN NOT NULL DEFAULT FALSE,
    departed_at             TIMESTAMPTZ,
    completed_at            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (plan_id, vehicle_id, trip_number)
);

COMMENT ON TABLE trips IS
    'One row per vehicle trip (route). Max 2 trips per vehicle per day. '
    'Fresh trips: 3:30AM–8:00AM window (270 min budget). '
    'Style/Tech trips: trading day window (480 min budget).';

CREATE INDEX idx_trips_plan_id ON trips(plan_id);
CREATE INDEX idx_trips_vehicle_id ON trips(vehicle_id);
CREATE INDEX idx_trips_status ON trips(status);


-- ── Trip Stops (ordered stops within a trip) ──────────────────────────────────
CREATE TABLE trip_stops (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trip_id             UUID NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    order_id            UUID NOT NULL REFERENCES orders(id),
    outlet_id           TEXT NOT NULL REFERENCES outlets(outlet_id),
    -- sequence_number: delivery order (1 = first stop after depot)
    sequence_number     INTEGER NOT NULL,
    -- load_position: loading order at warehouse (reverse of delivery)
    -- load_position 1 = loaded last = delivered first
    load_position       INTEGER NOT NULL,
    planned_arrival_time TEXT,                      -- HH:MM Asia/Colombo
    status              TEXT NOT NULL DEFAULT 'planned'
                            CHECK (status IN (
                                'planned',          -- trip not yet loaded
                                'loaded',           -- loader confirmed loaded
                                'shortfall',        -- loader flagged shortfall
                                'delivered',        -- driver: successfully delivered
                                'attempted',        -- driver: no one available
                                'refused'           -- driver: outlet refused
                            )),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (trip_id, order_id),
    UNIQUE (trip_id, sequence_number)
);

CREATE INDEX idx_trip_stops_trip_id ON trip_stops(trip_id);
CREATE INDEX idx_trip_stops_order_id ON trip_stops(order_id);


-- ── Deferred Orders ───────────────────────────────────────────────────────────
CREATE TABLE deferred_orders (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id                 UUID NOT NULL REFERENCES delivery_plans(id),
    order_id                UUID NOT NULL REFERENCES orders(id),
    -- Reason codes used by the allocation engine
    reason_code             TEXT NOT NULL CHECK (reason_code IN (
                                'CAPACITY_WEIGHT',       -- vehicle weight limit exceeded
                                'CAPACITY_VOLUME',       -- vehicle volume limit exceeded
                                'NO_REEFER_VEHICLE',     -- chilled order, no reefer available
                                'NO_VAN_AVAILABLE',      -- van-only outlet, no van available
                                'WINDOW_CONFLICT',       -- delivery window incompatible
                                'FUEL_QUOTA_EXCEEDED',   -- weekly fuel budget exhausted
                                'TRIP_LIMIT_REACHED',    -- vehicle already has 2 trips
                                'NO_ELIGIBLE_VEHICLE',   -- no vehicle meets all constraints
                                'MANUALLY_DEFERRED'      -- dispatcher chose to defer
                            )),
    reason_detail           TEXT NOT NULL,
    consecutive_deferrals   INTEGER NOT NULL DEFAULT 1,
    deferred_by             UUID REFERENCES users(id),  -- dispatcher or system
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (plan_id, order_id)
);

COMMENT ON TABLE deferred_orders IS
    'Every order that could not be allocated must have a recorded reason. '
    'consecutive_deferrals helps dispatcher identify repeatedly skipped outlets.';

CREATE INDEX idx_deferred_orders_plan_id ON deferred_orders(plan_id);
CREATE INDEX idx_deferred_orders_order_id ON deferred_orders(order_id);


-- ============================================================
-- DELIVERY EXECUTION
-- ============================================================

-- ── Deliveries (driver records per stop) ─────────────────────────────────────
CREATE TABLE deliveries (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trip_stop_id            UUID NOT NULL REFERENCES trip_stops(id),
    driver_id               UUID REFERENCES users(id),
    outcome                 TEXT CHECK (outcome IN ('delivered', 'attempted', 'refused')),
    delivered_at            TIMESTAMPTZ,
    recipient_name          TEXT,
    notes                   TEXT,
    -- Idempotency key: client-generated UUID for offline sync
    -- Ensures a delivery recorded offline cannot be double-applied on sync
    offline_operation_id    TEXT UNIQUE,
    synced_at               TIMESTAMPTZ,            -- when this was received from offline
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE deliveries IS
    'Driver records one row per stop outcome. '
    'offline_operation_id is a client-generated UUID for idempotent offline sync.';

CREATE INDEX idx_deliveries_trip_stop_id ON deliveries(trip_stop_id);
CREATE INDEX idx_deliveries_driver_id ON deliveries(driver_id);


-- ── Proof of Delivery ────────────────────────────────────────────────────────
CREATE TABLE proof_of_delivery (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    delivery_id             UUID NOT NULL REFERENCES deliveries(id) ON DELETE CASCADE,
    recipient_name          TEXT NOT NULL,
    photo_url               TEXT,                   -- Supabase Storage URL
    recipient_signature_url TEXT,                   -- optional signature scan
    recorded_at             TIMESTAMPTZ NOT NULL,   -- driver's device time
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_pod_delivery_id ON proof_of_delivery(delivery_id);


-- ── Shortfalls (loader records before vehicle departure) ─────────────────────
CREATE TABLE shortfalls (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trip_stop_id        UUID NOT NULL REFERENCES trip_stops(id),
    issue_type          TEXT NOT NULL
                            CHECK (issue_type IN ('missing', 'damaged', 'wrong_item')),
    sku                 TEXT NOT NULL,
    description         TEXT NOT NULL,
    expected_quantity   INTEGER NOT NULL,
    actual_quantity     INTEGER NOT NULL,
    photo_url           TEXT,                       -- Supabase Storage URL
    notes               TEXT,
    recorded_by         UUID REFERENCES users(id),  -- loader
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_shortfalls_trip_stop_id ON shortfalls(trip_stop_id);


-- ── Receipt Confirmations (store manager confirms what arrived) ───────────────
CREATE TABLE receipt_confirmations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    delivery_id     UUID NOT NULL REFERENCES deliveries(id),
    order_id        UUID NOT NULL REFERENCES orders(id),
    confirmed_by    UUID REFERENCES users(id),      -- store_manager
    items_received  JSONB,                          -- {sku: qty_received, ...}
    issues_noted    TEXT,
    confirmed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_receipts_delivery_id ON receipt_confirmations(delivery_id);
CREATE INDEX idx_receipts_order_id ON receipt_confirmations(order_id);


-- ============================================================
-- OFFLINE SYNC
-- ============================================================

-- ── Sync Events (offline operation audit log) ─────────────────────────────────
CREATE TABLE sync_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Client-generated UUID — the key that makes sync idempotent
    operation_id    TEXT NOT NULL UNIQUE,
    device_id       TEXT,
    driver_id       UUID REFERENCES users(id),
    entity_type     TEXT NOT NULL
                        CHECK (entity_type IN ('delivery', 'proof_of_delivery', 'shortfall')),
    entity_id       TEXT NOT NULL,
    operation       TEXT NOT NULL
                        CHECK (operation IN (
                            'complete_delivery',
                            'record_pod',
                            'record_shortfall'
                        )),
    payload         JSONB NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN (
                            'pending',      -- received but not yet applied
                            'applied',      -- successfully applied
                            'duplicate',    -- operation_id already seen — safe to ignore
                            'failed'        -- could not apply (validation/conflict)
                        )),
    error_detail    TEXT,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    applied_at      TIMESTAMPTZ
);

COMMENT ON TABLE sync_events IS
    'Every offline operation the driver syncs is recorded here first. '
    'The operation_id (client UUID) is the idempotency key — '
    'duplicate syncs of the same operation_id are recorded as "duplicate" and ignored.';

CREATE INDEX idx_sync_events_driver_id ON sync_events(driver_id);
CREATE INDEX idx_sync_events_status ON sync_events(status);


-- ============================================================
-- ROW-LEVEL SECURITY (RLS)
-- Enable RLS on all tables; policies added in 002_rls_policies migration.
-- ============================================================

ALTER TABLE outlets              ENABLE ROW LEVEL SECURITY;
ALTER TABLE vehicles             ENABLE ROW LEVEL SECURITY;
ALTER TABLE calendar             ENABLE ROW LEVEL SECURITY;
ALTER TABLE users                ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders               ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_items          ENABLE ROW LEVEL SECURITY;
ALTER TABLE delivery_plans       ENABLE ROW LEVEL SECURITY;
ALTER TABLE trips                ENABLE ROW LEVEL SECURITY;
ALTER TABLE trip_stops           ENABLE ROW LEVEL SECURITY;
ALTER TABLE deferred_orders      ENABLE ROW LEVEL SECURITY;
ALTER TABLE deliveries           ENABLE ROW LEVEL SECURITY;
ALTER TABLE proof_of_delivery    ENABLE ROW LEVEL SECURITY;
ALTER TABLE shortfalls           ENABLE ROW LEVEL SECURITY;
ALTER TABLE receipt_confirmations ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_events          ENABLE ROW LEVEL SECURITY;


-- ── Updated-at trigger (auto-maintain updated_at columns) ────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_orders_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_delivery_plans_updated_at
    BEFORE UPDATE ON delivery_plans
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_trips_updated_at
    BEFORE UPDATE ON trips
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
