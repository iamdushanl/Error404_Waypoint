"""
Vehicle repository — read-only access to the vehicles reference table.
Vehicles are seeded from the competition CSV; they are never mutated via the API.
"""
from __future__ import annotations

from supabase import Client


class VehicleRepository:
    TABLE = "vehicles"

    def __init__(self, client: Client) -> None:
        self._db = client

    def list(
        self,
        *,
        depot: str | None = None,
        type: str | None = None,
        temp: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Return (rows, total_count) with optional filters."""
        q = self._db.table(self.TABLE).select("*", count="exact")

        if depot:
            q = q.eq("depot", depot)
        if type:
            q = q.eq("type", type)
        if temp:
            q = q.eq("temp", temp)

        q = q.order("vehicle_id").range(offset, offset + limit - 1)
        resp = q.execute()
        return resp.data or [], resp.count or 0

    def get(self, vehicle_id: str) -> dict | None:
        resp = (
            self._db.table(self.TABLE)
            .select("*")
            .eq("vehicle_id", vehicle_id)
            .maybe_single()
            .execute()
        )
        return resp.data

    def list_by_depot(self, depot: str) -> list[dict]:
        """Return all vehicles for a depot — used by the allocation engine."""
        resp = (
            self._db.table(self.TABLE)
            .select("*")
            .eq("depot", depot)
            .order("vehicle_id")
            .execute()
        )
        return resp.data or []
