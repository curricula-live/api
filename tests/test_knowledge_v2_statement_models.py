"""Schema-contract checks for data-owned knowledge.predicate/statement ORM mappings.

These tests do not require or modify a production/staging database.
Physical PostgreSQL parity and release pinning remain separate release gates.
"""
from django.db import models

from core.knowledge_v2_models import V2Concept, V2Predicate, V2Statement


def test_v2_models_remain_unmanaged_and_schema_qualified():
    for model, table in (
        (V2Concept, '"knowledge"."concept"'),
        (V2Predicate, '"knowledge"."predicate"'),
        (V2Statement, '"knowledge"."statement"'),
    ):
        assert model._meta.managed is False
        assert model._meta.db_table == table
    assert V2Concept._meta.pk.name == "id"
    assert V2Predicate._meta.pk.name == "slug"
    assert V2Statement._meta.pk.name == "id"
    assert isinstance(V2Statement._meta.pk, models.UUIDField)


def test_statement_fk_columns_and_reference_targets_match_data_ddl():
    expected = {
        "subject_concept": ("subject_concept_id", V2Concept, True),
        "subject_statement": ("subject_statement_id", V2Statement, True),
        "predicate": ("predicate_slug", V2Predicate, False),
        "object_concept": ("object_concept_id", V2Concept, True),
        "object_statement": ("object_statement_id", V2Statement, True),
    }
    for name, (column, target, nullable) in expected.items():
        field = V2Statement._meta.get_field(name)
        assert isinstance(field, models.ForeignKey)
        assert field.column == column
        assert field.remote_field.model is target
        assert field.null is nullable
        assert field.remote_field.on_delete is models.DO_NOTHING
    assert V2Statement._meta.get_field("predicate").target_field.name == "slug"


def test_statement_literal_columns_preserve_jsonb_and_optional_datatype():
    value = V2Statement._meta.get_field("literal_value")
    datatype = V2Statement._meta.get_field("literal_datatype")
    assert isinstance(value, models.JSONField)
    assert value.column == "literal_value"
    assert value.null is True
    assert isinstance(datatype, models.TextField)
    assert datatype.column == "literal_datatype"
    assert datatype.null is True


def test_typed_statement_orm_can_represent_nested_statements_and_literals():
    from uuid import UUID

    sid = UUID("c74fe051-ac5e-521b-8770-3180fb0decb6")
    nested = V2Statement(
        id=sid,
        subject_statement_id=sid,
        predicate_id="part_of",
        literal_value={"text": "example"},
        literal_datatype="json",
    )
    assert nested.subject_statement_id == sid
    assert nested.predicate_id == "part_of"
    assert nested.literal_value == {"text": "example"}
    assert nested.object_concept_id is None
    assert nested.object_statement_id is None
