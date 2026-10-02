# Error 404 - Waypoint

## Project Structure
```text
TeamName_SolutionName/
│
├── apps/
│   ├── web/
│   └── mobile/
│
├── backend/
│   └── api/
│
├── supabase/
│   ├── migrations/
│   └── seed/
│
├── docs/
│   ├── architecture.md
│   ├── data-model.md
│   └── ai-disclosure.md
│
├── scripts/
│
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
└── LICENSE
```

## Frontend Apps
- `web/`: role-aware web console for Store Manager, Dispatcher, and Loader.
- `mobile/`: verified phone-first Driver browser preview.
- `mobile-native/`: React Native / Expo Driver app entrypoint for Android and iOS.

Both apps use seeded in-memory/localStorage state so the UI can be exercised without Supabase or FastAPI.

## Getting Started

### Prerequisites
- Node.js (v18+)
- Docker & Docker Compose
- Supabase CLI

### Setup
1. Clone the repository
2. Copy `.env.example` to `.env` and fill in necessary secrets
3. Start local services:
   ```bash
   docker-compose up -d
   ```

### Run Frontends
```bash
cd web && npm install && npm run dev
cd mobile && npm install && npm run dev
cd mobile-native && npm install && npx expo start
```
