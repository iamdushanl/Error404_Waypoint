# Error 404 - Waypoint

> **Tech-Triathlon 2026 · Hackathon Submission**
>
> 🌐 **Live Deployed Web Console:** [https://error404-waypoint-beryl.vercel.app](https://error404-waypoint-beryl.vercel.app) *(or local `http://localhost:3000`)*<br />
> 📱 **Live Deployed Driver Mobile:** [https://error404-waypoint-e6ki.vercel.app](https://error404-waypoint-e6ki.vercel.app) *(or local `http://localhost:5174`)*<br />
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

Error404 Waypoint is an end-to-end four-role delivery operations system designed for fresh supply chains: **Store Manager**, **Dispatcher**, **Loader**, and **Driver**. The repository provides a responsive multi-role React web console, a phone-first driver web app, an Expo/React Native driver app, a FastAPI backend with constraint-based allocation and sync engines, and Supabase database migrations with row-level security.

---

## Completed Features & Recent Updates

### 1. Email/Password Authentication & Staff Self-Registration
- **Replaced OTP with Email/Password**: Full migration from OTP to direct Supabase email/password authentication.
- **Dual-Mode Auth Console**: Unified interface with seamless switching between **Sign In** and **Create Account (Register)**.
- **Automatic Role Detection**: System automatically detects operational roles from the staff email handle:
  - `dispatcher*` / `dispatch*` &rarr; **Dispatcher** (Control Tower: route optimization, constraints & allocation)
  - `loader*` &rarr; **Loader** (Depot Loading Bay: reverse-unload sequencing & shortfalls)
  - `driver*` &rarr; **Driver** (Fleet Operations: route execution & offline proof-of-delivery)
  - `store*` / `manager*` / `outlet*` (or default) &rarr; **Store Manager** (Retail Outlet: ordering & receipt confirmation)
- **Live Role Detection Card**: Dynamically previews the detected role badge, workspace scope, assigned operational node, and core screens as the user types.
- **Client-Side Security Validation**: Includes a 4-tier visual password strength meter and real-time password confirmation match verification.
- **Station Persistence**: "Keep me signed in on this station" toggle.
- **Interactive Role Showcase**: Left hero section allows interactive previewing of each role's responsibilities, node assignments, and workflow scope.
- **Quick-Fill Demo Accounts**: One-click chips to quickly fill credentials for all 4 operational roles.

### 2. Auto-Provisioning & Database Migration
- **Self-Registration RLS Policies** (`supabase/migrations/007_allow_user_registration.sql`):
  - Adds `users_insert_own` and `users_update_own` row-level security policies to `public.users` so newly registered authenticated staff can provision their application profiles.
- **Backend Auto-Provisioning Middleware** (`backend/api/app/api/deps.py`):
  - Automatically identifies authenticated users without an existing `public.users` profile and provisions them with appropriate roles, default depot (`Peliyagoda`), or assigned outlet (`OUT001`).

### 3. Docker Full-Stack Deployment (Phase 9)
- Single-command orchestration via `docker-compose.yml`:
  - `waypoint-api`: FastAPI backend with health checks and OpenAPI docs on port `8000`.
  - `waypoint-web`: Vite React SPA served through Nginx on port `3000`.
  - `waypoint-seed`: Automated database seeder that loads reference CSVs and initializes demo accounts.

### 4. Offline/Online Sync Engine (Phase 7 & 8)
- Offline delivery execution support for drivers in low-connectivity areas.
- Stable client-side `operation_id` tracking with idempotent queued replay via `/api/v1/sync`.
- Complete 4-role closed-loop lifecycle from order placement to delivery receipt confirmation.

---

## Repository Layout

- `web/`: Responsive React web console for Store Managers, Dispatchers, and Loaders.
- `mobile/`: Mobile web application tailored for Driver route execution and browser verification.
- `mobile-native/`: Expo / React Native mobile driver source and native offline adapter.
- `backend/api/`: FastAPI backend (auth verification, allocation engine, delivery workflows, offline sync).
- `supabase/migrations/`: Database schema, table definitions, and row-level security (RLS) policies (`001` through `007`).
- `scripts/`: Seed scripts (`seed.py`), migration helpers, and containerized seed runners.
- `docs/`: Architecture specification, data model documentation, allocation constraint rules, and AI disclosure.
- `SETUP.md`: Detailed configuration instructions, environment secrets guide, and judge walkthrough.

---

## Prerequisites

- Node.js 18+
- Python 3.12
- Docker & Docker Compose
- A Supabase project with Auth enabled (Email & Password provider active)
- Supabase CLI or Supabase SQL Editor

---

## Local Configuration

Never commit secrets or environment files. Copy the provided templates and configure them locally:

```bash
cp .env.example .env
cp web/.env.example web/.env.local
cp mobile/.env.example mobile/.env.local
cp mobile-native/.env.example mobile-native/.env.local
```

### Environment Variables Overview

- **Root `.env` (Backend / Docker)**:
  `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` (server-only), `SUPABASE_JWT_SECRET`, `DATABASE_URL`, `CORS_ORIGINS`.
- **Frontend Clients (`web/.env.local`, `mobile/.env.local`)**:
  `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_BASE_URL`.
- **Native App (`mobile-native/.env.local`)**:
  `EXPO_PUBLIC_SUPABASE_URL`, `EXPO_PUBLIC_SUPABASE_ANON_KEY`, `EXPO_PUBLIC_API_BASE_URL`.

*Note: The `SUPABASE_SERVICE_ROLE_KEY` must never be exposed to browser or native client environments.*

---

## Database Migrations & Seeding

1. **Apply Migrations** (in sequential order from `001` to `007`):
   ```bash
   supabase db push
   ```
   *Or execute `supabase/migrations/*.sql` directly in the Supabase SQL Editor.*

2. **Seed Reference Data & Demo Accounts**:
   ```bash
   cd backend/api
   python3.12 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   cd ../..
   backend/api/.venv/bin/python scripts/seed.py
   ```
   *(CSVs should be placed in `data/`, which is gitignored. Use `--skip-csv` if reference CSVs are omitted.)*

### Demo User Accounts

| Role | Demo Email | Password | Assigned Scope |
|------|------------|----------|----------------|
| **Dispatcher** | `dispatcher@waypoint.lk` / `dispatcher@waypoint.demo` | `waypoint123` / `WaypointDemo2026!` | Central Operations & Peliyagoda |
| **Loader** | `loader@waypoint.lk` / `loader@waypoint.demo` | `waypoint123` / `WaypointDemo2026!` | Depot Loading Bay & Peliyagoda |
| **Store Manager** | `storemanager@waypoint.lk` / `manager@waypoint.demo` | `waypoint123` / `WaypointDemo2026!` | Retail Outlet OUT001 |
| **Driver** | `driver@waypoint.lk` / `driver@waypoint.demo` | `waypoint123` / `WaypointDemo2026!` | Vehicle WP-CAB-9241 |

*Staff can also self-register with any email matching the role keyword (e.g. `dispatcher@company.com`).*

---

## Running the Application

### Option A: Docker Compose Full Stack (Recommended)

Runs the API, Nginx-served Web console, and Seeder with a single command:

```bash
docker compose up --build
```

- **Web Console**: [http://localhost:3000](http://localhost:3000)
- **FastAPI Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

### Option B: Local Development

1. **Start Backend API**:
   ```bash
   cd backend/api
   source .venv/bin/activate
   uvicorn app.main:app --reload --port 8000
   ```

2. **Start Web Console** (Store Manager, Dispatcher, Loader):
   ```bash
   npm run dev:web
   ```

3. **Start Driver Mobile Web App**:
   ```bash
   npm run dev:mobile
   ```

4. **Start Driver Native App (Expo)**:
   ```bash
   npm run dev:native
   ```

---

## Verification & Testing

Verify that both frontend bundles and backend tests compile and pass cleanly:

```bash
# Build frontend web and mobile bundles
npm run build

# Run backend test suite (94 tests, 100% pass)
npm run test:backend

# Automated full 4-role golden walkthrough verification
python scripts/verify_e2e_flow.py

# Syntax and bytecode compilation verification
python3 -m compileall -q backend/api/app backend/api/tests scripts
```

---

## Golden Walkthrough

1. **Store Manager**: Sign in (or register new staff account), draft a next-day order for Outlet OUT001, and submit before cutoff.
2. **Dispatcher**: Sign in to the Control Tower, review the order queue, execute the allocation engine, inspect constraint/deferral reasons, and confirm the plan.
3. **Loader**: Sign in at the Depot Bay, verify pallet load sequence in reverse-drop order, acknowledge the load list, and record shortfalls if needed.
4. **Driver**: Sign in to fleet operations, acknowledge assigned trips, record delivery stops (supporting offline queueing & re-sync), and collect digital proof of delivery.
5. **Store Manager**: Inspect the completed delivery and record verified goods receipt.

---

## Git Safety & Cleanliness

Before committing, ensure that local secrets, datasets, and build artifacts remain uncommitted:

```bash
git status --short --ignored
git diff --check
git diff --cached --name-only
```

Strictly excluded from git commits:
- `.env`, `.env.local`, `*.local`
- Confidential datasets in `data/`
- Local guide notes (`phase8.md`)
- `node_modules/`, `dist/`, `.venv/`, `__pycache__/`, `.pytest_cache/`
