import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import APP_VERSION


@pytest.fixture
def client():
    return TestClient(app)


def test_root_endpoint_returns_service_info(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "status": "online",
        "service": "curricula.live api",
        "version": APP_VERSION,
    }


def test_health_endpoint_returns_ok_status(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
