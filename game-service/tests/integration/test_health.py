from fastapi.testclient import TestClient

from immortal_mmo.main import app


def test_health_endpoint_reports_service_status() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "service": "game-service",
        "status": "ok",
        "version": "0.1.0",
    }

