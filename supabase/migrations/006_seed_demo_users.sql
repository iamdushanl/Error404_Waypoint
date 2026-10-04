-- ============================================================
-- Seed: Create role-based demo users in Supabase Auth
-- Waypoint — Email + Password login
-- 
-- This script creates 4 demo users in auth.users and their
-- corresponding profiles in the public.users table.
--
-- All users share the same password: waypoint123
--
-- Run this AFTER 001_initial_schema.sql and the outlets/vehicles seeds.
-- ============================================================

-- ── 1. Insert auth users using Supabase's built-in function ──────────────────
-- NOTE: These must be created via Supabase Dashboard or the Auth API.
-- The SQL below inserts directly into auth.users for seeding purposes.
-- Password hash is for: waypoint123 (bcrypt)

-- We use fixed UUIDs so the public.users references are deterministic.

INSERT INTO auth.users (
  id, instance_id, email, encrypted_password,
  email_confirmed_at, created_at, updated_at,
  raw_app_meta_data, raw_user_meta_data,
  aud, role, confirmation_token
) VALUES
  -- Loader
  (
    'a1000000-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid,
    'loader@waypoint.lk',
    crypt('waypoint123', gen_salt('bf')),
    NOW(), NOW(), NOW(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"full_name":"Kamal Perera"}'::jsonb,
    'authenticated', 'authenticated', ''
  ),
  -- Store Manager
  (
    'a2000000-0000-0000-0000-000000000002'::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid,
    'storemanager@waypoint.lk',
    crypt('waypoint123', gen_salt('bf')),
    NOW(), NOW(), NOW(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"full_name":"Nimal Fernando"}'::jsonb,
    'authenticated', 'authenticated', ''
  ),
  -- Dispatcher
  (
    'a3000000-0000-0000-0000-000000000003'::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid,
    'dispatcher@waypoint.lk',
    crypt('waypoint123', gen_salt('bf')),
    NOW(), NOW(), NOW(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"full_name":"Sunil Jayawardena"}'::jsonb,
    'authenticated', 'authenticated', ''
  ),
  -- Driver
  (
    'a4000000-0000-0000-0000-000000000004'::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid,
    'driver@waypoint.lk',
    crypt('waypoint123', gen_salt('bf')),
    NOW(), NOW(), NOW(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"full_name":"Ruwan Silva"}'::jsonb,
    'authenticated', 'authenticated', ''
  )
ON CONFLICT (id) DO NOTHING;

-- ── 2. Create identities for each auth user ──────────────────────────────────
INSERT INTO auth.identities (
  id, user_id, provider_id, provider, identity_data, last_sign_in_at, created_at, updated_at
) VALUES
  (
    'a1000000-0000-0000-0000-000000000001'::uuid,
    'a1000000-0000-0000-0000-000000000001'::uuid,
    'loader@waypoint.lk', 'email',
    '{"sub":"a1000000-0000-0000-0000-000000000001","email":"loader@waypoint.lk"}'::jsonb,
    NOW(), NOW(), NOW()
  ),
  (
    'a2000000-0000-0000-0000-000000000002'::uuid,
    'a2000000-0000-0000-0000-000000000002'::uuid,
    'storemanager@waypoint.lk', 'email',
    '{"sub":"a2000000-0000-0000-0000-000000000002","email":"storemanager@waypoint.lk"}'::jsonb,
    NOW(), NOW(), NOW()
  ),
  (
    'a3000000-0000-0000-0000-000000000003'::uuid,
    'a3000000-0000-0000-0000-000000000003'::uuid,
    'dispatcher@waypoint.lk', 'email',
    '{"sub":"a3000000-0000-0000-0000-000000000003","email":"dispatcher@waypoint.lk"}'::jsonb,
    NOW(), NOW(), NOW()
  ),
  (
    'a4000000-0000-0000-0000-000000000004'::uuid,
    'a4000000-0000-0000-0000-000000000004'::uuid,
    'driver@waypoint.lk', 'email',
    '{"sub":"a4000000-0000-0000-0000-000000000004","email":"driver@waypoint.lk"}'::jsonb,
    NOW(), NOW(), NOW()
  )
ON CONFLICT DO NOTHING;


-- ── 3. Insert application user profiles ──────────────────────────────────────
INSERT INTO public.users (id, email, full_name, role, outlet_id, depot, vehicle_id) VALUES
  -- Loader (assigned to Peliyagoda depot)
  ('a1000000-0000-0000-0000-000000000001'::uuid, 'loader@waypoint.lk', 'Kamal Perera', 'loader', NULL, 'Peliyagoda', NULL),
  -- Store Manager (assigned to first outlet)
  ('a2000000-0000-0000-0000-000000000002'::uuid, 'storemanager@waypoint.lk', 'Nimal Fernando', 'store_manager', 'OUT001', NULL, NULL),
  -- Dispatcher (no outlet or depot assignment needed)
  ('a3000000-0000-0000-0000-000000000003'::uuid, 'dispatcher@waypoint.lk', 'Sunil Jayawardena', 'dispatcher', NULL, 'Peliyagoda', NULL),
  -- Driver (assigned to depot and a vehicle)
  ('a4000000-0000-0000-0000-000000000004'::uuid, 'driver@waypoint.lk', 'Ruwan Silva', 'driver', NULL, 'Peliyagoda', NULL)
ON CONFLICT (id) DO UPDATE SET
  email = EXCLUDED.email,
  full_name = EXCLUDED.full_name,
  role = EXCLUDED.role,
  outlet_id = EXCLUDED.outlet_id,
  depot = EXCLUDED.depot,
  vehicle_id = EXCLUDED.vehicle_id;
