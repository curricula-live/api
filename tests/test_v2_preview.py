"""Integration tests for the opt-in v2 staging read routes.

Physical v2 PostgreSQL parity still needs a staging database. These tests
ensure HTTP wiring, real ORM adapter invocation, and safe default disabling.
"""
from unittest.mock import patch
from uuid import UUID

from django.db import ProgrammingError
from django.test import override_settings
from django.urls import reverse

from core.knowledge_v2 import CanonicalConcept

CONCEPT_ID = UUID("c74fe051-ac5e-521b-8770-3180fb0decb6")
RECORD = CanonicalConcept(id=CONCEPT_ID, slug="operating-system", label="Operating System")
ROUTE_UUID = "v2-preview-concept-uuid"
ROUTE_SLUG = "v2-preview-concept-slug"


def test_disabled_by_default_no_query(client):
    with patch("core.knowledge_v2_repository.get_concept_by_id") as lookup:
        response = client.get(reverse(ROUTE_UUID, kwargs={"concept_id": CONCEPT_ID}))
    assert response.status_code == 404
    lookup.assert_not_called()


@override_settings(IS_PRODUCTION=True, V2_READ_PREVIEW_ENABLED=True)
def test_preview_cannot_be_enabled_in_production(client):
    with patch("core.knowledge_v2_repository.get_concept_by_slug") as lookup:
        response = client.get(reverse(ROUTE_SLUG, kwargs={"slug": "operating-system"}))
    assert response.status_code == 404
    lookup.assert_not_called()


@override_settings(IS_PRODUCTION=False, V2_READ_PREVIEW_ENABLED=True)
def test_real_uuid_repository_read_is_exposed_only_under_preview(client):
    with patch("core.knowledge_v2_repository.get_concept_by_id", return_value=RECORD) as lookup:
        response = client.get(reverse(ROUTE_UUID, kwargs={"concept_id": CONCEPT_ID}))
    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    assert response.json() == {
        "contract_version": "knowledge-v2-preview@1",
        "release_verified": False,
        "concept": {"id": str(CONCEPT_ID), "slug": "operating-system", "label": "Operating System"},
    }
    lookup.assert_called_once_with(CONCEPT_ID)


@override_settings(IS_PRODUCTION=False, V2_READ_PREVIEW_ENABLED=True)
def test_slug_preview_preserves_identity_and_uses_same_read_repository(client):
    with patch("core.knowledge_v2_repository.get_concept_by_slug", return_value=RECORD) as lookup:
        response = client.get(reverse(ROUTE_SLUG, kwargs={"slug": "operating-system"}))
    assert response.status_code == 200
    assert response.json()["concept"]["id"] == str(CONCEPT_ID)
    lookup.assert_called_once_with("operating-system")


@override_settings(IS_PRODUCTION=False, V2_READ_PREVIEW_ENABLED=True)
def test_missing_v2_schema_does_not_expose_sql_errors(client):
    with patch("core.knowledge_v2_repository.get_concept_by_slug", side_effect=ProgrammingError("sensitive details")):
        response = client.get(reverse(ROUTE_SLUG, kwargs={"slug": "operating-system"}))
    assert response.status_code == 503
    assert "sensitive details" not in response.content.decode()
    assert response.json() == {"error": "v2 preview database unavailable"}


@override_settings(IS_PRODUCTION=False, V2_READ_PREVIEW_ENABLED=True)
def test_unknown_v2_concept_is_404_and_not_legacy_fallback(client):
    with patch("core.knowledge_v2_repository.get_concept_by_slug", return_value=None):
        response = client.get(reverse(ROUTE_SLUG, kwargs={"slug": "missing"}))
    assert response.status_code == 404


@override_settings(IS_PRODUCTION=False, V2_READ_PREVIEW_ENABLED=True)
def test_preview_routes_are_read_only(client):
    with patch("core.knowledge_v2_repository.get_concept_by_slug") as lookup:
        response = client.post(reverse(ROUTE_SLUG, kwargs={"slug": "operating-system"}), {})
    assert response.status_code == 405
    lookup.assert_not_called()
