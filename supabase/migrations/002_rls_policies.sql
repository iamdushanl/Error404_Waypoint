-- ============================================================
-- Migration: 002_rls_policies
-- Row-Level Security policies for Waypoint
--
-- FIXED: auth.user_role() moved to public schema (Supabase blocks
-- creating functions in the auth schema from SQL Editor).
--
-- HOW IT WORKS:
-- FastAPI uses the service-role key → bypasses RLS entirely.
-- RLS here protects any direct Supabase client access from browser/mobile.
-- ============================================================

-- ── Helper function in PUBLIC schema (NOT auth schema) ────────────────────────
-- Gets the current authenticated user's application role.
-- Used by all RLS policies below.
CREATE OR REPLACE FUNCTION public.get_user_role()
RETURNS TEXT AS $$
    SELECT role FROM public.users WHERE id = auth.uid();
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- Grant execute permission so the function can be called in policies
GRANT EXECUTE ON FUNCTION public.get_user_role() TO authenticated;


-- ════════════════════════════════════════════════════════════
-- REFERENCE TABLES — readable by all authenticated users
-- ════════════════════════════════════════════════════════════

-- Outlets: any authenticated user can read
CREATE POLICY "outlets_read_all"
    ON outlets FOR SELECT
    TO authenticated
    USING (true);

-- Vehicles: dispatchers, loaders, and drivers can read
CREATE POLICY "vehicles_read_auth"
    ON vehicles FOR SELECT
    TO authenticated
    USING (public.get_user_role() IN ('dispatcher', 'loader', 'driver'));

-- Calendar: any authenticated user can read
CREATE POLICY "calendar_read_all"
    ON calendar FOR SELECT
    TO authenticated
    USING (true);


-- ════════════════════════════════════════════════════════════
-- USERS
-- ════════════════════════════════════════════════════════════

-- Users can read their own profile
CREATE POLICY "users_read_own"
    ON users FOR SELECT
    TO authenticated
    USING (id = auth.uid());

-- Dispatchers can read all user profiles (for assignment UI)
CREATE POLICY "users_dispatchers_read_all"
    ON users FOR SELECT
    TO authenticated
    USING (public.get_user_role() = 'dispatcher');


-- ════════════════════════════════════════════════════════════
-- ORDERS
-- ════════════════════════════════════════════════════════════

-- Store managers: read/write their own outlet's orders
CREATE POLICY "orders_store_manager_own"
    ON orders FOR ALL
    TO authenticated
    USING (
        public.get_user_role() = 'store_manager'
        AND outlet_id = (SELECT outlet_id FROM users WHERE id = auth.uid())
    )
    WITH CHECK (
        public.get_user_role() = 'store_manager'
        AND outlet_id = (SELECT outlet_id FROM users WHERE id = auth.uid())
    );

-- Dispatchers: full read access to all orders
CREATE POLICY "orders_dispatcher_read"
    ON orders FOR SELECT
    TO authenticated
    USING (public.get_user_role() = 'dispatcher');

-- Dispatchers: can update order status (allocate/defer)
CREATE POLICY "orders_dispatcher_update"
    ON orders FOR UPDATE
    TO authenticated
    USING (public.get_user_role() = 'dispatcher')
    WITH CHECK (public.get_user_role() = 'dispatcher');

-- Drivers: can read orders assigned to their trips
CREATE POLICY "orders_driver_read_assigned"
    ON orders FOR SELECT
    TO authenticated
    USING (
        public.get_user_role() = 'driver'
        AND id IN (
            SELECT ts.order_id
            FROM trip_stops ts
            JOIN trips t ON t.id = ts.trip_id
            JOIN users u ON u.vehicle_id = t.vehicle_id
            WHERE u.id = auth.uid()
        )
    );


-- ════════════════════════════════════════════════════════════
-- DELIVERY PLANS
-- ════════════════════════════════════════════════════════════

CREATE POLICY "plans_dispatcher_all"
    ON delivery_plans FOR ALL
    TO authenticated
    USING (public.get_user_role() = 'dispatcher')
    WITH CHECK (public.get_user_role() = 'dispatcher');

CREATE POLICY "plans_loader_driver_read"
    ON delivery_plans FOR SELECT
    TO authenticated
    USING (
        public.get_user_role() IN ('loader', 'driver')
        AND status IN ('confirmed', 'dispatched', 'completed')
        AND depot = (SELECT depot FROM users WHERE id = auth.uid())
    );


-- ════════════════════════════════════════════════════════════
-- TRIPS
-- ════════════════════════════════════════════════════════════

CREATE POLICY "trips_dispatcher_all"
    ON trips FOR ALL
    TO authenticated
    USING (public.get_user_role() = 'dispatcher')
    WITH CHECK (public.get_user_role() = 'dispatcher');

CREATE POLICY "trips_loader_read"
    ON trips FOR SELECT
    TO authenticated
    USING (
        public.get_user_role() = 'loader'
        AND depot = (SELECT depot FROM users WHERE id = auth.uid())
    );

CREATE POLICY "trips_loader_ack"
    ON trips FOR UPDATE
    TO authenticated
    USING (
        public.get_user_role() = 'loader'
        AND depot = (SELECT depot FROM users WHERE id = auth.uid())
    )
    WITH CHECK (public.get_user_role() = 'loader');

CREATE POLICY "trips_driver_own"
    ON trips FOR SELECT
    TO authenticated
    USING (
        public.get_user_role() = 'driver'
        AND vehicle_id = (SELECT vehicle_id FROM users WHERE id = auth.uid())
    );


-- ════════════════════════════════════════════════════════════
-- TRIP STOPS
-- ════════════════════════════════════════════════════════════

CREATE POLICY "trip_stops_dispatcher_all"
    ON trip_stops FOR ALL
    TO authenticated
    USING (public.get_user_role() = 'dispatcher')
    WITH CHECK (public.get_user_role() = 'dispatcher');

CREATE POLICY "trip_stops_loader_read"
    ON trip_stops FOR SELECT
    TO authenticated
    USING (
        public.get_user_role() = 'loader'
        AND trip_id IN (
            SELECT id FROM trips
            WHERE depot = (SELECT depot FROM users WHERE id = auth.uid())
        )
    );

CREATE POLICY "trip_stops_loader_update"
    ON trip_stops FOR UPDATE
    TO authenticated
    USING (public.get_user_role() = 'loader')
    WITH CHECK (public.get_user_role() = 'loader');

CREATE POLICY "trip_stops_driver_read"
    ON trip_stops FOR SELECT
    TO authenticated
    USING (
        public.get_user_role() = 'driver'
        AND trip_id IN (
            SELECT id FROM trips
            WHERE vehicle_id = (SELECT vehicle_id FROM users WHERE id = auth.uid())
        )
    );


-- ════════════════════════════════════════════════════════════
-- DELIVERIES
-- ════════════════════════════════════════════════════════════

CREATE POLICY "deliveries_driver_own"
    ON deliveries FOR ALL
    TO authenticated
    USING (driver_id = auth.uid())
    WITH CHECK (driver_id = auth.uid());

CREATE POLICY "deliveries_dispatcher_read"
    ON deliveries FOR SELECT
    TO authenticated
    USING (public.get_user_role() = 'dispatcher');

CREATE POLICY "deliveries_store_manager_read"
    ON deliveries FOR SELECT
    TO authenticated
    USING (
        public.get_user_role() = 'store_manager'
        AND trip_stop_id IN (
            SELECT ts.id FROM trip_stops ts
            JOIN orders o ON o.id = ts.order_id
            JOIN users u ON u.outlet_id = o.outlet_id
            WHERE u.id = auth.uid()
        )
    );


-- ════════════════════════════════════════════════════════════
-- PROOF OF DELIVERY
-- ════════════════════════════════════════════════════════════

CREATE POLICY "pod_driver_own"
    ON proof_of_delivery FOR ALL
    TO authenticated
    USING (
        delivery_id IN (
            SELECT id FROM deliveries WHERE driver_id = auth.uid()
        )
    );

CREATE POLICY "pod_dispatcher_read"
    ON proof_of_delivery FOR SELECT
    TO authenticated
    USING (public.get_user_role() = 'dispatcher');

CREATE POLICY "pod_store_manager_read"
    ON proof_of_delivery FOR SELECT
    TO authenticated
    USING (public.get_user_role() = 'store_manager');


-- ════════════════════════════════════════════════════════════
-- SHORTFALLS
-- ════════════════════════════════════════════════════════════

CREATE POLICY "shortfalls_loader_own"
    ON shortfalls FOR ALL
    TO authenticated
    USING (recorded_by = auth.uid())
    WITH CHECK (recorded_by = auth.uid());

CREATE POLICY "shortfalls_dispatcher_driver_read"
    ON shortfalls FOR SELECT
    TO authenticated
    USING (public.get_user_role() IN ('dispatcher', 'driver'));


-- ════════════════════════════════════════════════════════════
-- RECEIPT CONFIRMATIONS
-- ════════════════════════════════════════════════════════════

CREATE POLICY "receipts_store_manager_own"
    ON receipt_confirmations FOR ALL
    TO authenticated
    USING (confirmed_by = auth.uid())
    WITH CHECK (confirmed_by = auth.uid());

CREATE POLICY "receipts_dispatcher_read"
    ON receipt_confirmations FOR SELECT
    TO authenticated
    USING (public.get_user_role() = 'dispatcher');


-- ════════════════════════════════════════════════════════════
-- DEFERRED ORDERS
-- ════════════════════════════════════════════════════════════

CREATE POLICY "deferred_dispatcher_all"
    ON deferred_orders FOR ALL
    TO authenticated
    USING (public.get_user_role() = 'dispatcher')
    WITH CHECK (public.get_user_role() = 'dispatcher');

CREATE POLICY "deferred_store_manager_read"
    ON deferred_orders FOR SELECT
    TO authenticated
    USING (
        public.get_user_role() = 'store_manager'
        AND order_id IN (
            SELECT id FROM orders
            WHERE outlet_id = (SELECT outlet_id FROM users WHERE id = auth.uid())
        )
    );


-- ════════════════════════════════════════════════════════════
-- SYNC EVENTS
-- ════════════════════════════════════════════════════════════

CREATE POLICY "sync_driver_own"
    ON sync_events FOR ALL
    TO authenticated
    USING (driver_id = auth.uid())
    WITH CHECK (driver_id = auth.uid());

CREATE POLICY "sync_dispatcher_read"
    ON sync_events FOR SELECT
    TO authenticated
    USING (public.get_user_role() = 'dispatcher');
