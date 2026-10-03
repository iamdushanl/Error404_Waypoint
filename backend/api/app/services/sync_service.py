"""
Sync service — Phase 7 offline/online sync engine.

Orchestration layer between the sync route and the repositories.

Responsibilities:
  - Per-operation processing pipeline:
      1. Check idempotency (operation_id already in sync_events?).
      2. Insert sync_events row with status='pending' (audit-first).
      3. Validate payload and dispatch to the correct handler.
      4. Delegate entity creation to DeliveryRepository (no duplicated logic).
      5. Update sync_events row to applied / duplicate / failed.
  - Build the SyncBatchResponse summary counts.

Idempotency contract:
  - An operation_id that already exists in sync_events is a duplicate.
  - We return the existing entity_id from sync_events and mark it 'duplicate'
    in our response — no second insert is attempted.
  - This handles the "driver re-syncs after partial failure" case safely.

Business rule delegation:
  - Trip status checks, stop ownership, order status updates — all of this
    lives in the delivery route handlers (and in the direct Supabase calls they
    make).  The sync service calls the same DeliveryRepository methods, so
    rules are never duplicated.
"""
from __future__ import annotations

import datetime
import logging
from typing import Any

from supabase import Client

from app.repositories.delivery_repository import DeliveryRepository
from app.repositories.sync_repository import SyncRepository
from app.schemas.sync import (
    SyncBatchRequest,
    SyncBatchResponse,
    SyncOperation,
    SyncOperationResult,
)

log = logging.getLogger(__name__)

# ── entity_type values (must match sync_events.entity_type CHECK constraint) ──
ENTITY_TYPE_MAP: dict[str, str] = {
    "complete_delivery": "delivery",
    "record_pod": "proof_of_delivery",
    "record_shortfall": "shortfall",
}


class SyncService:
    def __init__(self, db: Client) -> None:
        self._db = db
        self._sync_repo = SyncRepository(db)
        self._delivery_repo = DeliveryRepository(db)

    # ─────────────────────────────────────────────────────────────────────────
    # Public: process a batch
    # ─────────────────────────────────────────────────────────────────────────

    def process_batch(
        self,
        batch: SyncBatchRequest,
        driver_id: str,
    ) -> SyncBatchResponse:
        """
        Process all operations in the batch sequentially.

        Each operation is independent — a failure on one does not stop the rest.
        Returns a SyncBatchResponse with one result per submitted operation.
        """
        results: list[SyncOperationResult] = []

        for op in batch.operations:
            result = self._process_single(op, driver_id)
            results.append(result)

        applied = sum(1 for r in results if r.status == "applied")
        dupes = sum(1 for r in results if r.status == "duplicate")
        failed = sum(1 for r in results if r.status == "failed")

        log.info(
            "Sync batch processed",
            extra={
                "driver_id": driver_id,
                "total": len(results),
                "applied": applied,
                "duplicate": dupes,
                "failed": failed,
            },
        )

        return SyncBatchResponse(
            results=results,
            applied_count=applied,
            duplicate_count=dupes,
            failed_count=failed,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Private: single-operation pipeline
    # ─────────────────────────────────────────────────────────────────────────

    def _process_single(
        self,
        op: SyncOperation,
        driver_id: str,
    ) -> SyncOperationResult:
        entity_type = ENTITY_TYPE_MAP.get(op.operation, "delivery")

        # ── Step 1: idempotency check ─────────────────────────────────────────
        existing_event = self._sync_repo.get_by_operation_id(op.operation_id)
        if existing_event:
            # Already processed (or currently pending from a previous crash).
            # If it was applied before, return the entity_id from the audit row.
            existing_status = existing_event.get("status", "duplicate")
            entity_id = existing_event.get("entity_id") or op.operation_id

            if existing_status == "applied":
                log.info(
                    "Duplicate sync operation — already applied",
                    extra={"operation_id": op.operation_id},
                )
                return SyncOperationResult(
                    operation_id=op.operation_id,
                    status="duplicate",
                    entity_id=entity_id,
                )
            elif existing_status == "pending":
                # Edge case: row exists but was never resolved (e.g. server
                # crashed mid-apply).  Re-attempt below by falling through,
                # but we won't insert a new row.
                pass
            else:
                # Was previously marked duplicate or failed; treat as duplicate
                # to avoid retry loops on permanently broken payloads.
                return SyncOperationResult(
                    operation_id=op.operation_id,
                    status="duplicate",
                    entity_id=entity_id,
                    error_detail=(
                        existing_event.get("error_detail")
                        if existing_status == "failed"
                        else None
                    ),
                )

        # ── Step 2: audit-first insert (only if not already in sync_events) ──
        if not existing_event:
            try:
                self._sync_repo.record_event(
                    operation_id=op.operation_id,
                    device_id=op.device_id,
                    driver_id=driver_id,
                    entity_type=entity_type,
                    operation=op.operation,
                    payload=op.payload,
                )
            except Exception as exc:
                # If the insert itself fails (e.g. UNIQUE violation on a race),
                # treat as duplicate — the other process will handle it.
                log.warning(
                    "sync_events insert failed (race condition?) — treating as duplicate",
                    extra={"operation_id": op.operation_id, "error": str(exc)},
                )
                return SyncOperationResult(
                    operation_id=op.operation_id,
                    status="duplicate",
                )

        # ── Step 3: dispatch to operation handler ─────────────────────────────
        try:
            entity_id = self._dispatch(op, driver_id)
        except _SyncValidationError as exc:
            self._sync_repo.mark_failed(op.operation_id, str(exc))
            log.warning(
                "Sync operation failed validation",
                extra={"operation_id": op.operation_id, "reason": str(exc)},
            )
            return SyncOperationResult(
                operation_id=op.operation_id,
                status="failed",
                error_detail=str(exc),
            )
        except Exception as exc:
            detail = f"Unexpected error: {exc}"
            self._sync_repo.mark_failed(op.operation_id, detail)
            log.error(
                "Sync operation raised unexpected exception",
                extra={"operation_id": op.operation_id, "error": str(exc)},
                exc_info=True,
            )
            return SyncOperationResult(
                operation_id=op.operation_id,
                status="failed",
                error_detail=detail,
            )

        # ── Step 4: mark applied ──────────────────────────────────────────────
        self._sync_repo.mark_applied(op.operation_id, entity_id)

        return SyncOperationResult(
            operation_id=op.operation_id,
            status="applied",
            entity_id=entity_id,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Dispatch table
    # ─────────────────────────────────────────────────────────────────────────

    def _dispatch(self, op: SyncOperation, driver_id: str) -> str:
        """Route to the correct handler.  Returns the created entity's UUID."""
        if op.operation == "complete_delivery":
            return self._apply_complete_delivery(op, driver_id)
        elif op.operation == "record_pod":
            return self._apply_record_pod(op, driver_id)
        elif op.operation == "record_shortfall":
            return self._apply_record_shortfall(op, driver_id)
        else:
            raise _SyncValidationError(f"Unknown operation: {op.operation!r}")

    # ─────────────────────────────────────────────────────────────────────────
    # Handlers — one per supported operation_name
    # ─────────────────────────────────────────────────────────────────────────

    def _apply_complete_delivery(
        self,
        op: SyncOperation,
        driver_id: str,
    ) -> str:
        """
        Apply a complete_delivery operation.

        Idempotency (second layer):
          - Check deliveries.offline_operation_id column.
          - If found, return the existing delivery UUID — not a failure.
        Business rules:
          - Trip must have departed.
          - Stop must not already have a delivery record (unless it's ours via
            offline_operation_id — handled above).
        """
        p = op.payload
        trip_stop_id = _require_str(p, "trip_stop_id", op.operation_id)
        outcome = _require_str(p, "outcome", op.operation_id)

        if outcome not in ("delivered", "attempted", "refused"):
            raise _SyncValidationError(
                f"[{op.operation_id}] Invalid outcome '{outcome}'. "
                "Must be 'delivered', 'attempted', or 'refused'."
            )

        # Idempotency: check deliveries table via offline_operation_id
        existing_delivery = self._delivery_repo.get_delivery_by_operation_id(
            op.operation_id
        )
        if existing_delivery:
            log.info(
                "Delivery already exists for operation_id — returning existing",
                extra={"operation_id": op.operation_id},
            )
            return existing_delivery["id"]

        # Conflict check: stop already completed by a different operation
        existing_for_stop = self._delivery_repo.get_delivery_by_stop(trip_stop_id)
        if existing_for_stop:
            raise _SyncValidationError(
                f"[{op.operation_id}] Stop '{trip_stop_id}' already has a delivery "
                f"(outcome: '{existing_for_stop['outcome']}'). "
                "A stop can only be completed once."
            )

        # Verify the stop exists and its trip has departed
        stop_resp = (
            self._db.table("trip_stops")
            .select("id, trip_id, order_id, status, trips!inner(status)")
            .eq("id", trip_stop_id)
            .maybe_single()
            .execute()
        )
        if not stop_resp.data:
            raise _SyncValidationError(
                f"[{op.operation_id}] Trip stop '{trip_stop_id}' not found."
            )

        stop = stop_resp.data
        trip = stop.get("trips", {})
        if trip.get("status") not in ("departed", "in_transit"):
            raise _SyncValidationError(
                f"[{op.operation_id}] Trip is in status '{trip.get('status')}'. "
                "Deliveries can only be recorded after the trip has departed."
            )

        # Parse optional delivered_at (driver device time)
        delivered_at_raw = p.get("delivered_at")
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if delivered_at_raw:
            try:
                dt = datetime.datetime.fromisoformat(str(delivered_at_raw))
                delivered_at_iso = dt.isoformat()
            except ValueError:
                delivered_at_iso = now_iso
        else:
            delivered_at_iso = now_iso

        # Build payload for delivery_repository.create_delivery()
        delivery_payload = {
            "trip_stop_id": trip_stop_id,
            "driver_id": driver_id,
            "outcome": outcome,
            "recipient_name": p.get("recipient_name"),
            "notes": p.get("notes"),
            "delivered_at": delivered_at_iso,
            "offline_operation_id": op.operation_id,
            "synced_at": now_iso,
        }

        delivery = self._delivery_repo.create_delivery(delivery_payload)
        delivery_id = delivery["id"]

        # Mirror side effects from the online delivery route
        status_map = {
            "delivered": "delivered",
            "attempted": "attempted",
            "refused": "refused",
        }
        self._db.table("trip_stops").update({
            "status": status_map[outcome],
            "actual_arrival_time": delivered_at_iso,
        }).eq("id", trip_stop_id).execute()

        order_id = stop.get("order_id")
        if order_id:
            order_status = "delivered" if outcome == "delivered" else "attempted"
            self._db.table("orders").update(
                {"status": order_status}
            ).eq("id", order_id).execute()

        if trip.get("status") == "departed":
            self._db.table("trips").update(
                {"status": "in_transit"}
            ).eq("id", stop["trip_id"]).execute()

        return delivery_id

    def _apply_record_pod(
        self,
        op: SyncOperation,
        driver_id: str,
    ) -> str:
        """Apply a record_pod operation."""
        p = op.payload
        delivery_id = _require_str(p, "delivery_id", op.operation_id)
        recipient_name = _require_str(p, "recipient_name", op.operation_id)
        recorded_at_raw = _require_str(p, "recorded_at", op.operation_id)

        # Validate the delivery exists and is 'delivered'
        delivery = self._delivery_repo.get_delivery(delivery_id)
        if not delivery:
            raise _SyncValidationError(
                f"[{op.operation_id}] Delivery '{delivery_id}' not found."
            )
        if delivery["outcome"] != "delivered":
            raise _SyncValidationError(
                f"[{op.operation_id}] POD can only be added to a 'delivered' stop. "
                f"Outcome is '{delivery['outcome']}'."
            )

        # Idempotency: check if POD already exists for this delivery
        existing_pod = self._delivery_repo.get_pod(delivery_id)
        if existing_pod:
            return existing_pod["id"]

        try:
            recorded_at_dt = datetime.datetime.fromisoformat(recorded_at_raw)
        except ValueError:
            recorded_at_dt = datetime.datetime.now(datetime.timezone.utc)

        pod_payload = {
            "delivery_id": delivery_id,
            "recipient_name": recipient_name,
            "photo_url": p.get("photo_url"),
            "recipient_signature_url": p.get("recipient_signature_url"),
            "recorded_at": recorded_at_dt.isoformat(),
        }

        pod = self._delivery_repo.create_pod(pod_payload)
        return pod["id"]

    def _apply_record_shortfall(
        self,
        op: SyncOperation,
        driver_id: str,
    ) -> str:
        """Apply a record_shortfall operation."""
        p = op.payload
        trip_stop_id = _require_str(p, "trip_stop_id", op.operation_id)
        issue_type = _require_str(p, "issue_type", op.operation_id)
        sku = _require_str(p, "sku", op.operation_id)
        description = _require_str(p, "description", op.operation_id)

        if issue_type not in ("missing", "damaged", "wrong_item"):
            raise _SyncValidationError(
                f"[{op.operation_id}] Invalid issue_type '{issue_type}'."
            )

        expected_qty = _require_int(p, "expected_quantity", op.operation_id)
        actual_qty = _require_int(p, "actual_quantity", op.operation_id)

        if actual_qty >= expected_qty:
            raise _SyncValidationError(
                f"[{op.operation_id}] actual_quantity ({actual_qty}) must be less "
                f"than expected_quantity ({expected_qty})."
            )

        shortfall_payload = {
            "trip_stop_id": trip_stop_id,
            "issue_type": issue_type,
            "sku": sku,
            "description": description,
            "expected_quantity": expected_qty,
            "actual_quantity": actual_qty,
            "photo_url": p.get("photo_url"),
            "notes": p.get("notes"),
            "recorded_by": driver_id,
        }

        shortfall = self._delivery_repo.create_shortfall(shortfall_payload)

        # Update stop status to reflect the shortfall
        self._db.table("trip_stops").update(
            {"status": "shortfall"}
        ).eq("id", trip_stop_id).execute()

        return shortfall["id"]


# ── Helpers ───────────────────────────────────────────────────────────────────

class _SyncValidationError(Exception):
    """Raised for payload validation failures within the sync service."""


def _require_str(payload: dict[str, Any], key: str, operation_id: str) -> str:
    val = payload.get(key)
    if not val or not isinstance(val, str):
        raise _SyncValidationError(
            f"[{operation_id}] Missing or invalid required field: '{key}'."
        )
    return val


def _require_int(payload: dict[str, Any], key: str, operation_id: str) -> int:
    val = payload.get(key)
    if val is None:
        raise _SyncValidationError(
            f"[{operation_id}] Missing required integer field: '{key}'."
        )
    try:
        return int(val)
    except (TypeError, ValueError):
        raise _SyncValidationError(
            f"[{operation_id}] Field '{key}' must be an integer, got {val!r}."
        )
