"""
Phase 3 tests — Authentication.

Tests:
  - Missing token → 401
  - Invalid token → 401
  - Malformed header → 401
  - /auth/me appears in OpenAPI schema
  - Valid token path (mocked — no live Supabase in CI)

Run with:
    cd backend/api
    pytest tests/ -v
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


class TestAuthEndpointContract:
    """Verify /auth/me appears in the OpenAPI schema."""

    def test_auth_me_in_openapi_schema(self, client: TestClient) -> None:
        schema = client.get("/openapi.json").json()
        paths = schema.get("paths", {})
        assert "/api/v1/auth/me" in paths, "/api/v1/auth/me must be documented in OpenAPI"

    def test_auth_me_requires_get_method(self, client: TestClient) -> None:
        schema = client.get("/openapi.json").json()
        methods = schema["paths"].get("/api/v1/auth/me", {})
        assert "get" in methods


class TestAuthMissingToken:
    """Unauthenticated requests must return 401."""

    def test_no_auth_header_returns_401(self, client: TestClient) -> None:
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_no_auth_header_returns_error_body(self, client: TestClient) -> None:
        response = client.get("/api/v1/auth/me")
        body = response.json()
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]

    def test_empty_bearer_returns_401(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer "},
        )
        assert response.status_code == 401

    def test_wrong_scheme_returns_401(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert response.status_code == 401


class TestAuthInvalidToken:
    """Invalid JWTs must be rejected with 401."""

    def test_garbage_token_returns_401(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer not.a.valid.jwt.at.all"},
        )
        assert response.status_code == 401

    def test_garbage_token_returns_error_code(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer garbage"},
        )
        body = response.json()
        assert body["error"]["code"] == "AUTHENTICATION_REQUIRED"


class TestAuthValidTokenMocked:
    """
    Test the authenticated path with a mocked Supabase response.
    These tests do not require a live Supabase connection.
    """

    MOCK_USER = {
        "id": "4eb77f82-3951-4225-a425-e2de6617c1ae",
        "email": "dispatcher@waypoint.demo",
        "full_name": "Dispatcher Perera",
        "role": "dispatcher",
        "outlet_id": None,
        "depot": "Peliyagoda",
        "vehicle_id": None,
    }

    def _make_valid_token(self) -> str:
        """Create a minimal JWT signed with the test secret."""
        import time
        from jose import jwt as jose_jwt

        # We use a test secret; the mock bypasses real verification
        payload = {
            "sub": self.MOCK_USER["id"],
            "email": self.MOCK_USER["email"],
            "role": "authenticated",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        }
        return jose_jwt.encode(payload, "test-secret", algorithm="HS256")

    def test_valid_token_with_mocked_db_returns_200(self, client: TestClient) -> None:
        """Mock both token verification and DB lookup."""
        token = self._make_valid_token()

        with (
            patch("app.api.deps.verify_supabase_token", return_value={"sub": self.MOCK_USER["id"]}),
            patch("app.api.deps.get_supabase") as mock_supa,
        ):
            # Mock the Supabase client chain: .table().select().eq().single().execute()
            mock_execute = MagicMock()
            mock_execute.data = self.MOCK_USER
            mock_supa.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_execute

            response = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200

    def test_valid_token_returns_correct_role(self, client: TestClient) -> None:
        token = self._make_valid_token()

        with (
            patch("app.api.deps.verify_supabase_token", return_value={"sub": self.MOCK_USER["id"]}),
            patch("app.api.deps.get_supabase") as mock_supa,
        ):
            mock_execute = MagicMock()
            mock_execute.data = self.MOCK_USER
            mock_supa.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_execute

            response = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )

        body = response.json()
        assert body["role"] == "dispatcher"
        assert body["email"] == "dispatcher@waypoint.demo"
        assert body["full_name"] == "Dispatcher Perera"

    def test_valid_token_response_has_all_fields(self, client: TestClient) -> None:
        token = self._make_valid_token()

        with (
            patch("app.api.deps.verify_supabase_token", return_value={"sub": self.MOCK_USER["id"]}),
            patch("app.api.deps.get_supabase") as mock_supa,
        ):
            mock_execute = MagicMock()
            mock_execute.data = self.MOCK_USER
            mock_supa.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_execute

            response = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )

        body = response.json()
        required_fields = ["id", "email", "full_name", "role", "outlet_id", "depot", "vehicle_id"]
        for field in required_fields:
            assert field in body, f"Response missing field: {field}"
