"""Disposable PostgreSQL integration test for cross-worker auth quotas.

The test data is isolated by pytest-django transaction rollback; it requires
the pinned data-owned 0002 and 0003 migrations.
"""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import sqlparse
from django.db import connection
from django.test import override_settings

from core.owner_rate_limit import consume_owner_request_quota, bucket_key

FILES = (
    os.environ.get("ADMIN_DDL_PATH"),
    os.environ.get("ADMIN_OUTBOX_DDL_PATH"),
)
pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(not all(FILES), reason="disposable PostgreSQL CI only"),
]


@override_settings(OWNER_RATE_LIMIT_KEY="isolated-ci-only-owner-rate-key-more-than-32")
def test_global_and_address_quotas_are_durable_and_reject_overflow():
    assert connection.vendor == "postgresql"
    with connection.cursor() as cursor:
        for file in FILES:
            for statement in sqlparse.split(Path(file).read_text(encoding="utf-8")):
                if statement.strip():
                    cursor.execute(statement)

    now = datetime(2026, 10, 12, 0, 0, tzinfo=timezone.utc)
    email = "unknown-test@example.org"
    for i in range(3):
        assert consume_owner_request_quota(email, now=now)
    assert consume_owner_request_quota(email, now=now) is False
    assert consume_owner_request_quota("another@example.org", now=now) is True
    assert consume_owner_request_quota(email, now=now+timedelta(minutes=10)) is True

    key = bucket_key("address", email, now)
    with connection.cursor() as cursor:
        cursor.execute(
            "select attempts from admin.owner_auth_rate_bucket where bucket_key=%s",
            (key,),
        )
        assert cursor.fetchone()[0] == 3
        cursor.execute("select bucket_key from admin.owner_auth_rate_bucket")
        assert all("@" not in row[0] for row in cursor.fetchall())
