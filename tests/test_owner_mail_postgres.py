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


@override_settings(**CONFIG)
def test_owner_disabled_between_claim_and_send_does_not_receive_mail():
    email = setup_owner()
    now = timezone.now()
    assert issue_challenge(email, now=now, queue_delivery=True) is not None
    original_claim = claim_next_job

    def disable_after_claim(*, now):
        job = original_claim(now=now)
        assert job is not None
        with connection.cursor() as cursor:
            cursor.execute(
                "update admin.owner_principal set active=false,disabled_at=%s "
                "where email=%s",
                (now, email),
            )
        return job

    with (
        patch("core.owner_mail_worker.claim_next_job", side_effect=disable_after_claim),
        patch("core.owner_mail_worker.send_mail") as mail,
    ):
        assert dispatch_one(now=now + timedelta(seconds=1)) == "discarded"
    mail.assert_not_called()


@override_settings(**CONFIG)
def test_challenge_consumed_between_claim_and_send_does_not_receive_mail():
    email = setup_owner()
    now = timezone.now()
    assert issue_challenge(email, now=now, queue_delivery=True) is not None
    original_claim = claim_next_job

    def consume_after_claim(*, now):
        job = original_claim(now=now)
        assert job is not None
        with connection.cursor() as cursor:
            cursor.execute(
                "update admin.email_challenge set consumed_at=%s where id=%s",
                (now, job.challenge_id),
            )
        return job

    with (
        patch("core.owner_mail_worker.claim_next_job", side_effect=consume_after_claim),
        patch("core.owner_mail_worker.send_mail") as mail,
    ):
        assert dispatch_one(now=now + timedelta(seconds=1)) == "discarded"
    mail.assert_not_called()


@override_settings(**CONFIG)
def test_worker_discards_challenge_with_less_than_thirty_seconds_left():
    email = setup_owner()
    now = timezone.now()
    issue_at = now - timedelta(minutes=9, seconds=45)
    assert issue_challenge(email, now=issue_at, queue_delivery=True) is not None
    with patch("core.owner_mail_worker.send_mail") as mail:
        assert dispatch_one(now=now) == "discarded"
    mail.assert_not_called()


@override_settings(**CONFIG)
def test_full_http_async_owner_login_uses_worker_not_request_thread(client):
    """Request -> PostgreSQL outbox -> mail worker -> redeem -> revoke."""
    import json
    from django.urls import reverse

    email = setup_owner()
    machine_key = "isolated-staging-bff-key-for-postgres-contract"
    headers = {"HTTP_X_ADMIN_BFF_SECRET": machine_key}
    with override_settings(
        OWNER_AUTH_ENABLED=True,
        OWNER_AUTH_HTTP_ENABLED=True,
        OWNER_BFF_SHARED_SECRET=machine_key,
        OWNER_RATE_LIMIT_KEY="independent-staging-quota-key-at-least-32-characters",
    ):
        with patch("core.owner_auth_http.send_mail") as forbidden_inline:
            request = client.post(
                reverse("owner-auth-request"),
                data=json.dumps({"email": email}),
                content_type="application/json",
                **headers,
            )
        assert request.status_code == 202
        assert "challenge" not in request.content.decode()
        forbidden_inline.assert_not_called()

        with connection.cursor() as cursor:
            cursor.execute("select count(*) from admin.owner_email_outbox")
            assert cursor.fetchone()[0] == 1

        with patch("core.owner_mail_worker.send_mail", return_value=1) as delivery:
            assert dispatch_one() == "delivered"
        assert delivery.call_count == 1
        link = delivery.call_args.args[1]
        token = link.split("#challenge=", 1)[1].splitlines()[0]

        redeemed = client.post(
            reverse("owner-auth-redeem"),
            data=json.dumps({"challenge": token}),
            content_type="application/json",
            **headers,
        )
        assert redeemed.status_code == 200
        bearer = redeemed.json()["session_token"]
        assert bearer not in str(request.content)
        assert client.post(
            reverse("owner-auth-redeem"),
            data=json.dumps({"challenge": token}),
            content_type="application/json",
            **headers,
        ).status_code == 401
        assert client.get(
            reverse("owner-auth-session"),
            HTTP_AUTHORIZATION="Bearer " + bearer,
        ).status_code == 200
        assert client.post(
            reverse("owner-auth-logout"),
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer " + bearer,
            **headers,
        ).status_code == 204
        assert client.get(
            reverse("owner-auth-session"),
            HTTP_AUTHORIZATION="Bearer " + bearer,
        ).status_code == 401


@override_settings(**CONFIG)
def test_maintenance_discards_expired_mail_without_sending():
    from core.owner_mail_maintenance import sweep_owner_mail

    email = setup_owner()
    now = timezone.now()
    assert issue_challenge(email, now=now - timedelta(minutes=11), queue_delivery=True)
    assert sweep_owner_mail(now=now) == (1, 0)
    assert sweep_owner_mail(now=now) == (0, 0)
    with patch("core.owner_mail_worker.send_mail") as mail:
        assert dispatch_one(now=now) == "idle"
    mail.assert_not_called()


@override_settings(**CONFIG)
def test_maintenance_does_not_clear_an_active_worker_lease():
    from core.owner_mail_maintenance import sweep_owner_mail

    email = setup_owner()
    now = timezone.now()
    assert issue_challenge(email, now=now - timedelta(minutes=9, seconds=40),
                           queue_delivery=True)
    lease = claim_next_job(now=now)
    assert lease is not None
    # The challenge expires while the worker holds the lease. Cleanup must
    # defer until the lease expires rather than overwriting its fence.
    assert sweep_owner_mail(now=now + timedelta(seconds=21)) == (0, 0)
    assert sweep_owner_mail(now=now + timedelta(seconds=91)) == (1, 0)
    assert not finalize_job(lease, "delivered", now=now + timedelta(seconds=91))


@override_settings(**CONFIG)
def test_maintenance_discards_crashed_fifth_attempt_and_prunes_old_quotas():
    from core.owner_mail_maintenance import sweep_owner_mail

    email = setup_owner()
    now = timezone.now()
    assert issue_challenge(email, now=now, queue_delivery=True)
    with connection.cursor() as cursor:
        cursor.execute("update admin.owner_email_outbox set attempts=5")
        cursor.execute(
            "insert into admin.owner_auth_rate_bucket (bucket_key,first_seen_at) "
            "values (%s,%s),(%s,%s)",
            ("c" * 64, now - timedelta(days=3), "d" * 64, now),
        )
    assert sweep_owner_mail(now=now, batch=1) == (1, 1)
    assert sweep_owner_mail(now=now, batch=1) == (0, 0)
    with connection.cursor() as cursor:
        cursor.execute("select bucket_key from admin.owner_auth_rate_bucket")
        assert cursor.fetchall() == [("d" * 64,)]


@override_settings(**CONFIG)
def test_owner_mail_cleanup_refuses_production_even_with_feature_flag():
    from core.owner_mail_maintenance import sweep_owner_mail

    setup_owner()
    with override_settings(APP_ENV="production", IS_PRODUCTION=True):
        with pytest.raises(RuntimeError, match="disabled"):
            sweep_owner_mail()
