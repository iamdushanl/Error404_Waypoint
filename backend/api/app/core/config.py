"""
Waypoint Backend — core configuration.

Loads all settings from environment variables / .env file.
Use pydantic-settings so every variable is validated and typed at startup.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings validated at startup."""

    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ─────────────────────────────────────────
    APP_NAME: str = "Waypoint API"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"  # development | production
    DEBUG: bool = False
    PORT: int = 8000

    # ── Supabase ─────────────────────────────────────────────
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""  # NEVER expose to client
    SUPABASE_JWT_SECRET: str = ""        # Used to verify Supabase JWTs

    # ── Database (direct connection, Phase 2+) ───────────────
    DATABASE_URL: str = ""

    # ── CORS ─────────────────────────────────────────────────
    # Comma-separated list of allowed origins.
    # Example: "http://localhost:5173,https://waypoint.vercel.app"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str) -> str:
        return v

    @property
    def cors_origins_list(self) -> List[str]:
        """Return CORS origins as a list, stripping whitespace."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    # ── Logging ──────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    # ── Security ─────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache
def get_settings() -> Settings:
    """
    Return a cached Settings instance.

    Using lru_cache means the .env file is only read once.
    In tests, call get_settings.cache_clear() to reload.
    """
    return Settings()
