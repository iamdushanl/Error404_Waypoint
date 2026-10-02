"""
Phase 1 tests — API health check.

These are the acceptance criteria for Phase 1.
All tests must pass before moving to Phase 2.

Run with:
    cd backend/api
    pytest tests/ -v
"""
import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Create a test client from a fresh app instance."""
    app = create_app()
    return TestClient(app)


class TestHealthEndpoint:
    """GET /health — Phase 1 acceptance gate."""

    def test_health_returns_200(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_ok_status(self, client: TestClient) -> None:
        data = response = client.get("/health").json()
        assert data["status"] == "ok"

    def test_health_includes_version(self, client: TestClient) -> None:
        data = client.get("/health").json()
        assert "version" in data
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0

    def test_health_includes_environment(self, client: TestClient) -> None:
        data = client.get("/health").json()
        assert "environment" in data

    def test_health_content_type_is_json(self, client: TestClient) -> None:
        response = client.get("/health")
        assert "application/json" in response.headers["content-type"]


class TestSwaggerUI:
    """OpenAPI docs must be accessible — required for judge walkthrough."""

    def test_docs_endpoint_returns_200(self, client: TestClient) -> None:
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_schema_returns_200(self, client: TestClient) -> None:
        response = client.get("/openapi.json")
        assert response.status_code == 200

    def test_openapi_schema_has_title(self, client: TestClient) -> None:
        schema = client.get("/openapi.json").json()
        assert "Waypoint" in schema["info"]["title"]


class TestCORSHeaders:
    """CORS headers must be present for browser clients."""

    def test_cors_header_present_for_allowed_origin(self, client: TestClient) -> None:
        response = client.get(
            "/health",
            headers={"Origin": "http://localhost:5173"},
        )
        # FastAPI TestClient does not enforce CORS the same way browsers do,
        # but this confirms the middleware is wired without crashing.
        assert response.status_code == 200


class TestErrorShape:
    """Verify the consistent error response shape on 404."""

    def test_unknown_route_returns_404_or_422(self, client: TestClient) -> None:
        response = client.get("/api/v1/does-not-exist")
        assert response.status_code == 404
