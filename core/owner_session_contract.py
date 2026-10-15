"""Reusable security primitives for the planned single-owner passwordless API.

There is deliberately no login route in this module. The data-owned admin
schema, atomic token consumption, rate limits, owner bootstrap and auditing
must be implemented and tested before these helpers can authenticate requests.
Client-supplied roles must never be passed to owner_session_attestation.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timezone
from uuid import UUID

OWNER_SESSION_CONTRACT_VERSION = "owner-session@1"
_ALLOWED_PURPOSES = frozenset({"challenge", "session"})
_TOKEN = re.compile(r"^[A-Za-z0-9_-]{32,256}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


def issue_opaque_token() -> str:
    """256 bits of entropy; callers must store only a purpose-bound digest."""
    return secrets.token_urlsafe(32)


def fingerprint_token(token: str, purpose: str) -> str:
    """Strong random tokens only; purpose separation avoids token confusion."""
    if purpose not in _ALLOWED_PURPOSES:
        raise ValueError("unknown token purpose")
    if not isinstance(token, str) or not _TOKEN.fullmatch(token):
        raise ValueError("invalid opaque token")
    return hashlib.sha256(f"curricula-owner:{purpose}:{token}".encode("ascii")).hexdigest()


def token_matches(candidate: str, stored_digest: str, purpose: str) -> bool:
    """Timing-safe check. A DB transaction must enforce one-time consumption."""
    if not isinstance(stored_digest, str) or not _DIGEST.fullmatch(stored_digest):
        return False
    try:
        actual = fingerprint_token(candidate, purpose)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, stored_digest)


def _utc(instant: datetime) -> datetime:
    if not isinstance(instant, datetime) or instant.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return instant.astimezone(timezone.utc)


def challenge_is_redeemable(
    *,
    issued_at: datetime,
    expires_at: datetime,
    consumed_at: datetime | None,
    now: datetime,
) -> bool:
    """The caller must additionally atomically mark the challenge consumed."""
    created, expiry, current = (_utc(value) for value in (issued_at, expires_at, now))
    if consumed_at is not None:
        _utc(consumed_at)
        return False
    return created <= current < expiry and created < expiry


def owner_session_attestation(
    *,
    verified_owner_id: UUID,
    verified_role: str,
    owner_active: bool,
    session_revoked: bool,
    session_expires_at: datetime,
    now: datetime,
) -> dict[str, object] | None:
    """Serialize only an already database-verified active owner session.

    Never call with an identity, role or status derived from the request.
    Returns no 'authenticated' payload on any failed role/session check.
    """
    if not isinstance(verified_owner_id, UUID):
        return None
    if verified_role != "owner" or not owner_active or session_revoked:
        return None
    expiry, current = _utc(session_expires_at), _utc(now)
    if expiry <= current:
        return None
    return {
        "contract_version": OWNER_SESSION_CONTRACT_VERSION,
        "authenticated": True,
        "active": True,
        "role": "owner",
        "subject_id": str(verified_owner_id),
        "expires_at": expiry.isoformat().replace("+00:00", "Z"),
    }
