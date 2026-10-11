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

    session = redeem_challenge(first.token, now=now)
    assert session is not None and session.owner_id == owner_id
    assert redeem_challenge(first.token, now=now) is None

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


def test_post_only_bff_email_exchange_with_real_postgres(client):
    """HTTP challenge + explicit redemption + verification + logout, no SMTP."""
    import json
    from unittest.mock import patch

    _schema()
    identity = uuid4()
    with connection.cursor() as cursor:
        cursor.execute(
            "insert into admin.owner_principal (id,email,role,active) "
            "values (%s,%s,'owner',true)",
            (identity, "owner-end-to-end@example.org"),
        )

    opts = {
        "OWNER_AUTH_ENABLED": True,
        "OWNER_AUTH_HTTP_ENABLED": True,
        "OWNER_BFF_SHARED_SECRET": "disposable-test-only-bff-key-at-least-32-bytes",
        "OWNER_LOGIN_LINK_BASE": "https://admin.curricula.live/login/verify",
        "OWNER_LOGIN_SENDER": "no-reply@curricula.live",
        "IS_PRODUCTION": False,
    }
    machine_header = {"HTTP_X_ADMIN_BFF_SECRET": opts["OWNER_BFF_SHARED_SECRET"]}

    with override_settings(**opts):
        with patch("core.owner_auth_http.send_mail", return_value=1) as send:
            response = client.post(
                reverse("owner-auth-request"),
                data=json.dumps({"email": "owner-end-to-end@example.org"}),
                content_type="application/json",
                **machine_header,
            )
        assert response.status_code == 202
        assert "session_token" not in response.content.decode()
        assert send.call_count == 1
        email_body = send.call_args.args[1]
        assert "#challenge=" in email_body
        challenge = email_body.split("#challenge=", 1)[1].splitlines()[0]
        assert len(challenge) >= 32

        # Link-preview GET cannot redeem it; POST is a deliberate user action.
        assert client.get(reverse("owner-auth-redeem"), **machine_header).status_code == 405

        redemption = client.post(
            reverse("owner-auth-redeem"),
            data=json.dumps({"challenge": challenge}),
            content_type="application/json",
            **machine_header,
        )
        assert redemption.status_code == 200
        bearer = redemption.json()["session_token"]
        assert challenge != bearer
        assert "Cache-Control" in redemption.headers
        assert redemption["Cache-Control"] == "private, no-store"

        replay = client.post(
            reverse("owner-auth-redeem"),
            data=json.dumps({"challenge": challenge}),
            content_type="application/json",
            **machine_header,
        )
        assert replay.status_code == 401

        authorized = client.get(
            reverse("owner-auth-session"),
            HTTP_AUTHORIZATION=f"Bearer {bearer}",
        )
        assert authorized.status_code == 200
        assert authorized.json()["subject_id"] == str(identity)

        out = client.post(
            reverse("owner-auth-logout"),
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {bearer}",
            **machine_header,
        )
        assert out.status_code == 204
        assert client.get(
            reverse("owner-auth-session"),
            HTTP_AUTHORIZATION=f"Bearer {bearer}",
        ).status_code == 401
