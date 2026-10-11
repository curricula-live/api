"""End-to-end internal owner passwordless lifecycle in disposable PostgreSQL CI.

Uses exactly the data-owned schema pinned in the auth PostgreSQL workflow.
No email transmission, cookie delivery, staging or production connections.
"""
import os
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
import sqlparse
from django.db import connection
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from core.owner_passwordless import issue_challenge, redeem_challenge, revoke_session
from core.owner_session_contract import fingerprint_token

SCHEMA_PATH = os.environ.get("ADMIN_DDL_PATH")
pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(not SCHEMA_PATH, reason="requires isolated PostgreSQL schema CI job"),
]


def _schema():
    assert connection.vendor == "postgresql"
    with connection.cursor() as cursor:
        for statement in sqlparse.split(Path(SCHEMA_PATH).read_text(encoding="utf-8")):
            if statement.strip():
                cursor.execute(statement)


def test_challenge_session_revocation_on_actual_postgresql(client):
    _schema()
    owner_id = uuid4()
    now = timezone.now()
    with connection.cursor() as cursor:
        cursor.execute(
            "insert into admin.owner_principal (id,email,role,active) "
            "values (%s,%s,'owner',true)",
            (owner_id, "owner-ci@example.org"),
        )

    # Unknown addresses never yield a challenge, including future enrollment.
    assert issue_challenge("other@example.org", now=now) is None
    first = issue_challenge("owner-ci@example.org", now=now)
    assert first is not None

    with connection.cursor() as cursor:
        cursor.execute(
            "select token_hash,consumed_at from admin.email_challenge where owner_id=%s",
            (owner_id,),
        )
        rows = cursor.fetchall()
    assert len(rows) == 1
    assert rows[0] == (fingerprint_token(first.token, "challenge"), None)
    assert first.token not in str(rows)

    # Issuance is serialized through the owner row and constrained by cooldown.
    assert issue_challenge("owner-ci@example.org", now=now + timedelta(seconds=1)) is None

    session = redeem_challenge(first.token, now=now + timedelta(seconds=2))
    assert session is not None and session.owner_id == owner_id
    assert redeem_challenge(first.token, now=now + timedelta(seconds=3)) is None

    with connection.cursor() as cursor:
        cursor.execute(
            "select token_hash,revoked_at from admin.owner_session where owner_id=%s",
            (owner_id,),
        )
        sessions = cursor.fetchall()
    assert sessions == [(fingerprint_token(session.token, "session"), None)]
    assert session.token not in str(sessions)

    url = reverse("owner-auth-session")
    with override_settings(OWNER_AUTH_ENABLED=True):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {session.token}"}
        authorized = client.get(url, **headers)
        assert authorized.status_code == 200
        assert authorized.json()["role"] == "owner"
        assert authorized.json()["subject_id"] == str(owner_id)

        with connection.cursor() as cursor:
            cursor.execute(
                "update admin.owner_principal set active=false,disabled_at=%s where id=%s",
                (timezone.now(), owner_id),
            )
        assert client.get(url, **headers).status_code == 401

        with connection.cursor() as cursor:
            cursor.execute(
                "update admin.owner_principal set active=true,disabled_at=null where id=%s",
                (owner_id,),
            )

        assert revoke_session(session.token, now=timezone.now()) is True
        assert client.get(url, **headers).status_code == 401
        assert revoke_session(session.token, now=timezone.now()) is False

    # A fresh challenge outside cooldown is valid, but expires without creating a session.
    second = issue_challenge("owner-ci@example.org", now=now + timedelta(minutes=2))
    assert second is not None
    assert redeem_challenge(second.token, now=second.expires_at) is None
    with connection.cursor() as cursor:
        cursor.execute("select count(*) from admin.owner_session where owner_id=%s", (owner_id,))
        assert cursor.fetchone()[0] == 1
