from fastapi.testclient import TestClient
from app.main import app

def test_health_endpoint_reports_non_sensitive_service_state() -> None:
    response = TestClient(app).get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "jarvis-api", "environment": "development"}
