"""Owner lifecycle service tests: replay, cooldown and secret-storage boundaries."""
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import UUID

import pytest

from core.owner_passwordless import (
    CHALLENGE_TTL,
    ISSUE_COOLDOWN,
    SESSION_TTL,
    issue_challenge,
    normalized_email,
    redeem_challenge,
    revoke_session,
)
from core.owner_session_contract import fingerprint_token

OWNER = UUID("c74fe051-ac5e-521b-8770-3180fb0decb6")
NOW = datetime(2026, 10, 12, 0, tzinfo=timezone.utc)


class Cursor:
    def __init__(self, results):
        self.results = iter(results)
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params):
        self.statements.append((sql, params))

    def fetchone(self):
        return next(self.results)


def run_with_fake_db(cursor, callback):
    with (
        patch("core.owner_passwordless.transaction.atomic", return_value=nullcontext()),
        patch("core.owner_passwordless.connection.cursor", return_value=cursor),
    ):
        return callback()


def test_normalization_and_invalid_identity():
    assert normalized_email("  Owner@EXAMPLE.org ") == "owner@example.org"
    for invalid in ("", "bad", "bad @example.org", "a" * 321, None):
        assert normalized_email(invalid) is None


def test_new_challenge_uses_owner_row_lock_and_stores_only_digest():
    cursor = Cursor([(OWNER,), None])
    issued = run_with_fake_db(
        cursor, lambda: issue_challenge("OWNER@EXAMPLE.org", now=NOW)
    )
    assert issued is not None
    assert issued.expires_at == NOW + CHALLENGE_TTL
    assert len(cursor.statements) == 4
    assert "for update" in cursor.statements[0][0]
    assert cursor.statements[0][1] == ("owner@example.org",)
    assert cursor.statements[1][1] == (OWNER, NOW - ISSUE_COOLDOWN)
    assert cursor.statements[2][1][2] == fingerprint_token(issued.token, "challenge")
    assert issued.token not in str(cursor.statements)
    assert "challenge_issued" in cursor.statements[3][0]


def test_unknown_owner_and_issue_cooldown_do_not_create_secrets():
    for results in ([None], [(OWNER,), (1,)]):
        cursor = Cursor(results)
        result = run_with_fake_db(
            cursor, lambda: issue_challenge("owner@example.org", now=NOW)
        )
        assert result is None
        assert all("insert" not in sql.lower() for sql, _ in cursor.statements)


def test_redeeming_challenge_atomically_creates_one_session():
    cursor = Cursor([(OWNER,)])
    result = run_with_fake_db(
        cursor, lambda: redeem_challenge("a" * 43, now=NOW)
    )
    assert result is not None
    assert result.owner_id == OWNER
    assert result.expires_at == NOW + SESSION_TTL
    assert len(cursor.statements) == 3
    assert "consumed_at is null" in cursor.statements[0][0]
    assert "expires_at>" in cursor.statements[0][0]
    assert cursor.statements[0][1][1] == fingerprint_token("a" * 43, "challenge")
    assert cursor.statements[1][1][2] == fingerprint_token(result.token, "session")
    assert result.token not in str(cursor.statements)
    assert "challenge_redeemed" in cursor.statements[2][0]
    assert "session_created" in cursor.statements[2][0]


def test_used_or_expired_challenge_cannot_create_a_session():
    cursor = Cursor([None])
    assert run_with_fake_db(
        cursor, lambda: redeem_challenge("a" * 43, now=NOW)
    ) is None
    assert len(cursor.statements) == 1


def test_revoke_session_is_idempotent_and_audited():
    first = Cursor([(OWNER,)])
    assert run_with_fake_db(
        first, lambda: revoke_session("b" * 43, now=NOW)
    )
    assert first.statements[0][1][1] == fingerprint_token("b" * 43, "session")
    assert "session_revoked" in first.statements[1][0]

    repeated = Cursor([None])
    assert not run_with_fake_db(
        repeated, lambda: revoke_session("b" * 43, now=NOW)
    )
    assert len(repeated.statements) == 1


def test_invalid_token_never_hits_database():
    cursor = Cursor([])
    assert run_with_fake_db(
        cursor, lambda: redeem_challenge("not-a-random-token", now=NOW)
    ) is None
    assert not run_with_fake_db(
        cursor, lambda: revoke_session("not-a-random-token", now=NOW)
    )
    assert cursor.statements == []


def test_naive_timestamp_fails_before_database_access():
    with pytest.raises(ValueError, match="timezone-aware"):
        issue_challenge("owner@example.org", now=NOW.replace(tzinfo=None))
    with pytest.raises(ValueError, match="timezone-aware"):
        redeem_challenge("a" * 43, now=NOW.replace(tzinfo=None))
