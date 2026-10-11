"""Isolated staging owner-mail outbox worker (no raw tokens in PostgreSQL).

One row is leased via SELECT ... FOR UPDATE SKIP LOCKED. Delivery is outside
the database transaction and bounded by Django EMAIL_TIMEOUT. The lease gives
at-least-once delivery after crashes; duplicate mail carries the SAME one-use
challenge. An expired, redeemed or key-mismatched challenge is discarded.
"""
from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from django.conf import settings
from django.core.mail import send_mail
from django.db import connection, transaction

from core.owner_mail_crypto import derive_owner_email_token
from core.owner_session_contract import fingerprint_token

LEASE = timedelta(seconds=90)
MAX_ATTEMPTS = 5


@dataclass(frozen=True)
class MailJob:
    id: UUID
    challenge_id: UUID
    attempts: int
    token_hash: str
    expires_at: datetime
    consumed_at: datetime | None
    email: str
    owner_active: bool
    owner_role: str
    lease_until: datetime


def utc_now(value: datetime | None = None) -> datetime:
    instant = value or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("timestamp must be timezone aware")
    return instant.astimezone(timezone.utc)


def worker_enabled() -> bool:
    from core.owner_auth_http import _link_destination
    return (
        getattr(settings, "APP_ENV", "") == "staging"
        and not getattr(settings, "IS_PRODUCTION", False)
        and getattr(settings, "OWNER_ASYNC_MAIL_ENABLED", False) is True
        and getattr(settings, "OWNER_EMAIL_WORKER_ENABLED", False) is True
        and isinstance(getattr(settings, "OWNER_LOGIN_SENDER", ""), str)
        and bool(getattr(settings, "OWNER_LOGIN_SENDER", "").strip())
        and _link_destination() is not None
        and isinstance(getattr(settings, "OWNER_EMAIL_TOKEN_KEY", ""), str)
        and len(getattr(settings, "OWNER_EMAIL_TOKEN_KEY", "").encode("utf-8")) >= 32
        and 0 < getattr(settings, "EMAIL_TIMEOUT", 0) <= 15
    )


def claim_next_job(*, now: datetime | None = None) -> MailJob | None:
    instant = utc_now(now)
    lease_until = instant + LEASE
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "select o.id,o.challenge_id,o.attempts,c.token_hash,"
                "c.expires_at,c.consumed_at,p.email,p.active,p.role "
                "from admin.owner_email_outbox o "
                "join admin.email_challenge c on c.id=o.challenge_id "
                "join admin.owner_principal p on p.id=c.owner_id "
                "where o.delivered_at is null and o.discarded_at is null "
                "and o.available_at<=%s and (o.leased_until is null or o.leased_until<=%s) "
                "order by o.available_at,o.id for update of o skip locked limit 1",
                (instant, instant),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            cursor.execute(
                "update admin.owner_email_outbox "
                "set attempts=attempts+1,leased_until=%s where id=%s",
                (lease_until, row[0]),
            )
            return MailJob(
                id=row[0], challenge_id=row[1], attempts=row[2] + 1,
                token_hash=row[3], expires_at=row[4], consumed_at=row[5],
                email=row[6], owner_active=row[7], owner_role=row[8],
                lease_until=lease_until,
            )


def finalize_job(
    job: MailJob, result: str, *, now: datetime | None = None
) -> bool:
    """Update only the lease owned by this worker; never override another lease."""
    instant = utc_now(now)
    if result not in ("delivered", "retry", "discarded"):
        raise ValueError("invalid terminal result")
    if result == "retry":
        retry_at = instant + timedelta(seconds=min(30 * (2 ** (job.attempts - 1)), 240))
        if job.attempts >= MAX_ATTEMPTS or retry_at >= job.expires_at:
            result = "discarded"
    else:
        retry_at = instant
    assignments = {
        "delivered": ("delivered_at=%s,leased_until=null", [instant]),
        "discarded": ("discarded_at=%s,leased_until=null", [instant]),
        "retry": ("available_at=%s,leased_until=null", [retry_at]),
    }
    update, args = assignments[result]
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "update admin.owner_email_outbox set " + update +
                " where id=%s and leased_until=%s and delivered_at is null and discarded_at is null",
                (*args, job.id, job.lease_until),
            )
            return cursor.rowcount == 1


def dispatch_one(*, now: datetime | None = None) -> str:
    """Dispatch at most one job, with sanitized result and no credential logging."""
    if not worker_enabled():
        raise RuntimeError("isolated staging owner email worker is disabled")
    instant = utc_now(now)
    job = claim_next_job(now=instant)
    if job is None:
        return "idle"
    # Refuse to send to inactive owners, used/expired links or rotated keys.
    if (not job.owner_active or job.owner_role != "owner" or
            job.consumed_at is not None or job.expires_at <= instant):
        finalize_job(job, "discarded", now=instant)
        return "discarded"
    try:
        from core.owner_auth_http import _link_destination
        token = derive_owner_email_token(job.challenge_id)
        if not hmac.compare_digest(fingerprint_token(token, "challenge"), job.token_hash):
            finalize_job(job, "discarded", now=instant)
            return "discarded"
        destination = _link_destination()
        if destination is None:
            raise RuntimeError("mail link origin not available")
        link = destination + "#challenge=" + token
        sent = send_mail(
            "Sign in to curricula.live administration",
            "Open this link and explicitly confirm sign-in within 10 minutes.\n\n" + link + "\n",
            settings.OWNER_LOGIN_SENDER, [job.email], fail_silently=False,
        )
        if sent != 1:
            raise RuntimeError("mail provider returned no successful delivery")
    except Exception:
        # Deliberately do not log exception text: providers may include links.
        finalize_job(job, "retry", now=instant)
        return "retry"
    finalize_job(job, "delivered", now=instant)
    return "delivered"
