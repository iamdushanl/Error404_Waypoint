"""
Outlet repository — read-only access to the outlets reference table.
Outlets are seeded from the competition CSV; they are never mutated via the API.
"""
from __future__ import annotations

from supabase import Client


class OutletRepository:
    TABLE = "outlets"

    def __init__(self, client: Client) -> None:
        self._db = client

    def list(
        self,
        *,
        brand: str | None = None,
        district: str | None = None,
        depot: str | None = None,
        parking_constraint: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Return (rows, total_count) with optional filters."""
        q = self._db.table(self.TABLE).select("*", count="exact")

        if brand:
            q = q.eq("brand", brand)
        if district:
            q = q.ilike("district", f"%{district}%")
        if depot:
            q = q.eq("depot", depot)
        if parking_constraint:
            q = q.eq("parking_constraint", parking_constraint)

        q = q.order("outlet_id").range(offset, offset + limit - 1)
        resp = q.execute()
        return resp.data or [], resp.count or 0

    def get(self, outlet_id: str) -> dict | None:
        """Return a single outlet by ID, or None."""
        resp = (
            self._db.table(self.TABLE)
            .select("*")
            .eq("outlet_id", outlet_id)
            .maybe_single()
            .execute()
        )
        return resp.data
