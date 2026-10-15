"""Bounded PostgreSQL cleanup for staging owner-email and quota records.

Never sends messages or reconstructs a token. Skip actively leased jobs to
avoid clearing another worker's fence during SMTP dispatch.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.db import connection, transaction

MAX_BATCH = 1000
RETAIN_BUCKETS = timedelta(days=2)


def maintenance_enabled() -> bool:
    return (
        ((getattr(settings, "APP_ENV", "") == "staging" and not settings.IS_PRODUCTION)
         or (getattr(settings, "APP_ENV", "") == "production" and settings.IS_PRODUCTION))
        and getattr(settings, "OWNER_ASYNC_MAIL_ENABLED", False) is True
        and getattr(settings, "OWNER_EMAIL_WORKER_ENABLED", False) is True
    )


def sweep_owner_mail(*, batch: int = 100, now: datetime | None = None) -> tuple[int, int]:
    """Return (discarded_jobs, pruned_buckets), never credentials.

    Short-lived transactions and SKIP LOCKED support concurrent dispatchers.
    The caller schedules this separately; it does not run in a login request.
    """
    if not maintenance_enabled():
        raise RuntimeError("owner mail cleanup disabled")
    if not isinstance(batch, int) or not 1 <= batch <= MAX_BATCH:
        raise ValueError("batch must be an integer between 1 and 1000")
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("aware timestamp required")
    instant = instant.astimezone(timezone.utc)
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                """
                with doomed as (
                    select o.id from admin.owner_email_outbox o
                    join admin.email_challenge c on c.id=o.challenge_id
                    join admin.owner_principal p on p.id=c.owner_id
                    where o.delivered_at is null and o.discarded_at is null
                      and (o.leased_until is null or o.leased_until<=%s)
                      and (c.expires_at<=%s or c.consumed_at is not null
                           or not p.active or o.attempts>=5)
                    order by o.created_at, o.id
                    for update of o skip locked limit %s
                )
                update admin.owner_email_outbox o
                set discarded_at=%s, leased_until=null, lease_token=null
                from doomed where o.id=doomed.id
                returning o.id
                """,
                (instant, instant, batch, instant),
            )
            discarded = len(cursor.fetchall())
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                """
                with old as (
                    select bucket_key from admin.owner_auth_rate_bucket
                    where first_seen_at<%s
                    order by first_seen_at, bucket_key
                    for update skip locked limit %s
                )
                delete from admin.owner_auth_rate_bucket b using old
                where b.bucket_key=old.bucket_key
                returning b.bucket_key
                """,
                (instant - RETAIN_BUCKETS, batch),
            )
            pruned = len(cursor.fetchall())
    return discarded, pruned
