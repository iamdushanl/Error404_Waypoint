"""Waypoint Backend — health route."""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns 200 when the API is running. Used by load balancers and judge walkthrough.",
)
async def health_check() -> HealthResponse:
    from app.core.config import get_settings

    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )
