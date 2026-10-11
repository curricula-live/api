"""Internal passwordless owner lifecycle (not wired to public HTTP routes).

Only data-owned admin PostgreSQL tables are used. All secrets are high-entropy
opaque tokens; the database stores purpose-separated SHA-256 digests, never
raw credentials. A one-use challenge is redeemed with atomic UPDATE/RETURNING.
The caller must add email delivery, CSRF and rate limiting before exposing this.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from django.db import connection, transaction

from core.owner_session_contract import fingerprint_token, issue_opaque_token

CHALLENGE_TTL = timedelta(minutes=10)
ISSUE_COOLDOWN = timedelta(minutes=1)
SESSION_TTL = timedelta(hours=8)
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class IssuedChallenge:
    token: str
    expires_at: datetime


@dataclass(frozen=True)
class IssuedSession:
    token: str
    owner_id: UUID
    expires_at: datetime


def normalized_email(value: str) -> str | None:
    if not isinstance(value, str):
        return None
    email = value.strip().lower()
    return email if 3 <= len(email) <= 320 and _EMAIL.fullmatch(email) else None


def utc_now(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return result.astimezone(timezone.utc)


def issue_challenge(email: str, *, now: datetime | None = None) -> IssuedChallenge | None:
    """Return a new challenge only for the provisioned active owner.

    The HTTP layer must never reveal whether an email matched, and must send
    any email only after this transaction has committed successfully.
    """
    identity = normalized_email(email)
    if identity is None:
        return None
    instant = utc_now(now)
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "select id from admin.owner_principal "
                "where email=%s and role='owner' and active for update",
                (identity,),
            )
            owner = cursor.fetchone()
            if owner is None:
                return None
            owner_id = owner[0]
            cursor.execute(
                "select 1 from admin.email_challenge "
                "where owner_id=%s and issued_at>%s limit 1",
                (owner_id, instant - ISSUE_COOLDOWN),
            )
            if cursor.fetchone() is not None:
                return None
            token = issue_opaque_token()
            expires = instant + CHALLENGE_TTL
            cursor.execute(
                "insert into admin.email_challenge "
                "(id,owner_id,token_hash,issued_at,expires_at) "
                "values (%s,%s,%s,%s,%s)",
                (uuid4(), owner_id, fingerprint_token(token, "challenge"), instant, expires),
            )
            cursor.execute(
                "insert into admin.owner_audit (owner_id,event_type) "
                "values (%s,'challenge_issued')",
                (owner_id,),
            )
    return IssuedChallenge(token=token, expires_at=expires)


def redeem_challenge(value: str, *, now: datetime | None = None) -> IssuedSession | None:
    """Atomically redeem one unexpired challenge and create a bearer session."""
    instant = utc_now(now)
    try:
        digest = fingerprint_token(value, "challenge")
    except (ValueError, TypeError):
        return None
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "update admin.email_challenge c set consumed_at=%s "
                "from admin.owner_principal p "
                "where c.owner_id=p.id and c.token_hash=%s "
                "and c.consumed_at is null "
                "and c.issued_at<=%s and c.expires_at>%s "
                "and p.active and p.role='owner' returning c.owner_id",
                (instant, digest, instant, instant),
            )
            owner = cursor.fetchone()
            if owner is None:
                return None
            owner_id = owner[0]
            token = issue_opaque_token()
            expires = instant + SESSION_TTL
            cursor.execute(
                "insert into admin.owner_session "
                "(id,owner_id,token_hash,issued_at,expires_at) "
                "values (%s,%s,%s,%s,%s)",
                (uuid4(), owner_id, fingerprint_token(token, "session"), instant, expires),
            )
            cursor.execute(
                "insert into admin.owner_audit (owner_id,event_type) "
                "values (%s,'challenge_redeemed'),(%s,'session_created')",
                (owner_id, owner_id),
            )
    return IssuedSession(token=token, owner_id=owner_id, expires_at=expires)


def revoke_session(value: str, *, now: datetime | None = None) -> bool:
    instant = utc_now(now)
    try:
        digest = fingerprint_token(value, "session")
    except (ValueError, TypeError):
        return False
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "update admin.owner_session set revoked_at=%s "
                "where token_hash=%s and revoked_at is null returning owner_id",
                (instant, digest),
            )
            owner = cursor.fetchone()
            if owner is None:
                return False
            cursor.execute(
                "insert into admin.owner_audit (owner_id,event_type) "
                "values (%s,'session_revoked')",
                (owner[0],),
            )
    return True
