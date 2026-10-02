"""
Waypoint Backend — Supabase client singleton.

Phase 2: Database connectivity.

The backend uses the Supabase Python client with the SERVICE_ROLE_KEY.
This key bypasses Row-Level Security — the API is responsible for
enforcing all authorization logic itself (via require_role dependency).

IMPORTANT:
  - Never pass the service-role key to the frontend or mobile client.
  - Never log the service-role key.
  - The anon key is for Supabase Auth SDK calls from the frontend only.
"""
from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    """
    Return a cached Supabase client using the service-role key.

    lru_cache ensures one client instance per process.
    The client is thread-safe for concurrent FastAPI requests.
    """
    settings = get_settings()

    if not settings.SUPABASE_URL:
        raise RuntimeError("SUPABASE_URL is not configured.")
    if not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is not configured.")

    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_ROLE_KEY,
    )
