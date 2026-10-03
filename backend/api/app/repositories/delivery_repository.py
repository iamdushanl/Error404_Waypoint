"""
Delivery repository — read/write for the delivery execution tables.

Tables:
  deliveries              — driver records one row per stop outcome
  proof_of_delivery       — driver attaches photo + signature per delivery
  shortfalls              — loader records item issues before departure
  receipt_confirmations   — store manager confirms what arrived
"""
from __future__ import annotations

import datetime

from supabase import Client


class DeliveryRepository:
    DELIVERIES_TABLE = "deliveries"
    POD_TABLE = "proof_of_delivery"
    SHORTFALLS_TABLE = "shortfalls"
    RECEIPTS_TABLE = "receipt_confirmations"

    def __init__(self, client: Client) -> None:
        self._db = client

    # ── Deliveries ────────────────────────────────────────────────────────────

    def get_delivery(self, delivery_id: str) -> dict | None:
        resp = (
            self._db.table(self.DELIVERIES_TABLE)
            .select("*")
            .eq("id", delivery_id)
            .maybe_single()
            .execute()
        )
        return resp.data

    def get_delivery_by_stop(self, trip_stop_id: str) -> dict | None:
        """Return the delivery record for a stop, or None if not yet recorded."""
        resp = (
            self._db.table(self.DELIVERIES_TABLE)
            .select("*")
            .eq("trip_stop_id", trip_stop_id)
            .maybe_single()
            .execute()
        )
        return resp.data

    def get_delivery_by_operation_id(self, operation_id: str) -> dict | None:
        """Look up by the client's idempotency key."""
        resp = (
            self._db.table(self.DELIVERIES_TABLE)
            .select("*")
            .eq("offline_operation_id", operation_id)
            .maybe_single()
            .execute()
        )
        return resp.data

    def create_delivery(self, payload: dict) -> dict:
        resp = self._db.table(self.DELIVERIES_TABLE).insert(payload).execute()
        return resp.data[0]

    def list_deliveries_for_trip(self, trip_id: str) -> list[dict]:
        """All deliveries for stops within a given trip."""
        resp = (
            self._db.table(self.DELIVERIES_TABLE)
            .select("*, trip_stops!inner(trip_id, sequence_number, outlet_id)")
            .eq("trip_stops.trip_id", trip_id)
            .order("created_at")
            .execute()
        )
        return resp.data or []

    # ── Proof of Delivery ─────────────────────────────────────────────────────

    def get_pod(self, delivery_id: str) -> dict | None:
        resp = (
            self._db.table(self.POD_TABLE)
            .select("*")
            .eq("delivery_id", delivery_id)
            .maybe_single()
            .execute()
        )
        return resp.data

    def create_pod(self, payload: dict) -> dict:
        resp = self._db.table(self.POD_TABLE).insert(payload).execute()
        return resp.data[0]

    # ── Shortfalls ────────────────────────────────────────────────────────────

    def list_shortfalls_for_stop(self, trip_stop_id: str) -> list[dict]:
        resp = (
            self._db.table(self.SHORTFALLS_TABLE)
            .select("*")
            .eq("trip_stop_id", trip_stop_id)
            .order("created_at")
            .execute()
        )
        return resp.data or []

    def list_shortfalls_for_trip(self, trip_id: str) -> list[dict]:
        """All shortfalls across all stops in a trip."""
        resp = (
            self._db.table(self.SHORTFALLS_TABLE)
            .select("*, trip_stops!inner(trip_id)")
            .eq("trip_stops.trip_id", trip_id)
            .execute()
        )
        return resp.data or []

    def create_shortfall(self, payload: dict) -> dict:
        resp = self._db.table(self.SHORTFALLS_TABLE).insert(payload).execute()
        return resp.data[0]

    # ── Receipt Confirmations ─────────────────────────────────────────────────

    def get_receipt(self, delivery_id: str) -> dict | None:
        resp = (
            self._db.table(self.RECEIPTS_TABLE)
            .select("*")
            .eq("delivery_id", delivery_id)
            .maybe_single()
            .execute()
        )
        return resp.data

    def create_receipt(self, payload: dict) -> dict:
        resp = self._db.table(self.RECEIPTS_TABLE).insert(payload).execute()
        return resp.data[0]
