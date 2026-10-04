# ============================================================
# Waypoint Web Console — Dockerfile
#
# Multi-stage build:
#   Stage 1 (builder) : installs Node deps and builds the Vite SPA
#   Stage 2 (runtime) : lightweight nginx image serves the static bundle
#
# Build-time env vars (injected via docker-compose build.args):
#   VITE_SUPABASE_URL      — your Supabase project URL
#   VITE_SUPABASE_ANON_KEY — Supabase anon/public key
#   VITE_API_BASE_URL      — FastAPI backend URL (default: http://api:8000)
# ============================================================

# ── Stage 1: Build ───────────────────────────────────────────────────────────
FROM node:20-slim AS builder

WORKDIR /app

# Layer-cache friendly: install deps before copying full source
COPY package.json package-lock.json ./
RUN npm ci

# Copy source
COPY . .

# Accept build args and expose as Vite env vars at build time
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL \
    VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY \
    VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

# ── Stage 2: Serve ───────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runtime

# Remove the default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy our SPA-aware nginx config
COPY nginx.conf /etc/nginx/conf.d/waypoint.conf

# Copy the Vite build output
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

# nginx runs as PID 1 in foreground mode
CMD ["nginx", "-g", "daemon off;"]
