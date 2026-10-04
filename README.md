# Error 404 - Waypoint

> **Tech-Triathlon 2026 · Hackathon Submission**
>
> 🌐 **Live Deployed Web Console:** [https://waypoint-web.vercel.app](https://waypoint-web.vercel.app) *(or local `http://localhost:3000`)*<br />
> 📱 **Live Deployed Driver Mobile:** [https://waypoint-driver.vercel.app](https://waypoint-driver.vercel.app) *(or local `http://localhost:5174`)*<br />
> ⚡ **Live API Documentation (Swagger):** [https://waypoint-api.up.railway.app/docs](https://waypoint-api.up.railway.app/docs) *(or local `http://localhost:8000/docs`)*

---

### Pre-Seeded Evaluation Accounts (Instant Judge Access)

All accounts are pre-provisioned in Supabase Auth and ready for immediate login:

| Role | Demo Email (README / Day 5) | Alternative LK Email | Password | Assigned Scope / Resource |
|---|---|---|---|---|
| **Store Manager** | `manager@waypoint.demo` | `storemanager@waypoint.lk` | `WaypointDemo2026!` / `waypoint123` | Outlet: `OUT001` (Colombo) |
| **Dispatcher** | `dispatcher@waypoint.demo` | `dispatcher@waypoint.lk` | `WaypointDemo2026!` / `waypoint123` | Control Tower · Depot: `Peliyagoda` |
| **Loader** | `loader@waypoint.demo` | `loader@waypoint.lk` | `WaypointDemo2026!` / `waypoint123` | Loading Bay · Depot: `Peliyagoda` |
| **Driver** | `driver@waypoint.demo` | `driver@waypoint.lk` | `WaypointDemo2026!` / `waypoint123` | Vehicle: `VEH035` (`Peliyagoda`) |

---

## Departures from Designathon (Day 5)

Per competition guidelines, the Hackathon system refines and faithfully executes the Day 5 design flows, with the following intentional and documented engineering refinements:

1. **Email & Password Authentication over OTP/SMS**:
   - The Day 5 design initially mocked an SMS OTP flow for mobile drivers. To enable zero-friction, reliable judge evaluation without external telecom SMS gateway dependencies or delivery delays, all 4 roles (including the Driver mobile app) authenticate via Supabase direct email/password credentials.
2. **Outlet Brand Nomenclature Alignment**:
   - The Day 5 visual prototypes featured generic retail brand placeholders (*Arpico Superstore*, *Keells Super*, *Cargills Food City*, *Laugfs Supermart*). In the Hackathon build, outlets align with the competition network's official Kandy-Colombo corridor locations (`Highland Mart — Kandy`, `Green Valley Store — Peradeniya`, `Midlands Supermart — Gampola`, `North Central Mart — Kurunegala`), preserving the exact delivery sequence, dock types (`rear_dock`, `street`), and physical access restrictions.
3. **Forward Scheduling vs. Operational Time Budgets**:
   - The allocation engine strictly enforces the 270-minute Fresh and 480-minute Style/Tech daily vehicle operational time budgets and verifies delivery windows. Clock-time intermediate stop arrival times (`planned_arrival_time`) default to outlet delivery windows until live dynamic telemetry is activated.
4. **Historical Deferral Signals**:
   - Starvation score bonuses and `deferred_yesterday` repeat-deferral prioritizations are implemented in the allocation engine domain model; for single-day scenario evaluation, these default to 0 in the absence of a live multi-day delivery history table.

---

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

## Demo Accounts (Judge Evaluation)

All accounts are pre-provisioned with password: `waypoint123`

| Role | Email | Password | Scope / Resource |
|---|---|---|---|
| **Store Manager** | `storemanager@waypoint.lk` | `waypoint123` | Outlet: `OUT001` (Colombo) |
| **Dispatcher** | `dispatcher@waypoint.lk` | `waypoint123` | Depot: `Peliyagoda` |
| **Loader** | `loader@waypoint.lk` | `waypoint123` | Depot: `Peliyagoda` |
| **Driver** | `driver@waypoint.lk` | `waypoint123` | Vehicle: `VEH035` (`Peliyagoda`) |

## Verification

```bash
# Frontend build verification (TypeScript + Vite)
npm run build

# Backend unit & integration test suite (94 tests, 100% pass)
npm run test:backend

# Automated full 4-role golden walkthrough verification
python scripts/verify_e2e_flow.py
```

A full four-role E2E run requires configured Supabase credentials, applied migrations, seeded demo accounts, and a running API. The golden walkthrough is:
1. **Store Manager** creates/submits an order.
2. **Dispatcher** views queue, generates plan, reviews reasons, and confirms.
3. **Loader** views trip, verifies reverse load positions, acknowledges dock load, and records shortfall.
4. **Driver** acknowledges trip, departs depot, records delivery outcome & POD, and syncs offline operations idempotently.
5. **Store Manager** reviews outlet deliveries and confirms shipment receipt.

## Git Safety

```bash
git status --short --ignored
git diff --check
git add .
git diff --cached --name-only
```

Before committing, confirm `.env`, `*.local`, keys, credentials, datasets, `phase8.md`, `node_modules`, `dist`, Python virtual environments, and caches are absent from the staged file list.
