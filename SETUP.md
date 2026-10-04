# Waypoint Setup and Handoff

This document is the complete local setup guide for the Phase 8 implementation.

## Security first

Never commit `.env`, `.env.local`, service-role keys, JWT secrets, database passwords, Supabase tokens, private keys, or competition datasets. `.gitignore` explicitly excludes them, and `phase8.md` is local-only and ignored.

The browser and native apps must receive only the Supabase URL, anon key, and API base URL. `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, and `DATABASE_URL` belong only in the backend/root `.env`.

## Prerequisites

- Node.js 18+
- Python 3.12
- Docker Compose
- A Supabase project with Auth enabled
- Supabase SQL Editor or Supabase CLI

## Configure

```bash
cp .env.example .env
cp web/.env.example web/.env.local
cp mobile/.env.example mobile/.env.local
cp mobile-native/.env.example mobile-native/.env.local
```

Fill the files with the values from your secret manager. Do not paste secrets into tracked files.

## Database and seed

Apply migrations in order:

```bash
supabase db push
```

Or execute `supabase/migrations/*.sql` in the Supabase SQL Editor. Put the confidential reference CSVs in local `data/`, then seed:

```bash
cd backend/api
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ../..
backend/api/.venv/bin/python scripts/seed.py
```

The seed script creates the four demo profiles and sample workflow data. Demo passwords are only for local/demo provisioning; use Supabase OTP/Google in the frontend.

## Run

Backend:

```bash
cd backend/api
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Web console:

```bash
npm run dev:web
```

Driver browser app:

```bash
npm run dev:mobile
```

Native driver app:

```bash
npm run dev:native
```

Docker API stack only (backend + health check):

```bash
docker compose up api --build
```

## Phase 9: Docker full stack

Runs **all three services** — API, web console, and seed runner — from a single command.

### Prerequisites

1. Docker Desktop running.
2. Root `.env` filled in (copy from `.env.example`). Make sure these are set:

```
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_JWT_SECRET=...
VITE_SUPABASE_URL=...        # same as SUPABASE_URL
VITE_SUPABASE_ANON_KEY=...   # Supabase anon/public key
VITE_API_BASE_URL=http://localhost:8000
SEED_SKIP_CSV=0              # 1 if data/ CSVs are not present
```

3. Place confidential CSV files in `data/` (gitignored). Required by the seed runner unless `SEED_SKIP_CSV=1`.

### Start the full stack

```bash
docker compose up --build
```

Services and ports:

| Service | Container name  | Host port | Notes                          |
|---------|----------------|-----------|--------------------------------|
| api     | waypoint-api   | 8000      | FastAPI + `/docs` + `/health` |
| web     | waypoint-web   | 3000      | Nginx serving the Vite SPA    |
| seed    | waypoint-seed  | —         | Exits after seeding (once)    |

- **Web console**: http://localhost:3000
- **API docs**: http://localhost:8000/docs
- **Health**: http://localhost:8000/health

### Re-run seed only (without rebuilding)

```bash
docker compose run --rm seed
```

### Backend only (for local frontend dev)

```bash
docker compose up api --build
```

Then run the frontend dev server locally:

```bash
npm run dev:web
```

## Verification

```bash
npm run build
npm run test:backend
backend/api/.venv/bin/python -m compileall -q backend/api/app backend/api/tests scripts
```

Expected backend result: all tests pass. A full cross-role E2E requires the configured Supabase project and seeded data.

## Golden walkthrough

1. Store Manager signs in with OTP or Google, creates and submits an order.
2. Dispatcher sees the submitted order, generates a plan, reviews trips and machine-readable deferral reasons, then confirms the plan.
3. Loader sees the confirmed backend trip in reverse load order, acknowledges it, and records a shortfall.
4. Driver signs in, sees only the assigned trip, records delivery online or offline, restarts with the operation still queued, then syncs.
5. Store Manager loads the backend delivery record and confirms receipt.

## Architecture boundary

The backend/database is the source of truth. UI components call typed adapters under `web/src/api`, `mobile/src/api.ts`, and `mobile-native/api.ts`; allocation and delivery validation remain in FastAPI. Offline operations use one stable `operation_id` through retries and are replayed through `/api/v1/sync`.
