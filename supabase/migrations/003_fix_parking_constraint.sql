-- ============================================================
-- Quick fix: add mall_dock to parking_constraint check
-- Paste this in Supabase SQL Editor → Run
-- ============================================================

ALTER TABLE outlets DROP CONSTRAINT IF EXISTS outlets_parking_constraint_check;

ALTER TABLE outlets ADD CONSTRAINT outlets_parking_constraint_check
    CHECK (parking_constraint IN ('normal', 'van_only', 'mall_dock'));

SELECT 'Constraint fixed — safe to run seed now' AS status;
