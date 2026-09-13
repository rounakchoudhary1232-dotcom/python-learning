from fastapi.testclient import TestClient
from app.main import app


def test_health_returns_api_metadata_and_request_id() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "ultron-api"
    assert response.headers["X-Request-ID"]
