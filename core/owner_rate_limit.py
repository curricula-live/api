"""Atomic, DB-backed rate limiting for the owner sign-in request path.

No plaintext email, IP or identity is written to the rate-bucket table.
Requires the data-owned migration 0003, installed separately in staging.
"""
from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.db import connection, transaction

WINDOW = timedelta(minutes=10)
GLOBAL_LIMIT = 100
ADDRESS_LIMIT = 3


def _secret() -> bytes:
    value = getattr(settings, "OWNER_RATE_LIMIT_KEY", "")
    if not isinstance(value, str) or len(value.encode("utf-8")) < 32:
        raise ValueError("owner rate-limit key not configured")
    return value.encode("utf-8")


def bucket_key(scope: str, value: str, instant: datetime) -> str:
    """Stable per-window digest, with isolated global/address scopes."""
    if instant.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    window = int(instant.timestamp()) // int(WINDOW.total_seconds())
    payload = f"owner-login:v1:{scope}:{value}:{window}".encode("utf-8")
    return hmac.new(_secret(), payload, hashlib.sha256).hexdigest()


def _increment(cursor, key: str, limit: int) -> bool:
    cursor.execute(
        "insert into admin.owner_auth_rate_bucket (bucket_key,attempts) "
        "values (%s,1) on conflict (bucket_key) do update "
        "set attempts=admin.owner_auth_rate_bucket.attempts+1 "
        "where admin.owner_auth_rate_bucket.attempts<%s returning attempts",
        (key, limit),
    )
    return cursor.fetchone() is not None


def consume_owner_request_quota(email: str, *, now: datetime | None = None) -> bool:
    """Atomically check a global and per-address budget for ALL identities.

    Caller returns the same neutral response regardless of allow/deny or
    whether an owner exists. PostgreSQL serialization prevents multi-instance
    races. The key must not be reused for email-link token derivation.
    """
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None or not isinstance(email, str) or not email:
        raise ValueError("normalized address and aware timestamp required")
    global_key = bucket_key("global", "all", instant)
    address_key = bucket_key("address", email, instant)
    with transaction.atomic():
        with connection.cursor() as cursor:
            # Charge global budget even when the per-address limit is exhausted.
            globally_allowed = _increment(cursor, global_key, GLOBAL_LIMIT)
            address_allowed = _increment(cursor, address_key, ADDRESS_LIMIT)
            return globally_allowed and address_allowed
