"""
Sync repository — Phase 7 offline sync engine.

Responsibilities:
  1. Write to sync_events (audit log of every offline operation received).
  2. Check whether an operation_id has already been processed (idempotency guard).
  3. Mark a sync_event row as applied / duplicate / failed after processing.
  4. Provide driver's sync history for GET /api/v1/sync/status.

This repository intentionally does NOT contain delivery business logic.
Entity creation (deliveries, POD, shortfalls) is delegated to the existing
DeliveryRepository so logic is never duplicated.
"""
from __future__ import annotations

import datetime
import logging

from supabase import Client

log = logging.getLogger(__name__)

SYNC_EVENTS_TABLE = "sync_events"


class SyncRepository:
    def __init__(self, client: Client) -> None:
        self._db = client

    # ─────────────────────────────────────────────────────────────────────────
    # Write: record incoming operation
    # ─────────────────────────────────────────────────────────────────────────

    def record_event(
        self,
        *,
        operation_id: str,
        device_id: str | None,
        driver_id: str,
        entity_type: str,
        operation: str,
        payload: dict,
    ) -> dict:
        """
        Insert a new sync_events row with status='pending'.

        entity_id is set to the operation_id at insert time (placeholder).
        It is updated once the entity has been created via mark_applied().
        """
        row = {
            "operation_id": operation_id,
            "device_id": device_id,
            "driver_id": driver_id,
            "entity_type": entity_type,
            # entity_id cannot be null (NOT NULL in schema) — use operation_id
            # as a placeholder until the real entity is created.
            "entity_id": operation_id,
            "operation": operation,
            "payload": payload,
            "status": "pending",
        }
        resp = self._db.table(SYNC_EVENTS_TABLE).insert(row).execute()
        return resp.data[0]

    # ─────────────────────────────────────────────────────────────────────────
    # Read: idempotency check
    # ─────────────────────────────────────────────────────────────────────────

    def get_by_operation_id(self, operation_id: str) -> dict | None:
        """
        Return the sync_events row for this operation_id, or None.
        Used to detect duplicates before attempting to apply the operation.
        """
        resp = (
            self._db.table(SYNC_EVENTS_TABLE)
            .select("*")
            .eq("operation_id", operation_id)
            .maybe_single()
            .execute()
        )
        return resp.data if resp else None

    # ─────────────────────────────────────────────────────────────────────────
    # Update: mark outcome
    # ─────────────────────────────────────────────────────────────────────────

    def mark_applied(self, operation_id: str, entity_id: str) -> None:
        """Set status='applied', record applied_at, and store the real entity_id."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self._db.table(SYNC_EVENTS_TABLE).update({
            "status": "applied",
            "entity_id": entity_id,
            "applied_at": now,
        }).eq("operation_id", operation_id).execute()

    def mark_duplicate(self, operation_id: str) -> None:
        """Set status='duplicate' — the operation_id was already applied."""
        self._db.table(SYNC_EVENTS_TABLE).update({
            "status": "duplicate",
        }).eq("operation_id", operation_id).execute()

    def mark_failed(self, operation_id: str, error_detail: str) -> None:
        """Set status='failed' and record the reason."""
        self._db.table(SYNC_EVENTS_TABLE).update({
            "status": "failed",
            "error_detail": error_detail,
        }).eq("operation_id", operation_id).execute()

    # ─────────────────────────────────────────────────────────────────────────
    # Read: driver history
    # ─────────────────────────────────────────────────────────────────────────

    def list_events_for_driver(
        self,
        driver_id: str,
        limit: int = 50,
    ) -> list[dict]:
        """
        Return the most recent sync events for a driver (newest first).
        Used by GET /api/v1/sync/status.
        """
        resp = (
            self._db.table(SYNC_EVENTS_TABLE)
            .select("*")
            .eq("driver_id", driver_id)
            .order("received_at", desc=True)
            .limit(limit)
            .execute()
        )
        return resp.data or []
