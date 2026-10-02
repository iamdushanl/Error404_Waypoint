"""
Waypoint Backend — centralised exception handling.

Defines:
  - WaypointError   : base application exception
  - HTTP exception handlers registered on the FastAPI app
  - Consistent JSON error response shape:

    {
        "error": {
            "code":    "ORDER_ALREADY_ALLOCATED",
            "message": "Human-readable description."
        }
    }
"""
from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


# ── Domain error codes ────────────────────────────────────────────────────────

class WaypointError(Exception):
    """Base class for all domain/application errors."""

    def __init__(
        self,
        code: str,
        message: str,
        http_status: int = status.HTTP_400_BAD_REQUEST,
    ) -> None:
        self.code = code
        self.message = message
        self.http_status = http_status
        super().__init__(message)


class AuthenticationError(WaypointError):
    def __init__(self, message: str = "Authentication required.") -> None:
        super().__init__("AUTHENTICATION_REQUIRED", message, status.HTTP_401_UNAUTHORIZED)


class AuthorizationError(WaypointError):
    def __init__(self, message: str = "You do not have permission to perform this action.") -> None:
        super().__init__("FORBIDDEN", message, status.HTTP_403_FORBIDDEN)


class NotFoundError(WaypointError):
    def __init__(self, resource: str, resource_id: str = "") -> None:
        detail = f"{resource} not found."
        if resource_id:
            detail = f"{resource} '{resource_id}' not found."
        super().__init__("NOT_FOUND", detail, status.HTTP_404_NOT_FOUND)


class ConflictError(WaypointError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, status.HTTP_409_CONFLICT)


class AllocationError(WaypointError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, status.HTTP_422_UNPROCESSABLE_ENTITY)


# ── Error response helpers ────────────────────────────────────────────────────

def _error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


# ── Exception handlers ────────────────────────────────────────────────────────

def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI application instance."""

    @app.exception_handler(WaypointError)
    async def waypoint_error_handler(request: Request, exc: WaypointError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content=_error_body(exc.code, exc.message),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Return a clean 422 without leaking internal Pydantic paths
        errors = exc.errors()
        first = errors[0] if errors else {}
        field = " → ".join(str(loc) for loc in first.get("loc", []))
        msg = first.get("msg", "Validation error.")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body(
                "VALIDATION_ERROR",
                f"Field '{field}': {msg}" if field else msg,
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        # Do NOT leak stack traces in production
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(
                "INTERNAL_SERVER_ERROR",
                "An unexpected error occurred. Please try again.",
            ),
        )
