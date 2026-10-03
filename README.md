# Error 404 - Waypoint

# Waypoint

Error404 Waypoint is a four-role delivery operations system: Store Manager, Dispatcher, Loader, and Driver. The repository contains a responsive React web app, a phone-first driver web app, an Expo/React Native driver source, a FastAPI API, and Supabase migrations.

## Repository Layout

- `web/`: responsive Store Manager, Dispatcher, and Loader web application.
- `mobile/`: responsive driver web application and browser verification target.
- `mobile-native/`: Expo/React Native driver source and native API/offline adapter.
- `backend/api/`: FastAPI API, role authorization, allocation engine, delivery workflow, and offline sync.
- `supabase/migrations/`: database schema and RLS policies.
- `scripts/seed.py`: reference-data, demo-user, and walkthrough seed script.
- `docs/`: architecture, data model, allocation rules, and AI disclosure.
- `phase8.md`: local implementation instructions; ignored and intentionally not committed.

See [SETUP.md](SETUP.md) for the complete Phase 8 setup, secret-handling rules, migration/seed steps, run commands, verification commands, and judge walkthrough.

## Prerequisites

- Node.js 18+
- Python 3.12
- Docker Compose
- A Supabase project with Auth enabled
- Supabase CLI or access to the Supabase SQL editor

## Local Configuration

Never commit secrets. Copy the templates and fill them locally:

```bash
cp .env.example .env
cp web/.env.example web/.env.local
cp mobile/.env.example mobile/.env.local
cp mobile-native/.env.example mobile-native/.env.local
```

Required root `.env` values are `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` (server only), `SUPABASE_JWT_SECRET`, `DATABASE_URL`, and `CORS_ORIGINS`.

Browser clients need `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, and `VITE_API_BASE_URL`. Native uses the corresponding `EXPO_PUBLIC_*` variables. Service-role keys must never appear in either client environment.

## Database And Seed Setup

Apply migrations in filename order:

```bash
supabase db push
```

Or run the SQL files in `supabase/migrations/` through the Supabase SQL editor. Then seed reference data and demo accounts:

```bash
cd backend/api
source .venv/bin/activate
python ../../scripts/seed.py
```

The seed script expects reference CSV files under local `data/`. Those datasets are ignored and must not be committed or uploaded.

## Run The System

```bash
cd backend/api
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

In separate terminals:

```bash
npm run dev:web
npm run dev:mobile
npm run dev:native
```

Compose starts the API service and requires `.env` for real Supabase access:

```bash
docker compose up --build
```

## Verification

```bash
npm run build
npm run test:backend
```

A full four-role E2E run requires configured Supabase credentials, applied migrations, seeded demo accounts, and a running API. The golden walkthrough is: Store Manager creates/submits an order; Dispatcher sees it, generates a plan, reviews reasons, and confirms; Loader sees the trip, verifies reverse load positions, acknowledges, and records a shortfall; Driver sees only the assigned trip, acknowledges, departs, records online/offline delivery, restarts, and syncs; Store Manager loads the delivery and confirms receipt.

## Git Safety

```bash
git status --short --ignored
git diff --check
git add .
git diff --cached --name-only
```

Before committing, confirm `.env`, `*.local`, keys, credentials, datasets, `phase8.md`, `node_modules`, `dist`, Python virtual environments, and caches are absent from the staged file list.
cd mobile && npm install && npm run dev
cd mobile-native && npm install && npx expo start
```
