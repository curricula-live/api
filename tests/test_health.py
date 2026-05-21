from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_endpoint_returns_service_info():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "status": "online",
        "service": "curricula.live api",
        "version": "0.1.0",
    }


def test_health_endpoint_returns_ok_status():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
