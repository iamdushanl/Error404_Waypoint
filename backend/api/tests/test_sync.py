"""
Phase 7 Offline Sync Engine tests.

Covers:
  - POST /api/v1/sync  — batch upload of offline operations
  - GET  /api/v1/sync/status — driver audit log
  - Idempotency: duplicate operation_id returns 'duplicate' not error
  - Payload validation: missing required fields returns 'failed'
  - Role-based authorization (driver only)
  - Multi-operation batch: partial success handled correctly
  - complete_delivery, record_pod, record_shortfall handlers
"""
from __future__ import annotations

import datetime
import uuid
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app):
    return TestClient(app)


# ── Mock users ────────────────────────────────────────────────────────────────

DRIVER_USER = {
    "id": "driver-uuid-sync-1",
    "email": "driver@waypoint.demo",
    "full_name": "Driver Silva",
    "role": "driver",
    "outlet_id": None,
    "depot": "Peliyagoda",
    "vehicle_id": "veh-101",
}

DISPATCHER_USER = {
    "id": "disp-uuid-1",
    "email": "dispatcher@waypoint.demo",
    "full_name": "Dispatcher",
    "role": "dispatcher",
    "outlet_id": None,
    "depot": "Peliyagoda",
    "vehicle_id": None,
}

LOADER_USER = {
    "id": "loader-uuid-1",
    "email": "loader@waypoint.demo",
    "full_name": "Loader Fernando",
    "role": "loader",
    "outlet_id": None,
    "depot": "Peliyagoda",
    "vehicle_id": None,
}


# ── DB mock helpers ───────────────────────────────────────────────────────────

def _mock_query(data: Any = None):
    """Return a chainable Supabase query mock."""
    mock = MagicMock()
    mock.execute.return_value.data = data
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.in_.return_value = mock
    mock.order.return_value = mock
    mock.limit.return_value = mock
    mock.maybe_single.return_value = mock
    mock.single.return_value = mock
    mock.insert.return_value = mock
    mock.update.return_value = mock
    return mock


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _make_sync_event(operation_id: str, status: str = "applied", entity_id: str = "ent-1") -> dict:
    return {
        "id": str(uuid.uuid4()),
        "operation_id": operation_id,
        "device_id": "dev-1",
        "driver_id": DRIVER_USER["id"],
        "entity_type": "delivery",
        "entity_id": entity_id,
        "operation": "complete_delivery",
        "payload": {},
        "status": status,
        "error_detail": None,
        "received_at": _now_iso(),
        "applied_at": _now_iso() if status == "applied" else None,
    }


# ═════════════════════════════════════════════════════════════════════════════
# Role / Auth Tests
# ═════════════════════════════════════════════════════════════════════════════

class TestSyncAuth:
    """Verify only drivers can use the sync endpoints."""

    def test_unauthenticated_sync_returns_401(self, client: TestClient):
        resp = client.post("/api/v1/sync", json={"operations": []})
        assert resp.status_code == 401

    def test_unauthenticated_status_returns_401(self, client: TestClient):
        resp = client.get("/api/v1/sync/status")
        assert resp.status_code == 401

    def test_dispatcher_cannot_sync(self, app, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: DISPATCHER_USER
        try:
            resp = client.post(
                "/api/v1/sync",
                json={
                    "operations": [
                        {
                            "operation_id": "op-1",
                            "operation": "complete_delivery",
                            "payload": {},
                        }
                    ]
                },
            )
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.clear()

    def test_loader_cannot_sync(self, app, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: LOADER_USER
        try:
            resp = client.post(
                "/api/v1/sync",
                json={"operations": [{"operation_id": "op-1", "operation": "complete_delivery", "payload": {}}]},
            )
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.clear()

    def test_dispatcher_cannot_view_sync_status(self, app, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: DISPATCHER_USER
        try:
            resp = client.get("/api/v1/sync/status")
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.clear()


# ═════════════════════════════════════════════════════════════════════════════
# Schema Validation
# ═════════════════════════════════════════════════════════════════════════════

class TestSyncSchemaValidation:
    """Verify FastAPI/Pydantic rejects malformed batch requests."""

    def test_empty_operations_list_rejected(self, app, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: DRIVER_USER
        try:
            resp = client.post("/api/v1/sync", json={"operations": []})
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.clear()

    def test_missing_operation_id_rejected(self, app, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: DRIVER_USER
        try:
            resp = client.post(
                "/api/v1/sync",
                json={
                    "operations": [
                        {"operation": "complete_delivery", "payload": {}}
                        # missing operation_id
                    ]
                },
            )
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.clear()

    def test_invalid_operation_type_rejected(self, app, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: DRIVER_USER
        try:
            resp = client.post(
                "/api/v1/sync",
                json={
                    "operations": [
                        {
                            "operation_id": "op-1",
                            "operation": "delete_everything",  # not a valid operation
                            "payload": {},
                        }
                    ]
                },
            )
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.clear()


# ═════════════════════════════════════════════════════════════════════════════
# complete_delivery operation
# ═════════════════════════════════════════════════════════════════════════════

class TestCompleteDeliverySync:
    """Tests for the complete_delivery operation via /api/v1/sync."""

    def test_successful_complete_delivery(self, app, client: TestClient):
        """A valid complete_delivery operation should create a delivery row."""
        operation_id = str(uuid.uuid4())
        stop_id = "stop-uuid-1"
        delivery_id = "delivery-uuid-1"

        mock_db = MagicMock()

        # sync_events: operation_id not seen before
        sync_check = _mock_query(data=None)
        # sync_events insert (record_event)
        sync_insert = _mock_query(data=[{
            "id": "evt-1", "operation_id": operation_id,
            "device_id": None, "driver_id": DRIVER_USER["id"],
            "entity_type": "delivery", "entity_id": operation_id,
            "operation": "complete_delivery", "payload": {},
            "status": "pending", "error_detail": None,
            "received_at": _now_iso(), "applied_at": None,
        }])
        # deliveries: offline_operation_id not found
        delivery_check_op = _mock_query(data=None)
        # deliveries: stop not completed yet
        delivery_check_stop = _mock_query(data=None)
        # trip_stops: stop exists with a departed trip
        stop_data = {
            "id": stop_id,
            "trip_id": "trip-1",
            "order_id": "order-1",
            "status": "planned",
            "trips": {"status": "departed"},
        }
        stop_lookup = _mock_query(data=stop_data)
        # delivery insert
        delivery_created = _mock_query(data=[{
            "id": delivery_id,
            "trip_stop_id": stop_id,
            "driver_id": DRIVER_USER["id"],
            "outcome": "delivered",
            "recipient_name": "John",
            "notes": None,
            "delivered_at": _now_iso(),
            "offline_operation_id": operation_id,
            "synced_at": _now_iso(),
            "created_at": _now_iso(),
        }])
        # trip_stops update, orders update, trips update, sync_events mark_applied
        update_mock = _mock_query(data=[{}])

        call_count = [0]

        def table_side_effect(table_name: str):
            call_count[0] += 1
            n = call_count[0]
            if table_name == "sync_events" and n == 1:
                return sync_check
            elif table_name == "sync_events" and n == 2:
                return sync_insert
            elif table_name == "deliveries" and n == 3:
                return delivery_check_op
            elif table_name == "deliveries" and n == 4:
                return delivery_check_stop
            elif table_name == "trip_stops" and n == 5:
                return stop_lookup
            elif table_name == "deliveries" and n == 6:
                return delivery_created
            else:
                return update_mock

        mock_db.table.side_effect = table_side_effect

        with patch("app.api.routes.sync.get_supabase", return_value=mock_db):
            app.dependency_overrides[get_current_user] = lambda: DRIVER_USER
            try:
                resp = client.post(
                    "/api/v1/sync",
                    json={
                        "operations": [
                            {
                                "operation_id": operation_id,
                                "operation": "complete_delivery",
                                "device_id": "dev-android-1",
                                "payload": {
                                    "trip_stop_id": stop_id,
                                    "outcome": "delivered",
                                    "recipient_name": "John",
                                    "delivered_at": _now_iso(),
                                },
                            }
                        ]
                    },
                )
            finally:
                app.dependency_overrides.clear()

        assert resp.status_code == 200
        body = resp.json()
        assert body["applied_count"] == 1
        assert body["duplicate_count"] == 0
        assert body["failed_count"] == 0
        assert len(body["results"]) == 1
        result = body["results"][0]
        assert result["operation_id"] == operation_id
        assert result["status"] == "applied"
        assert result["entity_id"] == delivery_id

    def test_duplicate_operation_id_returns_duplicate(self, app, client: TestClient):
        """
        If the operation_id was already processed (status='applied' in sync_events),
        the batch result should be 'duplicate', not an error.
        """
        operation_id = str(uuid.uuid4())
        existing_entity_id = "existing-delivery-uuid"

        mock_db = MagicMock()
        existing_event = _make_sync_event(operation_id, "applied", existing_entity_id)
        sync_check = _mock_query(data=existing_event)
        mock_db.table.return_value = sync_check

        with patch("app.api.routes.sync.get_supabase", return_value=mock_db):
            app.dependency_overrides[get_current_user] = lambda: DRIVER_USER
            try:
                resp = client.post(
                    "/api/v1/sync",
                    json={
                        "operations": [
                            {
                                "operation_id": operation_id,
                                "operation": "complete_delivery",
                                "payload": {
                                    "trip_stop_id": "stop-1",
                                    "outcome": "delivered",
                                },
                            }
                        ]
                    },
                )
            finally:
                app.dependency_overrides.clear()

        assert resp.status_code == 200
        body = resp.json()
        assert body["duplicate_count"] == 1
        assert body["applied_count"] == 0
        assert body["failed_count"] == 0
        result = body["results"][0]
        assert result["status"] == "duplicate"
        assert result["entity_id"] == existing_entity_id

    def test_invalid_outcome_returns_failed(self, app, client: TestClient):
        """An invalid outcome value should produce status='failed' in the result."""
        operation_id = str(uuid.uuid4())

        mock_db = MagicMock()
        # sync_events: not seen
        sync_check = _mock_query(data=None)
        # sync_events insert
        sync_insert = _mock_query(data=[{
            "id": "evt-x", "operation_id": operation_id,
            "device_id": None, "driver_id": DRIVER_USER["id"],
            "entity_type": "delivery", "entity_id": operation_id,
            "operation": "complete_delivery", "payload": {},
            "status": "pending", "error_detail": None,
            "received_at": _now_iso(), "applied_at": None,
        }])
        # deliveries check (not found)
        del_check = _mock_query(data=None)
        # stop check (not found) — won't reach this
        update_mock = _mock_query(data=[{}])

        call_count = [0]

        def table_side_effect(name: str):
            call_count[0] += 1
            n = call_count[0]
            if name == "sync_events" and n == 1:
                return sync_check
            elif name == "sync_events" and n == 2:
                return sync_insert
            elif name == "deliveries" and n == 3:
                return del_check
            else:
                return update_mock

        mock_db.table.side_effect = table_side_effect

        with patch("app.api.routes.sync.get_supabase", return_value=mock_db):
            app.dependency_overrides[get_current_user] = lambda: DRIVER_USER
            try:
                resp = client.post(
                    "/api/v1/sync",
                    json={
                        "operations": [
                            {
                                "operation_id": operation_id,
                                "operation": "complete_delivery",
                                "payload": {
                                    "trip_stop_id": "stop-1",
                                    "outcome": "INVALID_OUTCOME",
                                },
                            }
                        ]
                    },
                )
            finally:
                app.dependency_overrides.clear()

        assert resp.status_code == 200
        body = resp.json()
        assert body["failed_count"] == 1
        assert body["applied_count"] == 0
        result = body["results"][0]
        assert result["status"] == "failed"
        assert result["error_detail"] is not None

    def test_missing_trip_stop_id_returns_failed(self, app, client: TestClient):
        """Missing required trip_stop_id in payload should produce status='failed'."""
        operation_id = str(uuid.uuid4())

        mock_db = MagicMock()
        sync_check = _mock_query(data=None)
        sync_insert = _mock_query(data=[{
            "id": "evt-2", "operation_id": operation_id,
            "device_id": None, "driver_id": DRIVER_USER["id"],
            "entity_type": "delivery", "entity_id": operation_id,
            "operation": "complete_delivery", "payload": {},
            "status": "pending", "error_detail": None,
            "received_at": _now_iso(), "applied_at": None,
        }])
        update_mock = _mock_query(data=[{}])

        call_count = [0]

        def table_side_effect(name: str):
            call_count[0] += 1
            n = call_count[0]
            if name == "sync_events" and n == 1:
                return sync_check
            elif name == "sync_events" and n == 2:
                return sync_insert
            else:
                return update_mock

        mock_db.table.side_effect = table_side_effect

        with patch("app.api.routes.sync.get_supabase", return_value=mock_db):
            app.dependency_overrides[get_current_user] = lambda: DRIVER_USER
            try:
                resp = client.post(
                    "/api/v1/sync",
                    json={
                        "operations": [
                            {
                                "operation_id": operation_id,
                                "operation": "complete_delivery",
                                "payload": {
                                    # trip_stop_id is missing
                                    "outcome": "delivered",
                                },
                            }
                        ]
                    },
                )
            finally:
                app.dependency_overrides.clear()

        assert resp.status_code == 200
        body = resp.json()
        assert body["failed_count"] == 1
        result = body["results"][0]
        assert result["status"] == "failed"
        assert "trip_stop_id" in result["error_detail"]


# ═════════════════════════════════════════════════════════════════════════════
# Multi-operation batch
# ═════════════════════════════════════════════════════════════════════════════

class TestMultiOperationBatch:
    """Verify that one failure does not block other operations in the batch."""

    def test_partial_success_batch(self, app, client: TestClient):
        """
        Batch of 3:
          op1 = duplicate (already in sync_events as applied)
          op2 = failed   (missing required field trip_stop_id)
          op3 = failed   (stop not found in DB)

        All three get a result; the batch never raises.
        """
        op1_id = str(uuid.uuid4())
        op2_id = str(uuid.uuid4())
        op3_id = str(uuid.uuid4())

        mock_db = MagicMock()
        existing_for_op1 = _make_sync_event(op1_id, "applied", "existing-entity")

        # Track calls PER TABLE to avoid sync_events counter being skewed by
        # deliveries/trip_stops calls happening mid-sequence.
        calls_by_table: dict[str, int] = {}

        def _build_insert_row(operation_id: str, op_name: str = "complete_delivery") -> list:
            return [{
                "id": str(uuid.uuid4()),
                "operation_id": operation_id,
                "device_id": None,
                "driver_id": DRIVER_USER["id"],
                "entity_type": "delivery",
                "entity_id": operation_id,
                "operation": op_name,
                "payload": {},
                "status": "pending",
                "error_detail": None,
                "received_at": _now_iso(),
                "applied_at": None,
            }]

        def table_side_effect(name: str):
            calls_by_table[name] = calls_by_table.get(name, 0) + 1
            call_n = calls_by_table[name]

            if name == "sync_events":
                if call_n == 1:
                    # op1 idempotency check -> already applied
                    return _mock_query(data=existing_for_op1)
                elif call_n == 2:
                    # op2 idempotency check -> not found
                    return _mock_query(data=None)
                elif call_n == 3:
                    # op2 sync_events insert -> success
                    return _mock_query(data=_build_insert_row(op2_id))
                elif call_n == 4:
                    # op2 mark_failed
                    return _mock_query(data=[{}])
                elif call_n == 5:
                    # op3 idempotency check -> not found
                    return _mock_query(data=None)
                elif call_n == 6:
                    # op3 sync_events insert -> success
                    return _mock_query(data=_build_insert_row(op3_id))
                else:
                    # op3 mark_failed
                    return _mock_query(data=[{}])
            elif name == "deliveries":
                # All delivery idempotency checks -> not found
                return _mock_query(data=None)
            elif name == "trip_stops":
                # op3 stop lookup -> not found
                return _mock_query(data=None)
            else:
                return _mock_query(data=[{}])

        mock_db.table.side_effect = table_side_effect

        with patch("app.api.routes.sync.get_supabase", return_value=mock_db):
            app.dependency_overrides[get_current_user] = lambda: DRIVER_USER
            try:
                resp = client.post(
                    "/api/v1/sync",
                    json={
                        "operations": [
                            # op1: duplicate (already applied in sync_events)
                            {
                                "operation_id": op1_id,
                                "operation": "complete_delivery",
                                "payload": {"trip_stop_id": "s-1", "outcome": "delivered"},
                            },
                            # op2: missing trip_stop_id → failed validation
                            {
                                "operation_id": op2_id,
                                "operation": "complete_delivery",
                                "payload": {"outcome": "delivered"},
                            },
                            # op3: stop not found → failed
                            {
                                "operation_id": op3_id,
                                "operation": "complete_delivery",
                                "payload": {"trip_stop_id": "s-999", "outcome": "attempted"},
                            },
                        ]
                    },
                )
            finally:
                app.dependency_overrides.clear()

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["results"]) == 3

        results_by_id = {r["operation_id"]: r for r in body["results"]}
        assert results_by_id[op1_id]["status"] == "duplicate"
        assert results_by_id[op2_id]["status"] == "failed"
        assert results_by_id[op3_id]["status"] == "failed"



# ═════════════════════════════════════════════════════════════════════════════
# GET /api/v1/sync/status
# ═════════════════════════════════════════════════════════════════════════════

class TestSyncStatus:
    """Tests for the driver sync-status endpoint."""

    def test_returns_driver_events(self, app, client: TestClient):
        """Driver can view their own sync history."""
        op_id = str(uuid.uuid4())
        events = [_make_sync_event(op_id, "applied", "delivery-uuid-x")]

        mock_db = MagicMock()
        q = _mock_query(data=events)
        mock_db.table.return_value = q

        with patch("app.api.routes.sync.get_supabase", return_value=mock_db):
            app.dependency_overrides[get_current_user] = lambda: DRIVER_USER
            try:
                resp = client.get("/api/v1/sync/status")
            finally:
                app.dependency_overrides.clear()

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert len(body["events"]) == 1
        assert body["events"][0]["operation_id"] == op_id
        assert body["events"][0]["status"] == "applied"

    def test_empty_history_returns_zero(self, app, client: TestClient):
        """If the driver has no sync history, returns empty list."""
        mock_db = MagicMock()
        q = _mock_query(data=[])
        mock_db.table.return_value = q

        with patch("app.api.routes.sync.get_supabase", return_value=mock_db):
            app.dependency_overrides[get_current_user] = lambda: DRIVER_USER
            try:
                resp = client.get("/api/v1/sync/status")
            finally:
                app.dependency_overrides.clear()

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["events"] == []
