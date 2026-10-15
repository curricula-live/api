"""Real anonymous Atlas reads against disposable data-owned PostgreSQL DDL.

Uses the same CI PostgreSQL service as the owner tests, but no owner identity,
session, role or secret. Never connects to staging or production.
"""
from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

import pytest
import sqlparse
from django.db import connection
from django.test import override_settings
from django.urls import reverse

SCHEMA_PATH = os.environ.get("KNOWLEDGE_DDL_PATH")
pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(not SCHEMA_PATH, reason="isolated knowledge PostgreSQL integration job only"),
]
OS = UUID("c74fe051-ac5e-521b-8770-3180fb0decb6")
FILES = UUID("a363a776-30f0-5c1d-983d-339a464062f7")
STATEMENT = UUID("49100646-6a42-4269-9c62-76b8e42a2295")


def test_anonymous_atlas_reads_real_canonical_schema(client):
    assert connection.vendor == "postgresql"
    migration = Path(SCHEMA_PATH)
    assert migration.is_file()
    with connection.cursor() as cursor:
        for sql in sqlparse.split(migration.read_text(encoding="utf-8")):
            if sql.strip():
                cursor.execute(sql)
        cursor.execute(
            "insert into knowledge.concept (id,slug,label) values "
            "(%s,'operating-system','Operating System'), "
            "(%s,'file-system','File System')", [OS, FILES]
        )
        cursor.execute(
            "insert into knowledge.predicate (slug,label) values ('part_of','Part of')"
        )
        cursor.execute(
            "insert into knowledge.statement "
            "(id,subject_concept_id,predicate_slug,object_concept_id) "
            "values (%s,%s,'part_of',%s)", [STATEMENT, FILES, OS]
        )
    with override_settings(IS_PRODUCTION=False, V2_READ_PREVIEW_ENABLED=True):
        result = client.get(reverse("v2-preview-atlas"))
    assert result.status_code == 200
    payload = result.json()
    assert payload["release_verified"] is False
    assert payload["review_verified"] is False
    assert {item["id"] for item in payload["concepts"]} == {str(OS), str(FILES)}
    assert payload["relationships"] == [{
        "id": str(STATEMENT), "from": str(FILES),
        "to": str(OS), "type": "part_of", "review_state": "unverified"
    }]
    assert payload["definitions"] == []
    assert payload["references"] == []

    # Same rows must be traversable anonymously by immutable concept UUID.
    with override_settings(IS_PRODUCTION=False, V2_READ_PREVIEW_ENABLED=True):
        neighborhood = client.get(reverse("v2-preview-concept-relationships", kwargs={"concept_id": OS}))
    assert neighborhood.status_code == 200
    statement = neighborhood.json()["relationships"][0]
    assert statement["id"] == str(STATEMENT)
    assert statement["source"]["id"] == str(FILES)
    assert statement["target"]["id"] == str(OS)
    assert statement["direction"] == "incoming"
