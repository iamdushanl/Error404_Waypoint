"""
Order repository — CRUD for orders and order items.

Access patterns:
  - Store manager: read/write own outlet's orders
  - Dispatcher: read all orders, update status
  - Driver: read allocated orders on their trips
"""
from __future__ import annotations

import datetime

from supabase import Client


class OrderRepository:
    TABLE = "orders"
    ITEMS_TABLE = "order_items"

    def __init__(self, client: Client) -> None:
        self._db = client

    # ── Queries ───────────────────────────────────────────────────────────────

    def list(
        self,
        *,
        outlet_id: str | None = None,
        brand: str | None = None,
        status: str | None = None,
        requested_date: datetime.date | None = None,
        depot: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Return (rows, total_count) with optional filters."""
        q = self._db.table(self.TABLE).select("*", count="exact")

        if outlet_id:
            q = q.eq("outlet_id", outlet_id)
        if brand:
            q = q.eq("brand", brand)
        if status:
            q = q.eq("status", status)
        if requested_date:
            q = q.eq("requested_date", str(requested_date))
        if depot:
            # Join-style filter: orders where outlet.depot = depot
            # Supabase supports embedded filters via FK relationships
            q = q.eq("outlets.depot", depot)

        q = q.order("created_at", desc=True).range(offset, offset + limit - 1)
        resp = q.execute()
        return resp.data or [], resp.count or 0

    def get(self, order_id: str) -> dict | None:
        resp = (
            self._db.table(self.TABLE)
            .select("*")
            .eq("id", order_id)
            .maybe_single()
            .execute()
        )
        return resp.data if resp else None

    def get_with_items(self, order_id: str) -> dict | None:
        """Return order + its line items in one query."""
        resp = (
            self._db.table(self.TABLE)
            .select("*, order_items(*)")
            .eq("id", order_id)
            .maybe_single()
            .execute()
        )
        if resp and resp.data:
            # Normalise the nested key
            data = resp.data.copy()
            data["items"] = data.pop("order_items", [])
            return data
        return None

    def list_for_outlet(
        self, outlet_id: str, *, status: str | None = None,
        limit: int = 100, offset: int = 0
    ) -> tuple[list[dict], int]:
        """All orders for a specific outlet (store manager view)."""
        q = (
            self._db.table(self.TABLE)
            .select("*", count="exact")
            .eq("outlet_id", outlet_id)
        )
        if status:
            q = q.eq("status", status)
        q = q.order("requested_date", desc=True).range(offset, offset + limit - 1)
        resp = q.execute()
        return resp.data or [], resp.count or 0

    def list_for_date_depot(
        self, requested_date: datetime.date, depot: str,
        *, status: str = "submitted"
    ) -> list[dict]:
        """All submitted orders for a planning date + depot (dispatcher view)."""
        resp = (
            self._db.table(self.TABLE)
            .select("*, outlets!inner(depot, district, dock_type, parking_constraint, window_open_time, window_close_time, mall_window)")
            .eq("requested_date", str(requested_date))
            .eq("status", status)
            .eq("outlets.depot", depot)
            .execute()
        )
        return resp.data or []

    # ── Mutations ─────────────────────────────────────────────────────────────

    def create(self, payload: dict) -> dict:
        """Insert a new order and return the created row."""
        resp = self._db.table(self.TABLE).insert(payload).execute()
        return resp.data[0]

    def create_items(self, items: list[dict]) -> list[dict]:
        """Bulk insert order items."""
        resp = self._db.table(self.ITEMS_TABLE).insert(items).execute()
        return resp.data or []

    def update_status(
        self,
        order_id: str,
        status: str,
        *,
        extra: dict | None = None,
    ) -> dict | None:
        """Update an order's status (and optional extra fields)."""
        payload: dict = {"status": status}
        if extra:
            payload.update(extra)
        resp = (
            self._db.table(self.TABLE)
            .update(payload)
            .eq("id", order_id)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def submit(self, order_id: str) -> dict | None:
        """Mark order as submitted with current timestamp."""
        import datetime as dt
        return self.update_status(
            order_id,
            "submitted",
            extra={"submitted_at": dt.datetime.utcnow().isoformat()},
        )

    def get_items(self, order_id: str) -> list[dict]:
        resp = (
            self._db.table(self.ITEMS_TABLE)
            .select("*")
            .eq("order_id", order_id)
            .execute()
        )
        return resp.data or []
