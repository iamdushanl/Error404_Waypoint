"""
Trip repository — read/write trips and trip_stops.

Used by: Dispatcher (read all), Loader (read own depot), Driver (read own vehicle).
"""
from __future__ import annotations

from supabase import Client


class TripRepository:
    TABLE = "trips"
    STOPS_TABLE = "trip_stops"

    def __init__(self, client: Client) -> None:
        self._db = client

    # ── Queries ───────────────────────────────────────────────────────────────

    def list(
        self,
        *,
        plan_id: str | None = None,
        vehicle_id: str | None = None,
        depot: str | None = None,
        status: str | None = None,
        brand: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        q = self._db.table(self.TABLE).select("*", count="exact")

        if plan_id:
            q = q.eq("plan_id", plan_id)
        if vehicle_id:
            q = q.eq("vehicle_id", vehicle_id)
        if depot:
            q = q.eq("depot", depot)
        if status:
            q = q.eq("status", status)
        if brand:
            q = q.eq("brand", brand)

        q = q.order("created_at").range(offset, offset + limit - 1)
        resp = q.execute()
        return resp.data or [], resp.count or 0

    def get(self, trip_id: str) -> dict | None:
        resp = (
            self._db.table(self.TABLE)
            .select("*")
            .eq("id", trip_id)
            .maybe_single()
            .execute()
        )
        return resp.data if resp else None

    def get_with_stops(self, trip_id: str) -> dict | None:
        """Return trip + stops ordered by sequence_number."""
        resp = (
            self._db.table(self.TABLE)
            .select("*, trip_stops(*, outlets(outlet_id, district, window_open_time, window_close_time, dock_type, parking_constraint))")
            .eq("id", trip_id)
            .maybe_single()
            .execute()
        )
        if resp and resp.data:
            data = resp.data.copy()
            raw_stops = data.pop("trip_stops", [])
            # Sort stops by sequence_number
            data["stops"] = sorted(raw_stops, key=lambda s: s["sequence_number"])
            return data
        return None

    def get_stops(self, trip_id: str) -> list[dict]:
        resp = (
            self._db.table(self.STOPS_TABLE)
            .select("*")
            .eq("trip_id", trip_id)
            .order("sequence_number")
            .execute()
        )
        return resp.data or []

    def list_for_driver(self, vehicle_id: str) -> list[dict]:
        """All active trips for a driver's vehicle."""
        resp = (
            self._db.table(self.TABLE)
            .select("*")
            .eq("vehicle_id", vehicle_id)
            .in_("status", ["planned", "loading", "departed", "in_transit"])
            .order("trip_number")
            .execute()
        )
        return resp.data or []

    # ── Mutations ─────────────────────────────────────────────────────────────

    def create(self, payload: dict) -> dict:
        resp = self._db.table(self.TABLE).insert(payload).execute()
        return resp.data[0]

    def create_stops(self, stops: list[dict]) -> list[dict]:
        resp = self._db.table(self.STOPS_TABLE).insert(stops).execute()
        return resp.data or []

    def update_status(self, trip_id: str, status: str, extra: dict | None = None) -> dict | None:
        payload: dict = {"status": status}
        if extra:
            payload.update(extra)
        resp = (
            self._db.table(self.TABLE)
            .update(payload)
            .eq("id", trip_id)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def acknowledge(self, trip_id: str, *, role: str) -> dict | None:
        """Set loader_acknowledged or driver_acknowledged = True."""
        field = "loader_acknowledged" if role == "loader" else "driver_acknowledged"
        resp = (
            self._db.table(self.TABLE)
            .update({field: True})
            .eq("id", trip_id)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def update_stop_status(self, stop_id: str, status: str) -> dict | None:
        resp = (
            self._db.table(self.STOPS_TABLE)
            .update({"status": status})
            .eq("id", stop_id)
            .execute()
        )
        return resp.data[0] if resp.data else None
