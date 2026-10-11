"""Read-only v2 ORM query tests; mock physical PostgreSQL until staging exists."""
from unittest.mock import Mock
from uuid import UUID

import pytest

from core.knowledge_v2_models import V2Concept
from core.knowledge_v2_repository import get_concept_by_id, get_concept_by_slug

ID = UUID("c74fe051-ac5e-521b-8770-3180fb0decb6")


def manager_returning(record):
    manager = Mock()
    manager.filter.return_value.values.return_value.first.return_value = record
    return manager


def test_v2_django_model_maps_data_owned_schema_without_managing_it():
    assert V2Concept._meta.db_table == '"knowledge"."concept"'
    assert V2Concept._meta.managed is False
    assert V2Concept._meta.pk.name == "id"
    assert V2Concept._meta.get_field("slug").unique


def test_real_read_model_is_used_for_slug_to_uuid_lookup():
    manager = manager_returning({"id": ID, "slug": "operating-system", "label": "Operating System"})
    item = get_concept_by_slug("operating-system", manager=manager)
    assert item.id == ID
    assert item.as_public_summary() == {"slug": "operating-system"}
    manager.filter.assert_called_once_with(slug="operating-system")


def test_uuid_lookup_survives_slug_rename():
    manager = manager_returning({"id": ID, "slug": "renamed-operating-system", "label": "OS"})
    item = get_concept_by_id(ID, manager=manager)
    assert item.id == ID
    assert item.slug == "renamed-operating-system"
    manager.filter.assert_called_once_with(id=ID)


def test_unknown_record_returns_none():
    assert get_concept_by_slug("missing", manager=manager_returning(None)) is None


def test_invalid_slug_rejected_before_database_access():
    manager = Mock()
    assert get_concept_by_slug("Not A Slug", manager=manager) is None
    manager.filter.assert_not_called()


def test_non_uuid_identifier_rejected():
    with pytest.raises(ValueError, match="canonical UUID"):
        get_concept_by_id("operating-system", manager=Mock())


def test_malformed_v2_row_never_returns_silent_legacy_data():
    manager = manager_returning({"id": ID, "slug": "INVALID slug", "label": "OS"})
    with pytest.raises(ValueError, match="slug"):
        get_concept_by_slug("operating-system", manager=manager)
