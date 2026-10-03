# Backend Handoff

This folder is intentionally frontend-only. The backend team can add Supabase and FastAPI without changing the visual role boundaries.

## Replace these seams

- `web/src/App.tsx`: replace the preview auth action and `localStorage` role session with Supabase passwordless email/phone and Google OAuth.
- `web/src/App.tsx`: replace seeded orders, vehicles, capacity, receipt, and deferral data with typed API/query adapters.
- `mobile/src/App.tsx`: replace seeded driver route and outcome transitions with route and delivery endpoints.
- `mobile-native/App.tsx`: use the same API adapter as the native driver app.

## Required backend contracts

- Auth: passwordless OTP, Google OAuth, session refresh, and role claims for `store_manager`, `dispatcher`, `loader`, and `driver`.
- Orders: create draft, submit order, list queue, confirm receipt, report issue, and expose delivery status.
- Planning: list vehicles, validate weight/volume/temperature/window constraints, assign or defer orders, publish plan.
- Loading: reverse-unload load list, shortfall recording, plan-change notifications.
- Driver: route payload, stop outcome, proof-of-delivery metadata, idempotency key, offline replay.
- Sync: idempotent delivery writes keyed by a client-generated operation ID; replay must not duplicate records.

## Environment variables to add later

Create local `.env` files from `.env.example` when the backend is connected. Never commit Supabase service-role keys, FastAPI secrets, or OAuth client secrets.

## Frontend verification

From `codebase/`:

```bash
npm run build
```

The checked-in source does not require a database or API to render its seeded workflow states.
