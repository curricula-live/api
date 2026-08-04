import uuid

import pytest
from django.db import connection

from core.models import Concept, Relation, RelationType


UNMANAGED_CURRICULUM_MODELS = (
    Concept,
    RelationType,
    Relation,
)


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """Create the unmanaged curriculum tables inside the isolated test database."""
    with django_db_blocker.unblock():
        with connection.schema_editor() as schema_editor:
            for model in UNMANAGED_CURRICULUM_MODELS:
                schema_editor.create_model(model)

    yield

    with django_db_blocker.unblock():
        with connection.schema_editor() as schema_editor:
            for model in reversed(UNMANAGED_CURRICULUM_MODELS):
                schema_editor.delete_model(model)


@pytest.fixture
def curriculum_graph(db):
    """Insert a small graph shared by ORM and future API tests."""
    concepts = {
        slug: Concept.objects.create(slug=slug)
        for slug in (
            "array",
            "data-structure",
            "matrix",
        )
    }
    relation_types = {
        slug: RelationType.objects.create(slug=slug)
        for slug in (
            "subtype_of",
            "uses",
        )
    }

    relations = {}
    for source_slug, type_slug, target_slug in (
        ("array", "subtype_of", "data-structure"),
        ("matrix", "subtype_of", "data-structure"),
        ("matrix", "uses", "array"),
    ):
        semantic_key = (source_slug, type_slug, target_slug)
        relations[semantic_key] = Relation.objects.create(
            id=uuid.uuid4(),
            source=concepts[source_slug],
            type=relation_types[type_slug],
            target=concepts[target_slug],
        )

    return {
        "concepts": concepts,
        "relation_types": relation_types,
        "relations": relations,
    }
