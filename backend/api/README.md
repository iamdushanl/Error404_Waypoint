# Waypoint Backend API

FastAPI backend for the **Waypoint** delivery planning system.

Built for Tech-Triathlon 2026 — Error404 team.

---

## Quick Start (Local Development)

```bash
cd backend/api

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp ../../.env.example .env
# Edit .env and fill in SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_JWT_SECRET

# Start the development server
uvicorn app.main:app --reload --port 8000
```

Visit:
- API: http://localhost:8000
- Health: http://localhost:8000/health
- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## Running Tests

```bash
cd backend/api
pytest tests/ -v
```

---

## Docker

Build and run the container:

```bash
cd backend/api
docker build -t waypoint-api .
docker run -p 8000:8000 --env-file ../../.env waypoint-api
```

Or use the root `docker-compose.yml` to start the full stack:

```bash
# From repository root
docker compose up
```

---

## Project Structure

```
backend/api/
├── app/
│   ├── main.py                  ← FastAPI application factory
│   ├── core/
│   │   ├── config.py            ← pydantic-settings (env vars)
│   │   └── exceptions.py        ← error handlers + domain errors
│   ├── api/
│   │   ├── deps.py              ← shared FastAPI dependencies (auth)
│   │   └── routes/
│   │       ├── health.py        ← GET /health
│   │       ├── auth.py          ← GET /api/v1/auth/me       (Phase 3)
│   │       ├── orders.py        ← /api/v1/orders            (Phase 4)
│   │       ├── outlets.py       ← /api/v1/outlets           (Phase 4)
│   │       ├── vehicles.py      ← /api/v1/vehicles          (Phase 4)
│   │       ├── planning.py      ← /api/v1/planning          (Phase 5)
│   │       ├── trips.py         ← /api/v1/trips             (Phase 6)
│   │       ├── deliveries.py    ← /api/v1/deliveries        (Phase 6)
│   │       └── sync.py          ← /api/v1/sync              (Phase 7)
│   ├── db/
│   │   └── session.py           ← Supabase client singleton (Phase 2)
│   ├── models/                  ← SQLAlchemy/DB models       (Phase 2)
│   ├── schemas/                 ← Pydantic request/response  (Phase 4+)
│   ├── repositories/            ← Data access layer          (Phase 4+)
│   └── services/
│       ├── allocation_service.py ← Planning engine          (Phase 5)
│       ├── delivery_service.py  ← Delivery workflow         (Phase 6)
│       └── sync_service.py      ← Offline sync              (Phase 7)
├── tests/
│   └── test_health.py
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## Environment Variables

Copy `../../.env.example` → `.env` and fill in values.

| Variable | Description | Required |
|---|---|---|
| `ENVIRONMENT` | `development` or `production` | Yes |
| `PORT` | API port (default: 8000) | No |
| `SUPABASE_URL` | Your Supabase project URL | Phase 2 |
| `SUPABASE_ANON_KEY` | Supabase anon/public key | Phase 2 |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key — **NEVER expose to client** | Phase 2 |
| `SUPABASE_JWT_SECRET` | JWT secret for token verification | Phase 3 |
| `DATABASE_URL` | Direct PostgreSQL connection | Phase 2 |
| `CORS_ORIGINS` | Comma-separated allowed origins | Yes |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING` (default: INFO) | No |

---

## API Contract

See [`docs/api-contract.md`](../../docs/api-contract.md) for full request/response schemas.

---

## Implementation Phases

| Phase | Scope | Status |
|---|---|---|
| 0 | Repository audit | ✅ Done |
| 1 | FastAPI foundation, `/health`, config, CORS, Dockerfile | ✅ Done |
| 2 | Supabase connection, migrations, seed data | ✅ Done |
| 3 | JWT auth, `get_current_user`, role guards, `/auth/me` | ✅ Done |
| 4 | Domain model: outlets, vehicles, orders, trips | ✅ Done |
| 5 | Allocation engine + planning API | ✅ Done |
| 6 | Delivery workflow (complete, POD, receipt, shortfall) | ✅ Done |
| 7 | Offline sync (idempotent, keyed) | ✅ Done |
| 8 | Frontend/mobile integration | ✅ Done |
| 9 | Docker compose full stack + seed | ✅ Done |
