# System Architecture — Waypoint

*Error404 · Tech-Triathlon 2026 · Hackathon submission*

---

## Overview

Waypoint is a delivery planning and operational system for **Waypoint Group**, serving three retail brands across 120 outlets via a fleet of 60 vehicles from two depots (Peliyagoda and Kandy).

The system supports four user roles: **Dispatcher**, **Loader**, **Driver**, and **Store Manager**, across a responsive web app and a mobile app.

---

## High-Level Architecture

```mermaid
graph TB
    subgraph Clients
        Web["Web App\nweb/\nReact + TypeScript\nHosted: Vercel"]
        Mobile["Driver Mobile App\nmobile/\nReact + TypeScript"]
    end

    subgraph Backend["Backend (AWS Container)"]
        API["FastAPI\nbackend/api\nPython 3.13 · Uvicorn"]
        Auth["JWT Verification\nSupabase token → role claims"]
        Alloc["Allocation Engine\nallocation_service.py"]
        Sync["Sync Engine\nsync_service.py"]
    end

    subgraph Supabase
        SupaAuth["Supabase Auth\nOTP · Google OAuth\nJWT issuance"]
        DB[("PostgreSQL\nOutlets · Vehicles\nOrders · Trips\nDeliveries · Sync events")]
    end

    Web -->|"HTTPS /api/v1/"| API
    Mobile -->|"HTTPS /api/v1/"| API
    Mobile -.->|"Offline queue\n→ POST /api/v1/sync"| API

    API --> Auth
    Auth -->|"Verify JWT"| SupaAuth
    API --> Alloc
    API --> Sync
    API -->|"Supabase client\n(service-role)"| DB

    Web -->|"Supabase Auth UI"| SupaAuth
    Mobile -->|"Supabase Auth SDK"| SupaAuth
```

---

## Authentication Flow

```mermaid
sequenceDiagram
    participant C as Client (Web/Mobile)
    participant SA as Supabase Auth
    participant FA as FastAPI
    participant DB as Supabase DB

    C->>SA: Sign in (OTP / Google OAuth)
    SA-->>C: JWT access token
    C->>FA: Request + Bearer JWT
    FA->>FA: Verify JWT signature (SUPABASE_JWT_SECRET)
    FA->>DB: Look up user role from users table
    DB-->>FA: {role: "dispatcher"}
    FA->>FA: Check role authorization
    FA-->>C: API response
```

---

## Offline Sync Flow (Driver)

```mermaid
sequenceDiagram
    participant D as Driver (Phone)
    participant App as Mobile App
    participant FA as FastAPI
    participant DB as Supabase DB

    D->>App: Record delivery outcome
    App->>App: Save to local queue\n(operation_id = UUID)
    Note over App: No connectivity — Kandy corridor

    D->>App: Connectivity returns
    App->>FA: POST /api/v1/sync\n{operation_id, ...}
    FA->>DB: Check operation_id already processed?
    alt Already processed (duplicate)
        FA-->>App: 200 OK (idempotent)
    else First time
        FA->>DB: Apply delivery outcome
        FA->>DB: Record sync event
        FA-->>App: 200 OK
    end
```

---

## Components

### Frontend — `web/` (Vite + React + TypeScript)
- **Dispatcher**: Plan creation, vehicle allocation, live board, capacity forecast
- **Loader**: Load list, reverse-unload order, shortfall recording
- **Store Manager**: Order placement, delivery status, receipt confirmation

### Mobile App — `mobile/` + `mobile-native/`
- **Driver**: Route view, stop delivery recording, proof of delivery, offline mode, sync

### Backend API — `backend/api/` (FastAPI)
| Module | Responsibility |
|---|---|
| `core/config.py` | Environment-validated settings |
| `core/exceptions.py` | Centralised error handling |
| `api/deps.py` | JWT auth + role enforcement |
| `api/routes/` | Thin HTTP handlers |
| `services/allocation_service.py` | Planning engine (constraint-based) |
| `services/delivery_service.py` | Delivery state machine |
| `services/sync_service.py` | Idempotent offline sync |
| `repositories/` | Data access layer |

### Database — Supabase PostgreSQL
See [`data-model.md`](data-model.md) for full ERD.

### Hosting
| Component | Platform |
|---|---|
| Web frontend | Vercel |
| Backend API | AWS ECS / container |
| Database + Auth | Supabase |

---

## API Design

All application routes versioned at `/api/v1/`.

| Route group | Prefix |
|---|---|
| Health | `GET /health` |
| Auth | `/api/v1/auth/` |
| Orders | `/api/v1/orders/` |
| Outlets | `/api/v1/outlets/` |
| Vehicles | `/api/v1/vehicles/` |
| Planning | `/api/v1/planning/` |
| Trips | `/api/v1/trips/` |
| Deliveries | `/api/v1/deliveries/` |
| Offline Sync | `POST /api/v1/sync` |

See [`api-contract.md`](api-contract.md) for full request/response schemas.

---

## Deployment

```bash
# Full local stack
docker compose up

# Backend only
cd backend/api
uvicorn app.main:app --reload --port 8000
```
