"""Owner session verification HTTP and DB trust-boundary tests.

The data schema itself is tested against PostgreSQL in curricula-live/data#20.
These tests verify Django routing and no privilege escalation via headers.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import UUID

from django.db import OperationalError
from django.test import override_settings
from django.urls import reverse

from core.owner_auth_repository import find_verified_owner_session
from core.owner_session_contract import fingerprint_token

ENDPOINT = "owner-auth-session"
TOKEN = "s" * 43
OWNER_UUID = UUID("c74fe051-ac5e-521b-8770-3180fb0decb6")
NOW = datetime(2026, 10, 11, 19, tzinfo=timezone.utc)


def url():
    return reverse(ENDPOINT)


def attestation():
    return {
        "contract_version": "owner-session@1",
        "authenticated": True,
        "active": True,
        "role": "owner",
        "subject_id": str(OWNER_UUID),
        "expires_at": "2026-10-11T21:00:00Z",
    }


def test_route_is_off_by_default_and_does_not_read_database(client):
    with patch("core.owner_auth_views.find_verified_owner_session") as reader:
        response = client.get(url(), HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
    assert response.status_code == 404
    reader.assert_not_called()


@override_settings(OWNER_AUTH_ENABLED=True)
def test_missing_and_malformed_credentials_return_401_without_lookup(client):
    with patch("core.owner_auth_views.find_verified_owner_session") as reader:
        for value in (None, "Basic xyz", "Bearer short", "Bearer " + "x" * 400):
            kwargs = {} if value is None else {"HTTP_AUTHORIZATION": value}
            response = client.get(url(), **kwargs)
            assert response.status_code == 401
            assert response["Cache-Control"] == "private, no-store"
        reader.assert_not_called()


@override_settings(OWNER_AUTH_ENABLED=True)
def test_verified_owner_payload_only_from_backend_and_digest_not_raw_token(client):
    with patch("core.owner_auth_views.find_verified_owner_session", return_value=attestation()) as reader:
        response = client.get(url(), HTTP_AUTHORIZATION=f"Bearer {TOKEN}", HTTP_X_OWNER_ROLE="owner")
    assert response.status_code == 200
    assert response.json() == attestation()
    assert response["Cache-Control"] == "private, no-store"
    reader.assert_called_once_with(fingerprint_token(TOKEN, "session"))


@override_settings(OWNER_AUTH_ENABLED=True)
def test_unknown_or_revoked_session_fails_closed(client):
    with patch("core.owner_auth_views.find_verified_owner_session", return_value=None):
        response = client.get(url(), HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
    assert response.status_code == 401


@override_settings(OWNER_AUTH_ENABLED=True)
def test_no_user_input_can_assert_owner_by_query_or_body(client):
    with patch("core.owner_auth_views.find_verified_owner_session") as reader:
        response = client.get(url() + "?role=owner&active=true", HTTP_X_OWNER_ROLE="owner")
    assert response.status_code == 401
    reader.assert_not_called()
    assert client.post(url(), {"role": "owner"}).status_code == 405


@override_settings(OWNER_AUTH_ENABLED=True)
def test_database_unavailable_returns_generic_error(client):
    with patch("core.owner_auth_views.find_verified_owner_session", side_effect=OperationalError("secret SQL details")):
        response = client.get(url(), HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
    assert response.status_code == 503
    assert "secret SQL details" not in response.content.decode()


def test_db_repository_rechecks_owner_liveness_expiry_and_revocation():
    rows = [
        (OWNER_UUID, "owner", True, None, NOW + timedelta(hours=1)),
        (OWNER_UUID, "owner", False, None, NOW + timedelta(hours=1)),
        (OWNER_UUID, "super_admin", True, None, NOW + timedelta(hours=1)),
        (OWNER_UUID, "owner", True, NOW, NOW + timedelta(hours=1)),
        (OWNER_UUID, "owner", True, None, NOW),
        None,
    ]

    class Cursor:
        def __init__(self, row):
            self.row = row
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def execute(self, sql, params):
            assert "admin.owner_session" in sql
            assert "admin.owner_principal" in sql
            assert params == ("a" * 64,)
        def fetchone(self):
            return self.row

    for index, row in enumerate(rows):
        with patch("core.owner_auth_repository.connection.cursor", return_value=Cursor(row)):
            result = find_verified_owner_session("a" * 64, now=NOW)
        assert (result is not None) == (index == 0)
        if result:
            assert result["subject_id"] == str(OWNER_UUID)
