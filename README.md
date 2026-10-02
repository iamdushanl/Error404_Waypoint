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
