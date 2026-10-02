-- ============================================================
-- RESET SCRIPT — run this ONCE in Supabase SQL Editor
-- to clear any partial tables before re-running migrations.
--
-- PASTE THIS into Supabase Dashboard → SQL Editor → Run
-- Then paste 001_initial_schema.sql
-- Then paste 002_rls_policies.sql
-- ============================================================

DROP TABLE IF EXISTS sync_events              CASCADE;
DROP TABLE IF EXISTS receipt_confirmations    CASCADE;
DROP TABLE IF EXISTS shortfalls               CASCADE;
DROP TABLE IF EXISTS proof_of_delivery        CASCADE;
DROP TABLE IF EXISTS deliveries               CASCADE;
DROP TABLE IF EXISTS deferred_orders          CASCADE;
DROP TABLE IF EXISTS trip_stops               CASCADE;
DROP TABLE IF EXISTS trips                    CASCADE;
DROP TABLE IF EXISTS delivery_plans           CASCADE;
DROP TABLE IF EXISTS order_items              CASCADE;
DROP TABLE IF EXISTS orders                   CASCADE;
DROP TABLE IF EXISTS calendar                 CASCADE;
DROP TABLE IF EXISTS vehicles                 CASCADE;
DROP TABLE IF EXISTS users                    CASCADE;
DROP TABLE IF EXISTS outlets                  CASCADE;

DROP FUNCTION IF EXISTS update_updated_at()   CASCADE;
DROP FUNCTION IF EXISTS public.get_user_role() CASCADE;

SELECT 'Reset complete — safe to run 001_initial_schema.sql now' AS status;
