-- ============================================================
-- Migration: 007_allow_user_registration
-- Allow authenticated users to insert and update their own application
-- profile in public.users upon sign-up / registration.
-- Role is determined by email / app metadata (no manual role text required).
-- ============================================================

-- Users can insert their own profile matching their authenticated auth.uid()
CREATE POLICY "users_insert_own"
    ON users FOR INSERT
    TO authenticated
    WITH CHECK (id = auth.uid());

-- Users can update their own profile
CREATE POLICY "users_update_own"
    ON users FOR UPDATE
    TO authenticated
    USING (id = auth.uid())
    WITH CHECK (id = auth.uid());
