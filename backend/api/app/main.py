"""
Waypoint Backend — FastAPI application factory.

This is the entry point for the entire API.

Design decisions:
- Application is created inside create_app() so it can be instantiated
  cleanly in tests without side effects.
- Routers are registered with /api/v1 prefix for versioning.
- CORS origins are loaded from environment — never hardcoded.
- Exception handlers are registered centrally via register_exception_handlers().
- Structured JSON logging is configured at startup.
"""
from __future__ import annotations

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pythonjsonlogger import jsonlogger

from app.api.routes import auth, deliveries, health, orders, outlets, planning, sync, trips, vehicles
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers


def _configure_logging(log_level: str) -> None:
    """Set up structured JSON logging for the application."""
    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level.upper())

    # Quieten noisy third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Called once at startup by uvicorn (see __main__ block) and also
    by the test suite so each test run gets a clean instance.
    """
    settings = get_settings()

    _configure_logging(settings.LOG_LEVEL)
    logger = logging.getLogger(__name__)
    logger.info(
        "Starting Waypoint API",
        extra={
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "env": settings.ENVIRONMENT,
        },
    )

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Waypoint delivery planning and operational system API.\n\n"
            "Supports four roles: **Dispatcher**, **Loader**, **Driver**, **Store Manager**.\n\n"
            "All endpoints are versioned under `/api/v1/`."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Origins loaded from CORS_ORIGINS env var — never use "*" in production.
    allowed_origins = settings.cors_origins_list
    logger.info("CORS allowed origins configured", extra={"origins": allowed_origins})

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    # ── Exception handlers ────────────────────────────────────────────────────
    register_exception_handlers(app)

    # ── Routers ───────────────────────────────────────────────────────────────
    # /health is at root — no version prefix (useful for load balancer checks)
    app.include_router(health.router)

    # /api/v1/... — all application routes live here
    app.include_router(auth.router)      # GET /api/v1/auth/me          Phase 3 ✅
    app.include_router(outlets.router)   # GET /api/v1/outlets           Phase 4 ✅
    app.include_router(vehicles.router)  # GET /api/v1/vehicles          Phase 4 ✅
    app.include_router(orders.router)    # POST/GET/PATCH /api/v1/orders Phase 4 ✅
    app.include_router(trips.router)     # GET/PATCH /api/v1/trips       Phase 4 ✅
    app.include_router(planning.router)  # POST/GET  /api/v1/planning   Phase 5 ✅
    app.include_router(deliveries.router) # POST/GET  /api/v1/deliveries Phase 6 ✅
    app.include_router(sync.router)       # POST/GET  /api/v1/sync       Phase 7 ✅

    logger.info("Waypoint API ready", extra={"docs": "/docs"})
    return app


# ── Application instance (used by uvicorn) ────────────────────────────────────
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=not settings.is_production,
        log_level=settings.LOG_LEVEL.lower(),
    )
