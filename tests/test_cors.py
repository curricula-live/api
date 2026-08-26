def test_allowed_origin_receives_cors_header(client, settings):
    settings.CORS_ALLOWED_ORIGINS = ["https://curricula.live"]

    response = client.get("/health/", HTTP_ORIGIN="https://curricula.live")

    assert response.status_code == 200
    assert response["Access-Control-Allow-Origin"] == "https://curricula.live"
    assert "Origin" in response.get("Vary", "")


def test_disallowed_origin_receives_no_cors_header(client, settings):
    settings.CORS_ALLOWED_ORIGINS = ["https://curricula.live"]

    response = client.get("/health/", HTTP_ORIGIN="https://example.com")

    assert response.status_code == 200
    assert "Access-Control-Allow-Origin" not in response


def test_allowed_preflight_returns_declared_read_only_contract(client, settings):
    settings.CORS_ALLOWED_ORIGINS = ["https://curricula.live"]

    response = client.options(
        "/api/concepts/",
        HTTP_ORIGIN="https://curricula.live",
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="Authorization, Content-Type",
    )

    assert response.status_code == 204
    assert response["Access-Control-Allow-Origin"] == "https://curricula.live"
    assert response["Access-Control-Allow-Methods"] == "GET, HEAD, OPTIONS"
    assert response["Access-Control-Allow-Headers"] == "Accept, Content-Type, Authorization"
    assert response["Access-Control-Max-Age"] == "86400"
