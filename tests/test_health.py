from django.urls import reverse

def test_health_endpoint(client):
    # respsonse = client.get("/health/")
    response = client.get(reverse("health"))

    assert response.status_code == 200
    assert response.json() == {
            "status": "ok",
            "service": "curricula.live api",
            }   

