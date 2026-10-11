"""Server-side owner session contract and token safety regression tests."""
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from core.owner_session_contract import (
    OWNER_SESSION_CONTRACT_VERSION,
    challenge_is_redeemable,
    fingerprint_token,
    issue_opaque_token,
    owner_session_attestation,
    token_matches,
)

NOW = datetime(2026, 10, 11, 19, 0, tzinfo=timezone.utc)
OWNER_ID = UUID("c74fe051-ac5e-521b-8770-3180fb0decb6")


def test_opaque_tokens_are_unique_and_not_plaintext_at_rest() -> None:
    first = issue_opaque_token()
    second = issue_opaque_token()
    assert first != second
    assert len(first) >= 32
    digest = fingerprint_token(first, "challenge")
    assert len(digest) == 64
    assert first not in digest
    assert token_matches(first, digest, "challenge")
    assert not token_matches(second, digest, "challenge")
    assert not token_matches(first, digest, "session")


def test_token_digest_rejects_malformed_inputs() -> None:
    with pytest.raises(ValueError, match="purpose"):
        fingerprint_token("a" * 40, "other")
    with pytest.raises(ValueError, match="token"):
        fingerprint_token("short", "session")
    assert not token_matches("short", "x", "session")


def test_challenge_expires_and_cannot_be_reused() -> None:
    args = {"issued_at": NOW, "expires_at": NOW + timedelta(minutes=10), "now": NOW}
    assert challenge_is_redeemable(**args, consumed_at=None)
    assert not challenge_is_redeemable(**args, consumed_at=NOW)
    assert not challenge_is_redeemable(**{**args, "now": args["expires_at"]}, consumed_at=None)
    assert not challenge_is_redeemable(**{**args, "now": NOW - timedelta(seconds=1)}, consumed_at=None)


def test_reject_naive_time_for_expiration() -> None:
    with pytest.raises(ValueError, match="timezone"):
        challenge_is_redeemable(
            issued_at=NOW.replace(tzinfo=None),
            expires_at=NOW + timedelta(minutes=5),
            consumed_at=None,
            now=NOW,
        )


def attestation(**changes):
    data = {
        "verified_owner_id": OWNER_ID,
        "verified_role": "owner",
        "owner_active": True,
        "session_revoked": False,
        "session_expires_at": NOW + timedelta(minutes=30),
        "now": NOW,
    }
    return owner_session_attestation(**{**data, **changes})


def test_session_attestation_matches_admin_bff_contract() -> None:
    record = attestation()
    assert record == {
        "contract_version": OWNER_SESSION_CONTRACT_VERSION,
        "authenticated": True,
        "active": True,
        "role": "owner",
        "subject_id": str(OWNER_ID),
        "expires_at": "2026-10-11T19:30:00Z",
    }


@pytest.mark.parametrize("changes", [
    {"verified_role": "admin"},
    {"verified_role": "super_admin"},
    {"verified_role": "staff"},
    {"owner_active": False},
    {"session_revoked": True},
    {"session_expires_at": NOW},
    {"session_expires_at": NOW - timedelta(minutes=1)},
    {"verified_owner_id": str(OWNER_ID)},
])
def test_only_current_verified_owner_receives_authenticated_payload(changes) -> None:
    assert attestation(**changes) is None
