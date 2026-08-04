import uuid

import pytest
from django.db import IntegrityError, transaction

from core.models import Concept, Relation


pytestmark = pytest.mark.django_db


def test_concept_can_be_retrieved_by_slug(curriculum_graph):
    concept = Concept.objects.get(pk="matrix")

    assert concept == curriculum_graph["concepts"]["matrix"]
    assert concept.slug == "matrix"


def test_source_exposes_outgoing_relations(curriculum_graph):
    matrix = curriculum_graph["concepts"]["matrix"]

    outgoing = list(
        matrix.outgoing_relations.order_by("type_id", "target_id").values_list(
            "type_id",
            "target_id",
        )
    )

    assert outgoing == [
        ("subtype_of", "data-structure"),
        ("uses", "array"),
    ]


def test_target_exposes_incoming_relations(curriculum_graph):
    data_structure = curriculum_graph["concepts"]["data-structure"]

    incoming = list(
        data_structure.incoming_relations.order_by("source_id").values_list(
            "source_id",
            "type_id",
        )
    )

    assert incoming == [
        ("array", "subtype_of"),
        ("matrix", "subtype_of"),
    ]


def test_relations_can_be_filtered_by_type_slug(curriculum_graph):
    subtype_relations = list(
        Relation.objects.filter(type_id="subtype_of")
        .order_by("source_id")
        .values_list("source_id", "target_id")
    )

    assert subtype_relations == [
        ("array", "data-structure"),
        ("matrix", "data-structure"),
    ]
    assert curriculum_graph["relation_types"]["subtype_of"].relations.count() == 2


def test_semantic_duplicate_relation_is_rejected(curriculum_graph):
    duplicate = curriculum_graph["relations"][
        ("matrix", "subtype_of", "data-structure")
    ]

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Relation.objects.create(
                id=uuid.uuid4(),
                source_id=duplicate.source_id,
                type_id=duplicate.type_id,
                target_id=duplicate.target_id,
            )
