"""Contract tests for protected passwordless POST endpoints.

The API-to-BFF secret is a test-only value. No SMTP, credential database, or
production service is contacted. A browser's role headers are never trusted.
"""
import json
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID

import pytest
from django.db import OperationalError
from django.test import override_settings
from django.urls import reverse

from core.owner_passwordless import IssuedChallenge, IssuedSession

SECRET = "test-only-bff-secret-with-at-least-32-randomness-placeholder"
HEADERS = {"HTTP_X_ADMIN_BFF_SECRET": SECRET}
NOW = datetime(2026, 10, 12, 1, 0, tzinfo=timezone.utc)
OWNER = UUID("c74fe051-ac5e-521b-8770-3180fb0decb6")
CHALLENGE = "z" * 43
SESSION = "s" * 43
FLAGS = dict(
    OWNER_AUTH_ENABLED=True,
    OWNER_AUTH_HTTP_ENABLED=True,
    OWNER_BFF_SHARED_SECRET=SECRET,
    OWNER_LOGIN_LINK_BASE="https://admin.curricula.live/login/verify",
    OWNER_LOGIN_SENDER="no-reply@curricula.live",
    IS_PRODUCTION=False,
)


def post(client, name, body, **headers):
    return client.post(
        reverse(name),
        data=json.dumps(body),
        content_type="application/json",
        **headers,
    )


def test_authentication_post_endpoints_disabled_by_default(client):
    for name in ("owner-auth-request", "owner-auth-redeem", "owner-auth-logout"):
        response = post(client, name, {"email": "owner@example.org"}, **HEADERS)
        assert response.status_code == 404


@override_settings(**FLAGS)
def test_bff_shared_secret_and_browser_origin_are_mandatory(client):
    for name in ("owner-auth-request", "owner-auth-redeem", "owner-auth-logout"):
        assert post(client, name, {}, HTTP_X_OWNER_ROLE="owner").status_code == 403
        assert post(client, name, {}, HTTP_X_ADMIN_BFF_SECRET="invalid").status_code == 403
        assert post(client, name, {}, **HEADERS, HTTP_ORIGIN="https://evil.example").status_code == 403
        assert post(client, name, {}, **HEADERS, HTTP_SEC_FETCH_SITE="same-origin").status_code == 403


@override_settings(**FLAGS)
def test_request_challenge_uniform_response_and_no_token_disclosure(client):
    with (
        patch("core.owner_auth_http.issue_challenge", return_value=IssuedChallenge(CHALLENGE, NOW)) as issue,
        patch("core.owner_auth_http.send_mail", return_value=1) as send,
    ):
        response = post(client, "owner-auth-request", {"email": "Owner@Example.org"}, **HEADERS)
    assert response.status_code == 202
    assert response.json() == {"message": "If an eligible account exists, a sign-in email will be sent."}
    assert response["Cache-Control"] == "private, no-store"
    assert CHALLENGE not in response.content.decode()
    issue.assert_called_once_with("owner@example.org")
    assert send.call_count == 1
    assert "https://admin.curricula.live/login/verify#challenge=" + CHALLENGE in send.call_args.args[1]
    assert send.call_args.args[3] == ["owner@example.org"]


@override_settings(**FLAGS)
def test_unknown_or_invalid_email_still_gets_same_response(client):
    with (
        patch("core.owner_auth_http.issue_challenge", return_value=None) as issue,
        patch("core.owner_auth_http.send_mail") as send,
    ):
        unknown = post(client, "owner-auth-request", {"email": "unregistered@example.org"}, **HEADERS)
        malformed = post(client, "owner-auth-request", {"email": "broken email"}, **HEADERS)
    assert unknown.status_code == malformed.status_code == 202
    assert unknown.content == malformed.content
    issue.assert_called_once_with("unregistered@example.org")
    send.assert_not_called()


@override_settings(**FLAGS)
def test_email_provider_failure_is_not_an_account_or_token_oracle(client):
    with (
        patch("core.owner_auth_http.issue_challenge", return_value=IssuedChallenge(CHALLENGE, NOW)),
        patch("core.owner_auth_http.send_mail", side_effect=OSError("SMTP server unavailable")),
    ):
        response = post(client, "owner-auth-request", {"email": "owner@example.org"}, **HEADERS)
    assert response.status_code == 202
    assert CHALLENGE not in str(response.content)
    assert "SMTP" not in str(response.content)


@override_settings(**FLAGS)
def test_redemption_requires_explicit_post_and_returns_secret_only_to_bff(client):
    with patch(
        "core.owner_auth_http.redeem_challenge",
        return_value=IssuedSession(SESSION, OWNER, NOW)
    ) as redeem:
        response = post(
            client, "owner-auth-redeem", {"challenge": CHALLENGE},
            **HEADERS, HTTP_X_OWNER_ROLE="super_admin"
        )
        assert response.status_code == 200
        assert response.json() == {"session_token": SESSION, "expires_at": NOW.isoformat()}
        assert response["Cache-Control"] == "private, no-store"
        redeem.assert_called_once_with(CHALLENGE)

        get = client.get(reverse("owner-auth-redeem"), **HEADERS)
        assert get.status_code == 405
        assert redeem.call_count == 1


@override_settings(**FLAGS)
def test_replay_or_expired_challenge_never_returns_a_session(client):
    with patch("core.owner_auth_http.redeem_challenge", return_value=None):
        invalid = post(client, "owner-auth-redeem", {"challenge": CHALLENGE}, **HEADERS)
    assert invalid.status_code == 401
    assert "session_token" not in invalid.content.decode()


@override_settings(**FLAGS)
def test_database_failure_leaks_no_table_or_sql_details(client):
    with patch("core.owner_auth_http.redeem_challenge", side_effect=OperationalError("admin.owner_session leaked")):
        response = post(client, "owner-auth-redeem", {"challenge": CHALLENGE}, **HEADERS)
    assert response.status_code == 503
    assert b"owner_session" not in response.content


@override_settings(**FLAGS)
def test_logout_is_idempotent_and_never_exposes_token(client):
    with patch("core.owner_auth_http.revoke_session", return_value=False) as revoke:
        response = post(
            client, "owner-auth-logout", {},
            **HEADERS, HTTP_AUTHORIZATION=f"Bearer {SESSION}"
        )
    assert response.status_code == 204
    assert response["Cache-Control"] == "private, no-store"
    revoke.assert_called_once_with(SESSION)


@override_settings(**FLAGS)
def test_malformed_json_and_plain_text_rejected(client):
    response = client.post(
        reverse("owner-auth-request"), "not-json",
        content_type="application/json", **HEADERS
    )
    assert response.status_code == 400
    response = client.post(
        reverse("owner-auth-redeem"), "not-json",
        content_type="text/plain", **HEADERS
    )
    assert response.status_code == 400


@pytest.mark.parametrize("base", [
    "https://evil.example/login/verify",
    "https://admin.curricula.live.evil.example/login/verify",
    "https://admin.curricula.live/login/verify?redirect=evil",
    "http://admin.curricula.live/login/verify",
    "https://user:password@admin.curricula.live/login/verify",
])
def test_unsafe_email_link_base_fails_closed(client, base):
    with override_settings(**{**FLAGS, "OWNER_LOGIN_LINK_BASE": base}):
        with patch("core.owner_auth_http.issue_challenge") as issue:
            response = post(client, "owner-auth-request", {"email": "owner@example.org"}, **HEADERS)
        assert response.status_code == 404
        issue.assert_not_called()
