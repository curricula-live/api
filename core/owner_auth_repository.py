"""PostgreSQL-backed owner session lookup; data owns the operational DDL.

No ORM schema migrations or auto bootstrap. Missing schema fails closed.
Only a server-verified persisted bearer digest may yield owner identity.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from django.db import connection

from core.owner_session_contract import owner_session_attestation


SESSION_LOOKUP_SQL = """
select p.id, p.role, p.active, s.revoked_at, s.expires_at
from admin.owner_session s
join admin.owner_principal p on p.id = s.owner_id
where s.token_hash = %s
limit 1
"""


def find_verified_owner_session(token_digest: str, *, now: datetime | None = None) -> dict[str, Any] | None:
    """Re-read role, active status, expiry and revocation on *every* call."""
    with connection.cursor() as cursor:
        cursor.execute(SESSION_LOOKUP_SQL, (token_digest,))
        row = cursor.fetchone()

    if row is None:
        return None
    owner_id, role, active, revoked_at, expires_at = row
    return owner_session_attestation(
        verified_owner_id=owner_id,
        verified_role=role,
        owner_active=active,
        session_revoked=revoked_at is not None,
        session_expires_at=expires_at,
        now=now or datetime.now(timezone.utc),
    )
