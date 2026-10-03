-- ============================================================
-- Migration: 004_allocation_engine_updates
-- Waypoint — extend deferred_orders reason codes and add
-- a depot column to trips (was missing from initial schema).
--
-- This migration is ADDITIVE — no existing data is destroyed.
-- ============================================================

-- ── 1. Extend deferred_orders reason_code CHECK constraint ───────────────────
-- The allocation engine generates reason codes that weren't in the original set.
-- We drop the old constraint and replace it with a broader one.

ALTER TABLE deferred_orders
    DROP CONSTRAINT IF EXISTS deferred_orders_reason_code_check;

ALTER TABLE deferred_orders
    ADD CONSTRAINT deferred_orders_reason_code_check
    CHECK (reason_code IN (
        -- Original codes
        'CAPACITY_WEIGHT',       -- vehicle weight limit exceeded
        'CAPACITY_VOLUME',       -- vehicle volume limit exceeded
        'NO_REEFER_VEHICLE',     -- chilled order, no reefer available
        'NO_VAN_AVAILABLE',      -- van-only outlet, no van available
        'WINDOW_CONFLICT',       -- delivery window incompatible
        'FUEL_QUOTA_EXCEEDED',   -- weekly fuel budget exhausted
        'TRIP_LIMIT_REACHED',    -- vehicle already has 2 trips
        'NO_ELIGIBLE_VEHICLE',   -- no vehicle meets all constraints
        'MANUALLY_DEFERRED',     -- dispatcher chose to defer
        -- Engine-specific codes (mapped to DB equivalents in service layer,
        -- included here for completeness and future direct use)
        'FRESH_TIME_CAPACITY',   -- Fresh daily budget exhausted
        'STYLE_TECH_TIME_CAPACITY', -- Style/Tech daily budget exhausted
        'BRAND_MISMATCH',        -- order brand ≠ any trip's brand
        'DISTRICT_MISMATCH',     -- order district ≠ any trip's district
        'WRONG_DEPOT'            -- order depot ≠ vehicle depot
    ));

-- ── 2. Ensure trips.depot column exists ──────────────────────────────────────
-- The initial schema has depot in the trips table; confirm it's there.
-- This is a no-op if the column already exists.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'trips' AND column_name = 'depot'
    ) THEN
        ALTER TABLE trips
            ADD COLUMN depot TEXT CHECK (depot IN ('Peliyagoda', 'Kandy'));
    END IF;
END $$;

COMMENT ON TABLE deferred_orders IS
    'Every order that could not be allocated must have a recorded reason. '
    'consecutive_deferrals helps dispatcher identify repeatedly skipped outlets. '
    'reason_code set expanded in migration 004 to cover engine-generated codes.';
