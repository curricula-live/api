"""Disposable PostgreSQL end-to-end owner outbox tests; no real SMTP."""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
import sqlparse
from django.db import connection
from django.test import override_settings
from django.utils import timezone

from core.owner_mail_crypto import derive_owner_email_token
from core.owner_mail_worker import dispatch_one, worker_enabled, claim_next_job, finalize_job
from core.owner_passwordless import issue_challenge, redeem_challenge
from core.owner_session_contract import fingerprint_token

FILES = (os.environ.get("ADMIN_DDL_PATH"), os.environ.get("ADMIN_OUTBOX_DDL_PATH"))
pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(not all(FILES), reason="disposable PostgreSQL CI only"),
]

KEY = "isolated-postgres-owner-mail-derivation-key-long-enough"
CONFIG = {
    "APP_ENV": "staging", "IS_PRODUCTION": False,
    "OWNER_ASYNC_MAIL_ENABLED": True, "OWNER_EMAIL_WORKER_ENABLED": True,
    "OWNER_EMAIL_TOKEN_KEY": KEY,
    "OWNER_LOGIN_SENDER": "no-reply@curricula.live",
    "OWNER_LOGIN_LINK_BASE": "https://admin.curricula.live/login/verify",
    "EMAIL_TIMEOUT": 10,
}


def setup_owner() -> str:
    assert connection.vendor == "postgresql"
    with connection.cursor() as cursor:
        for path in FILES:
            for statement in sqlparse.split(Path(path).read_text(encoding="utf-8")):
                if statement.strip():
                    cursor.execute(statement)
        cursor.execute(
            "insert into admin.owner_principal (id,email) values (%s,%s)",
            (uuid4(), "owner-test@example.org"),
        )
    return "owner-test@example.org"


@override_settings(**CONFIG)
def test_queued_challenge_is_derived_delivered_and_redeemed_without_plaintext_storage():
    email = setup_owner()
    now = timezone.now()
    challenge = issue_challenge(email, now=now, queue_delivery=True)
    assert challenge is not None
    with connection.cursor() as cursor:
        cursor.execute(
            "select o.challenge_id,c.token_hash,o.attempts "
            "from admin.owner_email_outbox o join admin.email_challenge c "
            "on o.challenge_id=c.id"
        )
        queued = cursor.fetchall()
    assert len(queued) == 1
    identifier, stored_digest, count = queued[0]
    assert count == 0
    assert derive_owner_email_token(identifier) == challenge.token
    assert stored_digest == fingerprint_token(challenge.token, "challenge")
    assert challenge.token not in str(queued)
    with patch("core.owner_mail_worker.send_mail", return_value=1) as delivered:
        assert worker_enabled()
        assert dispatch_one(now=now + timedelta(seconds=1)) == "delivered"
    assert delivered.call_count == 1
    assert "#challenge=" + challenge.token in delivered.call_args.args[1]
    assert delivered.call_args.args[3] == [email]
    with connection.cursor() as cursor:
        cursor.execute(
            "select attempts, delivered_at, discarded_at, leased_until "
            "from admin.owner_email_outbox"
        )
        attempts, delivered_at, discarded_at, lease = cursor.fetchone()
    assert (attempts, discarded_at, lease) == (1, None, None)
    assert delivered_at is not None
    assert redeem_challenge(challenge.token, now=now + timedelta(seconds=2)) is not None
    assert redeem_challenge(challenge.token, now=now + timedelta(seconds=3)) is None
    assert dispatch_one(now=now + timedelta(seconds=4)) == "idle"


@override_settings(**CONFIG)
def test_mail_failure_retries_with_backoff_without_leaking_or_losing_challenge():
    email = setup_owner()
    now = timezone.now()
    challenge = issue_challenge(email, now=now, queue_delivery=True)
    assert challenge is not None
    with patch("core.owner_mail_worker.send_mail", side_effect=OSError("sensitive SMTP diagnostic")):
        assert dispatch_one(now=now + timedelta(seconds=1)) == "retry"
    with connection.cursor() as cursor:
        cursor.execute(
            "select attempts,available_at,leased_until from admin.owner_email_outbox"
        )
        attempts, next_time, lease = cursor.fetchone()
    assert attempts == 1 and lease is None
    assert next_time > now + timedelta(seconds=1)
    assert dispatch_one(now=now + timedelta(seconds=2)) == "idle"
    with patch("core.owner_mail_worker.send_mail", return_value=1) as delivered:
        assert dispatch_one(now=now + timedelta(seconds=33)) == "delivered"
    assert delivered.call_count == 1


@override_settings(**CONFIG)
def test_expired_or_rotated_key_jobs_are_discarded_without_email():
    email = setup_owner()
    now = timezone.now()
    challenge = issue_challenge(email, now=now - timedelta(minutes=11), queue_delivery=True)
    assert challenge is not None
    with patch("core.owner_mail_worker.send_mail") as sent:
        assert dispatch_one(now=now) == "discarded"
    sent.assert_not_called()


@override_settings(**CONFIG)
def test_worker_key_rotation_fails_closed_without_sending():
    email = setup_owner()
    now = timezone.now()
    issued = issue_challenge(email, now=now, queue_delivery=True)
    assert issued is not None
    with (override_settings(OWNER_EMAIL_TOKEN_KEY="different-rotated-mail-key-longer-than-32"),
          patch("core.owner_mail_worker.send_mail") as sent):
        assert dispatch_one(now=now + timedelta(seconds=1)) == "discarded"
    sent.assert_not_called()


@override_settings(**CONFIG)
def test_worker_is_denied_outside_isolated_staging():
    setup_owner()
    with override_settings(APP_ENV="production", IS_PRODUCTION=True):
        assert not worker_enabled()
        with pytest.raises(RuntimeError, match="disabled"):
            dispatch_one()
    with override_settings(OWNER_EMAIL_WORKER_ENABLED=False):
        assert not worker_enabled()


@override_settings(**CONFIG)
def test_fencing_token_prevents_stale_worker_finalization():
    email = setup_owner()
    now = timezone.now()
    assert issue_challenge(email, now=now, queue_delivery=True) is not None
    older = claim_next_job(now=now + timedelta(seconds=1))
    assert older is not None
    newer = claim_next_job(now=now + timedelta(seconds=93))
    assert newer is not None
    assert newer.id == older.id and newer.fence != older.fence
    assert newer.attempts == older.attempts + 1
    assert not finalize_job(older, "delivered", now=now + timedelta(seconds=93))
    assert finalize_job(newer, "delivered", now=now + timedelta(seconds=93))
