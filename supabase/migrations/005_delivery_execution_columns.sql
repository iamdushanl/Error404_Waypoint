-- ============================================================
-- Migration: 005_delivery_execution_columns
-- Waypoint — add missing columns for Phase 6 delivery workflow.
--
-- ADDITIVE: no existing data is destroyed.
-- ============================================================

-- ── 1. Add actual_arrival_time to trip_stops ─────────────────────────────────
-- The driver records actual arrival time when completing a stop.
-- planned_arrival_time already exists; this column tracks actuals.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'trip_stops' AND column_name = 'actual_arrival_time'
    ) THEN
        ALTER TABLE trip_stops
            ADD COLUMN actual_arrival_time TEXT;   -- HH:MM Asia/Colombo or ISO timestamp

        COMMENT ON COLUMN trip_stops.actual_arrival_time IS
            'Driver-recorded actual arrival time. '
            'Compared with planned_arrival_time for on-time analysis.';
    END IF;
END $$;


-- ── 2. Add completed_at to trips (if missing) ─────────────────────────────────
-- completed_at is stamped when the driver marks the trip complete after all stops.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'trips' AND column_name = 'completed_at'
    ) THEN
        ALTER TABLE trips ADD COLUMN completed_at TIMESTAMPTZ;

        COMMENT ON COLUMN trips.completed_at IS
            'When the driver marked the trip as completed (returned to depot). '
            'NULL for in-progress trips.';
    END IF;
END $$;


-- ── 3. Verify key columns exist in deliveries ────────────────────────────────
-- recipient_name lives in both deliveries and proof_of_delivery by design.
-- deliveries.recipient_name is the quick capture; POD has the formal record.
-- No changes needed — schema is correct from migration 001.


-- ── 4. Confirm all Phase 6 tables exist ──────────────────────────────────────
DO $$
DECLARE
    missing_tables TEXT := '';
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'deliveries') THEN
        missing_tables := missing_tables || 'deliveries, ';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'proof_of_delivery') THEN
        missing_tables := missing_tables || 'proof_of_delivery, ';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'shortfalls') THEN
        missing_tables := missing_tables || 'shortfalls, ';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'receipt_confirmations') THEN
        missing_tables := missing_tables || 'receipt_confirmations, ';
    END IF;
    IF missing_tables != '' THEN
        RAISE EXCEPTION 'Missing tables from initial schema: %', missing_tables;
    END IF;
    RAISE NOTICE 'All Phase 6 tables verified OK.';
END $$;
