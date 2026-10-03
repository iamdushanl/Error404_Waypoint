"""
Sync route — Phase 7 offline/online sync engine.

Role access:
  driver : POST /api/v1/sync           ← upload offline operation batch
  driver : GET  /api/v1/sync/status    ← view own sync history

Endpoints:
  POST /api/v1/sync
    Body  : SyncBatchRequest  (list of SyncOperation)
    200   : SyncBatchResponse (per-op results + summary counts)

    The endpoint always returns 200, even when some operations fail.
    Failure details live inside each SyncOperationResult.  This is intentional:
    the client must inspect individual results and decide what to retry.
    An HTTP 4xx/5xx would cause the client to retry the entire batch, which
    would re-submit already-applied operations — safe due to idempotency, but
    wasteful.

  GET /api/v1/sync/status
    200   : SyncStatusResponse  (driver's operation log, newest first)

Design note:
  All business logic lives in SyncService.  This layer is intentionally thin —
  it handles auth, injects the Supabase client, and returns the response.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, require_role
from app.db.session import get_supabase
from app.schemas.sync import SyncBatchRequest, SyncBatchResponse, SyncStatusResponse, SyncEventResponse
from app.services.sync_service import SyncService
from app.repositories.sync_repository import SyncRepository

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["sync"])


# ── POST /api/v1/sync — driver uploads offline operation batch ────────────────

@router.post(
    "/sync",
    response_model=SyncBatchResponse,
    status_code=200,
    summary="Upload offline operation batch",
    description=(
        "Driver submits all queued offline operations in a single call.\\n\\n"
        "Each operation is processed independently — partial success is valid.\\n\\n"
        "The response contains one result per submitted operation. "
        "The driver should dequeue operations with status **'applied'** or **'duplicate'** "
        "and retry only those with status **'failed'** (after investigating the error).\\n\\n"
        "**Idempotent**: submitting the same `operation_id` again returns 'duplicate' "
        "without re-applying. Safe to retry the entire batch on network failure.\\n\\n"
        "**Driver only.**"
    ),
)
async def sync_batch(
    body: SyncBatchRequest,
    current_user: dict[str, Any] = Depends(require_role("driver")),
) -> SyncBatchResponse:
    db = get_supabase()
    service = SyncService(db)

    driver_id: str = current_user["id"]

    log.info(
        "Sync batch received",
        extra={
            "driver_id": driver_id,
            "operation_count": len(body.operations),
        },
    )

    return service.process_batch(body, driver_id)


# ── GET /api/v1/sync/status — driver views own sync history ──────────────────

@router.get(
    "/sync/status",
    response_model=SyncStatusResponse,
    summary="Driver sync status / history",
    description=(
        "Returns the most recent sync operations submitted by the authenticated driver "
        "(newest first, up to 50 entries).\\n\\n"
        "Use this to verify which operations were applied, identify failures, "
        "and confirm the queue is empty before going offline again.\\n\\n"
        "**Driver only.**"
    ),
)
async def get_sync_status(
    current_user: dict[str, Any] = Depends(require_role("driver")),
) -> SyncStatusResponse:
    db = get_supabase()
    repo = SyncRepository(db)

    driver_id: str = current_user["id"]
    events_raw = repo.list_events_for_driver(driver_id)

    events = [SyncEventResponse(**e) for e in events_raw]
    return SyncStatusResponse(events=events, total=len(events))
