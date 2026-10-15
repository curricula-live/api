"""Trusted machine-to-machine CSRF contract with Django's real CSRF middleware.

These endpoints are NOT browser-authenticated. They require the BFF's private
shared secret and reject browser Origin/fetch metadata. The Next.js browser
POST routes independently require exact same-origin requests.
"""
import json
from unittest.mock import patch

from django.test import Client, override_settings
from django.urls import reverse

SETTINGS = dict(
    APP_ENV="staging",
    IS_PRODUCTION=False,
    OWNER_AUTH_ENABLED=True,
    OWNER_AUTH_HTTP_ENABLED=True,
    OWNER_BFF_SHARED_SECRET="isolated-test-only-BFF-secret-at-least-32-bytes",
    OWNER_LOGIN_LINK_BASE="https://admin.curricula.live/login/verify",
    OWNER_LOGIN_SENDER="no-reply@curricula.live",
    OWNER_RATE_LIMIT_KEY="isolated-test-only-quota-secret-at-least-32-bytes",
    OWNER_ASYNC_MAIL_ENABLED=True,
    OWNER_EMAIL_TOKEN_KEY="isolated-test-only-challenge-HMAC-at-least-32-bytes",
)


def _post(client, name, body=None, **headers):
    return client.post(
        reverse(name),
        data=json.dumps(body or {}),
        content_type="application/json",
        **headers,
    )


@override_settings(**SETTINGS)
def test_private_bff_post_works_with_csrf_middleware_enforced():
    client = Client(enforce_csrf_checks=True)
    auth = {"HTTP_X_ADMIN_BFF_SECRET": SETTINGS["OWNER_BFF_SHARED_SECRET"]}
    with (
        patch("core.owner_auth_http.consume_owner_request_quota", return_value=True),
        patch("core.owner_auth_http.issue_challenge", return_value=None) as issue,
    ):
        response = _post(client, "owner-auth-request", {"email": "test-owner@example.invalid"}, **auth)
    assert response.status_code == 202
    issue.assert_called_once_with("test-owner@example.invalid", queue_delivery=True)
    assert response["Cache-Control"] == "private, no-store"


@override_settings(**SETTINGS)
def test_csrf_exemption_never_grants_browser_or_unauthenticated_access():
    client = Client(enforce_csrf_checks=True)
    machine = {"HTTP_X_ADMIN_BFF_SECRET": SETTINGS["OWNER_BFF_SHARED_SECRET"]}
    for name in ("owner-auth-request", "owner-auth-redeem", "owner-auth-logout"):
        assert _post(client, name, {"email": "owner@example.invalid"}).status_code == 403
        assert _post(client, name, {}, HTTP_X_ADMIN_BFF_SECRET="untrusted").status_code == 403
        assert _post(
            client, name, {}, **machine, HTTP_ORIGIN="https://example.invalid",
        ).status_code == 403
        assert _post(
            client, name, {}, **machine, HTTP_SEC_FETCH_SITE="same-origin",
        ).status_code == 403
        assert client.get(reverse(name), **machine).status_code == 405


@override_settings(**{**SETTINGS, "IS_PRODUCTION": True, "APP_ENV": "production"})
def test_private_bff_csrf_exemption_does_not_open_production():
    client = Client(enforce_csrf_checks=True)
    machine = {"HTTP_X_ADMIN_BFF_SECRET": SETTINGS["OWNER_BFF_SHARED_SECRET"]}
    for name in ("owner-auth-request", "owner-auth-redeem", "owner-auth-logout"):
        assert _post(client, name, {}, **machine).status_code == 404
