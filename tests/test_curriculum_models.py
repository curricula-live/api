import uuid

from django.db.models.deletion import CASCADE, RESTRICT

from core.models import Concept, Relation, RelationType


def test_concept_uses_slug_as_primary_key():
    primary_key = Concept._meta.pk

    assert primary_key.name == "slug"
    assert primary_key.column == "slug"


def test_relation_type_uses_slug_as_primary_key():
    primary_key = RelationType._meta.pk

    assert primary_key.name == "slug"
    assert primary_key.column == "slug"


def test_relation_maps_expected_database_columns():
    assert Relation._meta.pk.name == "id"
    assert Relation._meta.get_field("source").column == "source"
    assert Relation._meta.get_field("type").column == "type"
    assert Relation._meta.get_field("target").column == "target"


def test_relation_foreign_keys_reference_expected_models():
    source = Relation._meta.get_field("source")
    relation_type = Relation._meta.get_field("type")
    target = Relation._meta.get_field("target")

    assert source.remote_field.model is Concept
    assert relation_type.remote_field.model is RelationType
    assert target.remote_field.model is Concept


def test_relation_reverse_names_are_explicit():
    source = Relation._meta.get_field("source")
    relation_type = Relation._meta.get_field("type")
    target = Relation._meta.get_field("target")

    assert source.remote_field.related_name == "outgoing_relations"
    assert relation_type.remote_field.related_name == "relations"
    assert target.remote_field.related_name == "incoming_relations"


def test_relation_deletion_behaviour_matches_database_schema():
    source = Relation._meta.get_field("source")
    relation_type = Relation._meta.get_field("type")
    target = Relation._meta.get_field("target")

    assert source.remote_field.on_delete is CASCADE
    assert relation_type.remote_field.on_delete is RESTRICT
    assert target.remote_field.on_delete is CASCADE


def test_relation_declares_semantic_unique_constraint():
    constraint = next(
        constraint
        for constraint in Relation._meta.constraints
        if constraint.name == "unique_typed_relation"
    )

    assert tuple(constraint.fields) == ("source", "type", "target")


def test_relation_string_representation_uses_semantic_identity():
    relation = Relation(
        id=uuid.uuid4(),
        source_id="matrix",
        type_id="subtype_of",
        target_id="data-structure",
    )

    assert str(relation) == "matrix —subtype_of→ data-structure"
