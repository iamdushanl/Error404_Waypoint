"""
Phase 6 Delivery Execution tests.

Covers:
  - Delivery outcome recording (POST /api/v1/deliveries)
  - Offline sync idempotency (offline_operation_id)
  - Duplicate stop delivery prevention
  - Proof of Delivery (POST/GET /api/v1/deliveries/{id}/pod)
  - Shortfall reporting (POST/GET /api/v1/trips/{trip_id}/stops/{stop_id}/shortfalls)
  - Store manager receipt confirmation (POST /api/v1/deliveries/{id}/confirm)
  - Trip completion (PATCH /api/v1/trips/{trip_id}/complete)
  - Role-based authorization enforcement
"""
from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import MagicMock, patch

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


# Mock users for each role
DRIVER_USER = {
    "id": "driver-uuid-1",
    "email": "driver@waypoint.demo",
    "full_name": "Driver Silva",
    "role": "driver",
    "outlet_id": None,
    "depot": "Peliyagoda",
    "vehicle_id": "veh-101",
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

STORE_MANAGER_USER = {
    "id": "sm-uuid-1",
    "email": "sm@waypoint.demo",
    "full_name": "Store Manager Perera",
    "role": "store_manager",
    "outlet_id": "out-001",
    "depot": None,
    "vehicle_id": None,
}

DISPATCHER_USER = {
    "id": "disp-uuid-1",
    "email": "dispatcher@waypoint.demo",
    "full_name": "Dispatcher Jayasinghe",
    "role": "dispatcher",
    "outlet_id": None,
    "depot": "Peliyagoda",
    "vehicle_id": None,
}


def _mock_query(data: Any = None):
    mock = MagicMock()
    mock.execute.return_value.data = data
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.in_.return_value = mock
    mock.order.return_value = mock
    mock.maybe_single.return_value = mock
    mock.single.return_value = mock
    mock.insert.return_value = mock
    mock.update.return_value = mock
    return mock


class TestDeliveryPermissions:
    """Verify role-based access control for Phase 6 endpoints."""

    def test_unauthenticated_requests_return_401(self, client: TestClient):
        assert client.post("/api/v1/deliveries", json={}).status_code == 401
        assert client.post("/api/v1/deliveries/del-1/pod", json={}).status_code == 401
        assert client.post("/api/v1/deliveries/del-1/confirm", json={}).status_code == 401
        assert client.post("/api/v1/trips/t-1/stops/s-1/shortfalls", json={}).status_code == 401
        assert client.patch("/api/v1/trips/t-1/complete").status_code == 401

    def test_non_driver_cannot_record_delivery(self, app, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: LOADER_USER
        try:
            resp = client.post(
                "/api/v1/deliveries",
                json={"trip_stop_id": "s-1", "outcome": "delivered"},
            )
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.clear()

    def test_driver_cannot_record_shortfall(self, app, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: DRIVER_USER
        try:
            resp = client.post(
                "/api/v1/trips/t-1/stops/s-1/shortfalls",
                json={
                    "issue_type": "missing",
                    "sku": "SKU-01",
                    "description": "Apples",
                    "expected_quantity": 10,
                    "actual_quantity": 8,
                },
            )
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.clear()

    def test_loader_cannot_confirm_receipt(self, app, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: LOADER_USER
        try:
            resp = client.post(
                "/api/v1/deliveries/del-1/confirm",
                json={"items_received": {"SKU-01": 10}},
            )
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.clear()


class TestRecordDelivery:
    """Tests for POST /api/v1/deliveries."""

    def test_record_delivery_success(self, app, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: DRIVER_USER
        mock_db = MagicMock()

        # Stop query
        stop_data = {
            "id": "stop-101",
            "trip_id": "trip-202",
            "order_id": "order-303",
            "status": "pending",
            "trips": {"vehicle_id": "veh-101", "status": "departed"},
        }

        mock_delivery_record = {
            "id": "del-505",
            "trip_stop_id": "stop-101",
            "driver_id": DRIVER_USER["id"],
            "outcome": "delivered",
            "recipient_name": "Manager John",
            "notes": "Delivered successfully",
            "delivered_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "offline_operation_id": None,
            "synced_at": None,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        with (
            patch("app.api.routes.deliveries.get_supabase", return_value=mock_db),
            patch("app.api.routes.deliveries.DeliveryRepository") as MockRepoClass,
        ):
            mock_repo = MockRepoClass.return_value
            mock_repo.get_delivery_by_operation_id.return_value = None
            mock_repo.get_delivery_by_stop.return_value = None
            mock_repo.create_delivery.return_value = mock_delivery_record

            mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = stop_data

            resp = client.post(
                "/api/v1/deliveries",
                json={
                    "trip_stop_id": "stop-101",
                    "outcome": "delivered",
                    "recipient_name": "Manager John",
                    "notes": "Delivered successfully",
                },
            )

            assert resp.status_code == 201
            body = resp.json()
            assert body["id"] == "del-505"
            assert body["outcome"] == "delivered"
            assert body["recipient_name"] == "Manager John"
        app.dependency_overrides.clear()

    def test_offline_operation_id_idempotency(self, app, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: DRIVER_USER
        existing_delivery = {
            "id": "del-existing-1",
            "trip_stop_id": "stop-101",
            "driver_id": DRIVER_USER["id"],
            "outcome": "delivered",
            "recipient_name": "Manager John",
            "notes": None,
            "delivered_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "offline_operation_id": "op-uuid-1234",
            "synced_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        with (
            patch("app.api.routes.deliveries.get_supabase"),
            patch("app.api.routes.deliveries.DeliveryRepository") as MockRepoClass,
        ):
            mock_repo = MockRepoClass.return_value
            mock_repo.get_delivery_by_operation_id.return_value = existing_delivery

            resp = client.post(
                "/api/v1/deliveries",
                json={
                    "trip_stop_id": "stop-101",
                    "outcome": "delivered",
                    "offline_operation_id": "op-uuid-1234",
                },
            )

            assert resp.status_code == 200
            assert resp.json()["id"] == "del-existing-1"
        app.dependency_overrides.clear()

    def test_duplicate_delivery_on_stop_returns_409(self, app, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: DRIVER_USER
        with (
            patch("app.api.routes.deliveries.get_supabase"),
            patch("app.api.routes.deliveries.DeliveryRepository") as MockRepoClass,
        ):
            mock_repo = MockRepoClass.return_value
            mock_repo.get_delivery_by_operation_id.return_value = None
            mock_repo.get_delivery_by_stop.return_value = {
                "id": "del-prior",
                "outcome": "delivered",
            }

            resp = client.post(
                "/api/v1/deliveries",
                json={"trip_stop_id": "stop-101", "outcome": "delivered"},
            )
            assert resp.status_code == 409
            assert "already has a delivery record" in resp.json()["detail"]
        app.dependency_overrides.clear()

    def test_delivery_on_nonexistent_stop_returns_404(self, app, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: DRIVER_USER
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = None

        with (
            patch("app.api.routes.deliveries.get_supabase", return_value=mock_db),
            patch("app.api.routes.deliveries.DeliveryRepository") as MockRepoClass,
        ):
            mock_repo = MockRepoClass.return_value
            mock_repo.get_delivery_by_operation_id.return_value = None
            mock_repo.get_delivery_by_stop.return_value = None

            resp = client.post(
                "/api/v1/deliveries",
                json={"trip_stop_id": "stop-unknown", "outcome": "delivered"},
            )
            assert resp.status_code == 404
        app.dependency_overrides.clear()

    def test_delivery_before_trip_departed_returns_409(self, app, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: DRIVER_USER
        mock_db = MagicMock()
        stop_data = {
            "id": "stop-101",
            "trip_id": "trip-202",
            "status": "pending",
            "trips": {"vehicle_id": "veh-101", "status": "loading"},
        }
        mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = stop_data

        with (
            patch("app.api.routes.deliveries.get_supabase", return_value=mock_db),
            patch("app.api.routes.deliveries.DeliveryRepository") as MockRepoClass,
        ):
            mock_repo = MockRepoClass.return_value
            mock_repo.get_delivery_by_operation_id.return_value = None
            mock_repo.get_delivery_by_stop.return_value = None

            resp = client.post(
                "/api/v1/deliveries",
                json={"trip_stop_id": "stop-101", "outcome": "delivered"},
            )
            assert resp.status_code == 409
            assert "only be recorded after the trip has departed" in resp.json()["detail"]
        app.dependency_overrides.clear()


class TestProofOfDelivery:
    """Tests for POST & GET /api/v1/deliveries/{id}/pod."""

    def test_record_pod_success(self, app, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: DRIVER_USER
        delivery = {"id": "del-1", "outcome": "delivered"}
        created_pod = {
            "id": "pod-1",
            "delivery_id": "del-1",
            "recipient_name": "Store Mgr",
            "photo_url": "https://storage.supabase.com/pods/photo.jpg",
            "recipient_signature_url": "https://storage.supabase.com/pods/sig.png",
            "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        with (
            patch("app.api.routes.deliveries.get_supabase"),
            patch("app.api.routes.deliveries.DeliveryRepository") as MockRepoClass,
        ):
            mock_repo = MockRepoClass.return_value
            mock_repo.get_delivery.return_value = delivery
            mock_repo.get_pod.return_value = None
            mock_repo.create_pod.return_value = created_pod

            resp = client.post(
                "/api/v1/deliveries/del-1/pod",
                json={
                    "recipient_name": "Store Mgr",
                    "photo_url": "https://storage.supabase.com/pods/photo.jpg",
                    "recipient_signature_url": "https://storage.supabase.com/pods/sig.png",
                    "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                },
            )
            assert resp.status_code == 201
            assert resp.json()["id"] == "pod-1"
        app.dependency_overrides.clear()

    def test_pod_rejected_if_not_delivered_outcome(self, app, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: DRIVER_USER
        delivery = {"id": "del-1", "outcome": "attempted"}

        with (
            patch("app.api.routes.deliveries.get_supabase"),
            patch("app.api.routes.deliveries.DeliveryRepository") as MockRepoClass,
        ):
            mock_repo = MockRepoClass.return_value
            mock_repo.get_delivery.return_value = delivery

            resp = client.post(
                "/api/v1/deliveries/del-1/pod",
                json={
                    "recipient_name": "Store Mgr",
                    "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                },
            )
            assert resp.status_code == 422
            assert "only be added to a 'delivered' stop" in resp.json()["detail"]
        app.dependency_overrides.clear()

    def test_pod_duplicate_rejected(self, app, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: DRIVER_USER
        delivery = {"id": "del-1", "outcome": "delivered"}
        existing_pod = {"id": "pod-1", "delivery_id": "del-1"}

        with (
            patch("app.api.routes.deliveries.get_supabase"),
            patch("app.api.routes.deliveries.DeliveryRepository") as MockRepoClass,
        ):
            mock_repo = MockRepoClass.return_value
            mock_repo.get_delivery.return_value = delivery
            mock_repo.get_pod.return_value = existing_pod

            resp = client.post(
                "/api/v1/deliveries/del-1/pod",
                json={
                    "recipient_name": "Store Mgr",
                    "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                },
            )
            assert resp.status_code == 409
        app.dependency_overrides.clear()


class TestReceiptConfirmation:
    """Tests for POST /api/v1/deliveries/{id}/confirm."""

    def test_confirm_receipt_success(self, app, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: STORE_MANAGER_USER
        delivery = {"id": "del-1", "outcome": "delivered", "trip_stop_id": "stop-101"}
        created_receipt = {
            "id": "rec-1",
            "delivery_id": "del-1",
            "order_id": "ord-999",
            "confirmed_by": STORE_MANAGER_USER["id"],
            "items_received": {"SKU-A": 5, "SKU-B": 10},
            "issues_noted": "None",
            "confirmed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "order_id": "ord-999"
        }

        with (
            patch("app.api.routes.deliveries.get_supabase", return_value=mock_db),
            patch("app.api.routes.deliveries.DeliveryRepository") as MockRepoClass,
        ):
            mock_repo = MockRepoClass.return_value
            mock_repo.get_delivery.return_value = delivery
            mock_repo.get_receipt.return_value = None
            mock_repo.create_receipt.return_value = created_receipt

            resp = client.post(
                "/api/v1/deliveries/del-1/confirm",
                json={
                    "items_received": {"SKU-A": 5, "SKU-B": 10},
                    "issues_noted": "None",
                },
            )
            assert resp.status_code == 201
            assert resp.json()["id"] == "rec-1"
            assert resp.json()["items_received"] == {"SKU-A": 5, "SKU-B": 10}
        app.dependency_overrides.clear()

    def test_confirm_receipt_rejected_if_not_delivered(self, app, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: STORE_MANAGER_USER
        delivery = {"id": "del-1", "outcome": "refused", "trip_stop_id": "stop-101"}

        with (
            patch("app.api.routes.deliveries.get_supabase"),
            patch("app.api.routes.deliveries.DeliveryRepository") as MockRepoClass,
        ):
            mock_repo = MockRepoClass.return_value
            mock_repo.get_delivery.return_value = delivery

            resp = client.post(
                "/api/v1/deliveries/del-1/confirm",
                json={"items_received": {"SKU-A": 5}},
            )
            assert resp.status_code == 422
        app.dependency_overrides.clear()


class TestShortfalls:
    """Tests for POST /api/v1/trips/{trip_id}/stops/{stop_id}/shortfalls."""

    def test_record_shortfall_success(self, app, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: LOADER_USER
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "id": "stop-1",
            "trip_id": "trip-1",
            "status": "pending",
            "trips": {"status": "loading"},
        }
        shortfall_record = {
            "id": "sf-1",
            "trip_stop_id": "stop-1",
            "issue_type": "damaged",
            "sku": "SKU-100",
            "description": "Milk crate crushed",
            "expected_quantity": 20,
            "actual_quantity": 18,
            "photo_url": None,
            "notes": "2 cartons ruptured",
            "recorded_by": LOADER_USER["id"],
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        with (
            patch("app.api.routes.deliveries.get_supabase", return_value=mock_db),
            patch("app.api.routes.deliveries.DeliveryRepository") as MockRepoClass,
        ):
            mock_repo = MockRepoClass.return_value
            mock_repo.create_shortfall.return_value = shortfall_record

            resp = client.post(
                "/api/v1/trips/trip-1/stops/stop-1/shortfalls",
                json={
                    "issue_type": "damaged",
                    "sku": "SKU-100",
                    "description": "Milk crate crushed",
                    "expected_quantity": 20,
                    "actual_quantity": 18,
                    "notes": "2 cartons ruptured",
                },
            )
            assert resp.status_code == 201
            assert resp.json()["id"] == "sf-1"
            assert resp.json()["actual_quantity"] == 18
        app.dependency_overrides.clear()

    def test_shortfall_actual_not_less_than_expected_returns_422(self, app, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: LOADER_USER
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "id": "stop-1",
            "trip_id": "trip-1",
            "status": "pending",
            "trips": {"status": "loading"},
        }

        with patch("app.api.routes.deliveries.get_supabase", return_value=mock_db):
            resp = client.post(
                "/api/v1/trips/trip-1/stops/stop-1/shortfalls",
                json={
                    "issue_type": "missing",
                    "sku": "SKU-100",
                    "description": "Full quantity arrived",
                    "expected_quantity": 20,
                    "actual_quantity": 20,
                },
            )
            assert resp.status_code == 422
            assert "must be less than expected_quantity" in resp.json()["detail"]
        app.dependency_overrides.clear()

    def test_shortfall_when_trip_not_loading_returns_409(self, app, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: LOADER_USER
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "id": "stop-1",
            "trip_id": "trip-1",
            "status": "pending",
            "trips": {"status": "departed"},
        }

        with patch("app.api.routes.deliveries.get_supabase", return_value=mock_db):
            resp = client.post(
                "/api/v1/trips/trip-1/stops/stop-1/shortfalls",
                json={
                    "issue_type": "missing",
                    "sku": "SKU-100",
                    "description": "Missing",
                    "expected_quantity": 20,
                    "actual_quantity": 10,
                },
            )
            assert resp.status_code == 409
            assert "only be recorded while the trip is loading" in resp.json()["detail"]
        app.dependency_overrides.clear()


class TestTripCompletion:
    """Tests for PATCH /api/v1/trips/{trip_id}/complete."""

    def test_complete_trip_success(self, app, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: DRIVER_USER
        trip_data = {
            "id": "trip-1",
            "plan_id": "dp-1",
            "vehicle_id": DRIVER_USER["vehicle_id"],
            "trip_number": 1,
            "brand": "Waypoint Fresh",
            "district": "Colombo",
            "depot": "Peliyagoda",
            "status": "in_transit",
            "planned_departure_time": "06:00",
            "total_weight_kg": 1500.0,
            "total_volume_m3": 12.0,
            "total_distance_km": 45.0,
            "fuel_used_l": 10.5,
            "estimated_duration_min": 180,
            "loader_acknowledged": True,
            "driver_acknowledged": True,
            "departed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "completed_at": None,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        completed_trip = dict(trip_data, status="completed", completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat())

        mock_repo = MagicMock()
        mock_repo.get.return_value = trip_data
        mock_repo.update_status.return_value = completed_trip

        from app.api.routes.trips import _get_repo
        app.dependency_overrides[_get_repo] = lambda: mock_repo

        try:
            resp = client.patch("/api/v1/trips/trip-1/complete")
            assert resp.status_code == 200
            assert resp.json()["status"] == "completed"
            assert resp.json()["completed_at"] is not None
        finally:
            app.dependency_overrides.clear()

    def test_complete_trip_not_in_transit_returns_409(self, app, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: DRIVER_USER
        trip_data = {
            "id": "trip-1",
            "vehicle_id": DRIVER_USER["vehicle_id"],
            "status": "loading",
            "delivery_plan_id": "dp-1",
            "trip_number": 1,
            "depot": "Peliyagoda",
            "driver_acknowledged": True,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        mock_repo = MagicMock()
        mock_repo.get.return_value = trip_data

        from app.api.routes.trips import _get_repo
        app.dependency_overrides[_get_repo] = lambda: mock_repo

        try:
            resp = client.patch("/api/v1/trips/trip-1/complete")
            assert resp.status_code == 409
            assert "Must be departed or in_transit" in resp.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_complete_trip_different_vehicle_returns_404(self, app, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: DRIVER_USER
        trip_data = {
            "id": "trip-1",
            "vehicle_id": "other-vehicle-999",
            "status": "in_transit",
            "delivery_plan_id": "dp-1",
            "trip_number": 1,
            "depot": "Peliyagoda",
            "driver_acknowledged": True,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        mock_repo = MagicMock()
        mock_repo.get.return_value = trip_data

        from app.api.routes.trips import _get_repo
        app.dependency_overrides[_get_repo] = lambda: mock_repo

        try:
            resp = client.patch("/api/v1/trips/trip-1/complete")
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()
