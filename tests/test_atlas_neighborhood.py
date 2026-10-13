"""Public UUID neighborhood: anonymous, bounded and staging-gated."""
from unittest.mock import patch
from uuid import UUID

from django.db import ProgrammingError
from django.test import override_settings
from django.urls import reverse

OS = UUID("c74fe051-ac5e-521b-8770-3180fb0decb6")
FILES = UUID("a363a776-30f0-5c1d-983d-339a464062f7")
STATEMENT = UUID("49100646-6a42-4269-9c62-76b8e42a2295")
URL = lambda: reverse("v2-preview-concept-relationships", kwargs={"concept_id": OS})


def test_neighborhood_off_by_default(client):
    with patch("core.atlas_neighborhood.connection.cursor") as cursor:
        assert client.get(URL()).status_code == 404
        cursor.assert_not_called()


@override_settings(IS_PRODUCTION=True, V2_READ_PREVIEW_ENABLED=True)
def test_neighborhood_off_in_production(client):
    with patch("core.atlas_neighborhood.connection.cursor") as cursor:
        assert client.get(URL()).status_code == 404
        cursor.assert_not_called()


@override_settings(IS_PRODUCTION=False, V2_READ_PREVIEW_ENABLED=True)
def test_neighborhood_anonymous_uuid_and_statement_identity(client):
    with patch("core.atlas_neighborhood.connection.cursor") as cursor:
        sql = cursor.return_value.__enter__.return_value
        sql.fetchone.return_value = (OS, "operating-system", "Operating System")
        sql.fetchall.return_value = [(STATEMENT, "part_of", FILES, "file-system", "File System",
                                      OS, "operating-system", "Operating System")]
        response = client.get(URL() + "?limit=1&offset=0")
    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    data = response.json()
    assert data["concept"]["id"] == str(OS)
    assert data["release_verified"] is False
    assert data["review_verified"] is False
    assert data["relationships"][0]["id"] == str(STATEMENT)
    assert data["relationships"][0]["direction"] == "incoming"
    assert data["relationships"][0]["source"]["id"] == str(FILES)
    assert data["relationships"][0]["references"] == []
    assert sql.execute.call_count == 2
    assert sql.execute.call_args_list[1].args[1] == [OS, OS, 2, 0]


@override_settings(IS_PRODUCTION=False, V2_READ_PREVIEW_ENABLED=True)
def test_invalid_pagination_never_queries(client):
    with patch("core.atlas_neighborhood.connection.cursor") as cursor:
        for query in ["?limit=0", "?limit=101", "?limit=garbage",
                      "?offset=-1", "?offset=10001", "?offset=nan"]:
            assert client.get(URL() + query).status_code == 400
        cursor.assert_not_called()


@override_settings(IS_PRODUCTION=False, V2_READ_PREVIEW_ENABLED=True)
def test_missing_schema_safe_failure(client):
    with patch("core.atlas_neighborhood.connection.cursor", side_effect=ProgrammingError("sensitive DDL")):
        response = client.get(URL())
    assert response.status_code == 503
    assert "sensitive DDL" not in response.content.decode()


@override_settings(IS_PRODUCTION=False, V2_READ_PREVIEW_ENABLED=True)
def test_get_only_and_missing_uuid(client):
    assert client.post(URL()).status_code == 405
    with patch("core.atlas_neighborhood.connection.cursor") as cursor:
        cursor.return_value.__enter__.return_value.fetchone.return_value = None
        assert client.get(URL()).status_code == 404
