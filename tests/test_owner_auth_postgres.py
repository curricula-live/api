"""API integration against the *actual data-owned PostgreSQL schema*.

Only the CI job with ADMIN_DDL_PATH and a disposable PostgreSQL test database
runs this test. It does not initialize or contact staging/production databases.
"""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
import sqlparse
from django.conf import settings
from django.db import connection
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from core.owner_session_contract import fingerprint_token

SCHEMA_PATH = os.environ.get("ADMIN_DDL_PATH")
pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(not SCHEMA_PATH, reason="isolated owner PostgreSQL integration job only"),
]


def _install_owner_schema() -> None:
    assert connection.vendor == "postgresql", "admin owner DDL must run against PostgreSQL"
    migration = Path(SCHEMA_PATH)
    assert migration.is_file(), "data-owned migration missing"
    # Split into single statements for psycopg's prepared-query protocol.
    with connection.cursor() as cursor:
        for statement in sqlparse.split(migration.read_text(encoding="utf-8")):
            if statement.strip():
                cursor.execute(statement)


def _get(client, credential: str):
    return client.get(
        reverse("owner-auth-session"),
        HTTP_AUTHORIZATION=f"Bearer {credential}",
        HTTP_X_OWNER_ROLE="owner",  # Must never grant additional privileges.
    )


def test_real_postgres_owner_session_is_revocable_and_owner_gated(client) -> None:
    _install_owner_schema()
    owner_id = uuid4()
    credential = "q" * 43
    digest = fingerprint_token(credential, "session")
    session_id = uuid4()
    now = timezone.now()

    with connection.cursor() as cursor:
        cursor.execute(
            "insert into admin.owner_principal (id, email, role, active) "
            "values (%s, %s, 'owner', true)",
            (owner_id, "owner-ci@example.org"),
        )
        cursor.execute(
            "insert into admin.owner_session "
            "(id, owner_id, token_hash, issued_at, expires_at) "
            "values (%s, %s, %s, %s, %s)",
            (session_id, owner_id, digest, now - timedelta(minutes=2), now + timedelta(minutes=15)),
        )

    with override_settings(OWNER_AUTH_ENABLED=False):
        assert _get(client, credential).status_code == 404

    with override_settings(OWNER_AUTH_ENABLED=True):
        authorized = _get(client, credential)
        assert authorized.status_code == 200
        assert authorized["Cache-Control"] == "private, no-store"
        assert authorized["Vary"] == "Authorization"
        payload = authorized.json()
        assert payload["contract_version"] == "owner-session@1"
        assert payload["role"] == "owner"
        assert payload["subject_id"] == str(owner_id)
        assert payload["active"] is True

        # A different credential cannot adopt the owner role via headers.
        assert _get(client, "r" * 43).status_code == 401

        with connection.cursor() as cursor:
            cursor.execute(
                "update admin.owner_principal set active=false, disabled_at=%s where id=%s",
                (timezone.now(), owner_id),
            )
        assert _get(client, credential).status_code == 401

        with connection.cursor() as cursor:
            cursor.execute(
                "update admin.owner_principal set active=true, disabled_at=null where id=%s",
                (owner_id,),
            )
            cursor.execute(
                "update admin.owner_session set revoked_at=%s where id=%s",
                (timezone.now(), session_id),
            )
        assert _get(client, credential).status_code == 401

        with connection.cursor() as cursor:
            cursor.execute(
                "update admin.owner_session set revoked_at=null, expires_at=%s where id=%s",
                (timezone.now() - timedelta(seconds=1), session_id),
            )
        assert _get(client, credential).status_code == 401

    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"
