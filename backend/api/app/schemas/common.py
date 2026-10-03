"""
Waypoint — shared Pydantic schemas.

Pagination wrapper used by all list endpoints.
"""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PagedResponse(BaseModel, Generic[T]):
    """Standard paginated list response."""
    data: list[T]
    total: int
    limit: int
    offset: int
