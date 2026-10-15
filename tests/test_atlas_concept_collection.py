"""Public Atlas collection contract: bounded, anonymous, disabled in production."""
from unittest.mock import patch

from django.db import ProgrammingError
from django.test import override_settings
from django.urls import reverse

from core.knowledge_v2 import CanonicalConcept
from uuid import UUID

ROUTE = "v2-preview-concept-list"
RECORD = CanonicalConcept(
    id=UUID("c74fe051-ac5e-521b-8770-3180fb0decb6"),
    slug="operating-system",
    label="Operating System",
)


def test_collection_disabled_by_default(client):
    with patch("core.knowledge_v2_repository.list_concepts") as lookup:
        response = client.get(reverse(ROUTE))
    assert response.status_code == 404
    lookup.assert_not_called()


@override_settings(IS_PRODUCTION=True, V2_READ_PREVIEW_ENABLED=True)
def test_collection_disabled_in_production(client):
    with patch("core.knowledge_v2_repository.list_concepts") as lookup:
        response = client.get(reverse(ROUTE))
    assert response.status_code == 404
    lookup.assert_not_called()


@override_settings(IS_PRODUCTION=False, V2_READ_PREVIEW_ENABLED=True)
def test_collection_is_public_and_paginated(client):
    with patch("core.knowledge_v2_repository.list_concepts", return_value=[RECORD]) as lookup:
        response = client.get(reverse(ROUTE), {"limit": "25", "offset": "50"})
    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    assert response.json() == {
        "contract_version": "knowledge-v2-preview@1",
        "release_verified": False,
        "results": [{"id": str(RECORD.id), "slug": RECORD.slug, "label": RECORD.label}],
        "limit": 25,
        "offset": 50,
        "has_more": False,
    }
    lookup.assert_called_once_with(limit=25, offset=50)


@override_settings(IS_PRODUCTION=False, V2_READ_PREVIEW_ENABLED=True)
def test_collection_rejects_invalid_pagination(client):
    for query in ({"limit": "0"}, {"limit": "101"}, {"offset": "-1"}, {"limit": "NaN"}, {"offset": "100001"}):
        with patch("core.knowledge_v2_repository.list_concepts") as lookup:
            response = client.get(reverse(ROUTE), query)
        assert response.status_code == 400
        lookup.assert_not_called()


@override_settings(IS_PRODUCTION=False, V2_READ_PREVIEW_ENABLED=True)
def test_collection_fails_closed_on_missing_database(client):
    with patch("core.knowledge_v2_repository.list_concepts", side_effect=ProgrammingError("sensitive SQL")):
        response = client.get(reverse(ROUTE))
    assert response.status_code == 503
    assert "sensitive SQL" not in response.content.decode()


@override_settings(IS_PRODUCTION=False, V2_READ_PREVIEW_ENABLED=True)
def test_collection_is_get_only(client):
    with patch("core.knowledge_v2_repository.list_concepts") as lookup:
        response = client.post(reverse(ROUTE))
    assert response.status_code == 405
    lookup.assert_not_called()
