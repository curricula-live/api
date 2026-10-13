"""Unauthenticated Atlas preview: bounded, off by default, and not a publication claim."""
from unittest.mock import patch
from uuid import UUID

from django.db import ProgrammingError
from django.test import override_settings
from django.urls import reverse

IDENTIFIER = UUID("c74fe051-ac5e-521b-8770-3180fb0decb6")
STATEMENT = UUID("49100646-6a42-4269-9c62-76b8e42a2295")
ROUTE = "v2-preview-atlas"


def test_atlas_preview_disabled_without_database_queries(client):
    with patch("core.atlas_preview.connection.cursor") as cursor:
        assert client.get(reverse(ROUTE)).status_code == 404
        cursor.assert_not_called()


@override_settings(IS_PRODUCTION=True, V2_READ_PREVIEW_ENABLED=True)
def test_atlas_preview_cannot_run_in_production(client):
    with patch("core.atlas_preview.connection.cursor") as cursor:
        assert client.get(reverse(ROUTE)).status_code == 404
        cursor.assert_not_called()


@override_settings(IS_PRODUCTION=False, V2_READ_PREVIEW_ENABLED=True)
def test_anonymous_get_returns_bounded_nonpublished_canonical_ids(client):
    with patch("core.atlas_preview.connection.cursor") as cursor:
        sql = cursor.return_value.__enter__.return_value
        sql.fetchall.side_effect = [
            [(IDENTIFIER, "operating-system", "Operating System")],
            [(STATEMENT, IDENTIFIER, IDENTIFIER, "part_of")],
        ]
        response = client.get(reverse(ROUTE))
    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    data = response.json()
    assert data["release_verified"] is False
    assert data["review_verified"] is False
    assert data["concepts"][0]["id"] == str(IDENTIFIER)
    assert data["relationships"][0]["id"] == str(STATEMENT)
    assert data["definitions"] == []
    assert data["references"] == []
    assert "auth" not in response.headers
    assert sql.execute.call_count == 2
    assert "limit 20" in sql.execute.call_args_list[0].args[0].lower()
    assert "limit 100" in sql.execute.call_args_list[1].args[0].lower()


@override_settings(IS_PRODUCTION=False, V2_READ_PREVIEW_ENABLED=True)
def test_atlas_preview_no_sql_leak_when_schema_missing(client):
    with patch("core.atlas_preview.connection.cursor", side_effect=ProgrammingError("private schema secret")):
        response = client.get(reverse(ROUTE))
    assert response.status_code == 503
    assert "private schema secret" not in response.content.decode()


@override_settings(IS_PRODUCTION=False, V2_READ_PREVIEW_ENABLED=True)
def test_atlas_preview_is_read_only(client):
    with patch("core.atlas_preview.connection.cursor") as cursor:
        assert client.post(reverse(ROUTE)).status_code == 405
        cursor.assert_not_called()
