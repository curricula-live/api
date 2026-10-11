"""Rate-limit boundary tests. They never persist raw email identifiers."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from django.test import override_settings

from core.owner_rate_limit import (
    ADDRESS_LIMIT, GLOBAL_LIMIT, WINDOW, bucket_key, consume_owner_request_quota
)

KEY = "isolated-ci-only-hmac-rate-key-of-adequate-length"
NOW = datetime(2026, 10, 12, tzinfo=timezone.utc)


@override_settings(OWNER_RATE_LIMIT_KEY=KEY)
def test_digest_is_windowed_and_domain_separated():
    a = bucket_key("address", "owner@example.org", NOW)
    b = bucket_key("address", "unknown@example.org", NOW)
    assert len(a) == 64 and a != b
    assert "owner@" not in a
    assert bucket_key("address", "owner@example.org", NOW + WINDOW) != a
    assert bucket_key("global", "owner@example.org", NOW) != a


def test_missing_or_weak_key_is_rejected():
    with override_settings(OWNER_RATE_LIMIT_KEY="short"):
        with pytest.raises(ValueError, match="not configured"):
            bucket_key("address", "x@example.org", NOW)


@override_settings(OWNER_RATE_LIMIT_KEY=KEY)
def test_rate_limit_sql_is_atomic_and_never_contains_plaintext_address():
    class Cursor:
        def __init__(self):
            self.calls = []
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def execute(self, sql, args):
            self.calls.append((sql, args))
            assert "on conflict (bucket_key) do update" in sql
            assert "returning attempts" in sql
        def fetchone(self): return (1,)

    cursor = Cursor()
    from contextlib import nullcontext
    with patch("core.owner_rate_limit.connection.cursor", return_value=cursor), patch(
        "core.owner_rate_limit.transaction.atomic", return_value=nullcontext()
    ):
        assert consume_owner_request_quota("owner@example.org", now=NOW)
    assert len(cursor.calls) == 2
    assert cursor.calls[0][1][1] == GLOBAL_LIMIT
    assert cursor.calls[1][1][1] == ADDRESS_LIMIT
    assert "owner@example.org" not in str(cursor.calls)


@override_settings(OWNER_RATE_LIMIT_KEY=KEY)
def test_naive_timestamp_denied():
    with pytest.raises(ValueError, match="aware"):
        consume_owner_request_quota("owner@example.org", now=NOW.replace(tzinfo=None))
